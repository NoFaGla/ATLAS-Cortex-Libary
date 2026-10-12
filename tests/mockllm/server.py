#!/usr/bin/env python3
"""Lokaler Mock-LLM-Endpunkt (OpenAI-kompatibel: /v1/chat/completions) für Paperless-GPT-Tests. Nur Standardbibliothek.

Deterministische „Antworten“ aus dem Dokumenttext (Prompt-Typen von Paperless-GPT v0.29.0: Titel, Tags, Korrespondent,
Dokumenttyp, Erstellungsdatum). Fehlermodi per ``POST /_mode {"mode": "..."}``; Statistik per ``GET /_stats``.

Modi: ok | prose (geschwätzige Antwort) | invented (erfundene Typen/Tags/Datum) | empty | http500 | http429 | invalid_json |
      truncated | slow | timeout
"""
import json
import re
import sys
import threading
import time
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

STATE = {"mode": "ok", "requests": 0, "by_kind": {}, "log": []}
LOCK = threading.Lock()
MONTHS = {"januar": 1, "februar": 2, "märz": 3, "maerz": 3, "april": 4, "mai": 5, "juni": 6, "juli": 7, "august": 8,
          "september": 9, "oktober": 10, "november": 11, "dezember": 12}
TYPE_WORDS = [("verdienstabrechnung", "Abrechnung"), ("betriebskostenabrechnung", "Abrechnung"), ("mietvertrag", "Vertrag"),
              ("vertrag", "Vertrag"), ("bescheid", "Bescheid"), ("urkunde", "Urkunde"), ("zeugnis", "Zeugnis"),
              ("quittung", "Rechnung"), ("rechnung", "Rechnung")]


def section(text, tag):
    m = re.search(rf"<{tag}>\s*(.*?)\s*</{tag}>", text, re.S)
    return m.group(1) if m else ""


def kind_of(prompt: str) -> str:
    p = prompt.lower()
    for key, kind in (("suitable document title", "title"), ("select appropriate tags", "tags"), ("suggest a correspondent", "correspondent"),
                      ("most appropriate document type", "document_type"), ("date when the document was created", "created_date")):
        if key in p:
            return kind
    return "other"


def answer(kind: str, prompt: str) -> str:
    content = section(prompt, "content")
    lines = [l.strip() for l in content.splitlines() if l.strip()]
    low = content.lower()
    if kind == "title":
        m = re.search(r"(Verdienstabrechnung|Betriebskostenabrechnung)(?:[ \t]+[\wäöüÄÖÜ]+)?(?:[ \t]+\d{4})?", content)
        return m.group(0) if m else (lines[0][:80] if lines else "Dokument")
    if kind == "correspondent":
        return lines[0] if lines and re.search(r"GmbH|AG|amt|Standesamt|Verein", lines[0]) else "Unknown"
    if kind == "document_type":
        avail = [t.strip() for t in section(prompt, "available_document_types").split(",")]
        for word, t in TYPE_WORDS:
            if word in low and t in avail:
                return t
        return ""
    if kind == "tags":
        avail = [t.strip() for t in section(prompt, "available_tags").split(",")]
        picks = []
        for needle, tag in (("eur", "Thema/Finanzen"), ("steuer", "Thema/Steuern"), ("miet", "Kontext/Wohnen"), ("wohn", "Kontext/Wohnen")):
            if needle in low and tag in avail and tag not in picks:
                picks.append(tag)
        return ", ".join(picks)
    if kind == "created_date":
        m = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", content)
        if m:
            return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
        m = re.search(r"(" + "|".join(MONTHS) + r")\s+(\d{4})", low)
        if m:
            return f"{m.group(2)}-{MONTHS[m.group(1)]:02d}-01"
        return date.today().isoformat()
    return "OK"


def mangle(kind: str, mode: str, good: str) -> str:
    if mode == "prose":
        return f"Okay, based on the document I would say the answer is: **{good}**. Let me know if you need anything else!"
    if mode == "invented":
        return {"title": "Erfundener Titel " + "x" * 300, "tags": "Neu-Tag-1, Neu-Tag-2, Thema/Finanzen", "correspondent": "Erfundene Firma",
                "document_type": "Frei Erfundener Typ", "created_date": "not-a-date"}.get(kind, good)
    return good


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _json(self, code, obj, raw=None):
        body = raw if raw is not None else json.dumps(obj).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        if self.path == "/_stats":
            return self._json(200, {k: STATE[k] for k in ("mode", "requests", "by_kind")})
        if self.path.endswith("/models"):
            return self._json(200, {"object": "list", "data": [{"id": "mock-model", "object": "model"}]})
        self._json(404, {"error": "not found"})

    def do_POST(self):
        n = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(n)
        if self.path == "/_mode":
            with LOCK:
                STATE.update(mode=json.loads(body)["mode"], requests=0, by_kind={})
            return self._json(200, {"mode": STATE["mode"]})
        if not self.path.endswith("/chat/completions"):
            return self._json(404, {"error": "not found"})
        req = json.loads(body or b"{}")
        prompt = "\n".join(m.get("content", "") if isinstance(m.get("content"), str) else json.dumps(m.get("content")) for m in req.get("messages", []))
        kind = kind_of(prompt)
        with LOCK:
            STATE["requests"] += 1
            STATE["by_kind"][kind] = STATE["by_kind"].get(kind, 0) + 1
            mode = STATE["mode"]
        if mode == "timeout":
            time.sleep(600)
        if mode == "slow":
            time.sleep(8)
        if mode == "http500":
            return self._json(500, {"error": {"message": "mock internal error", "type": "server_error"}})
        if mode == "http429":
            return self._json(429, {"error": {"message": "mock rate limit", "type": "rate_limit"}})
        if mode == "invalid_json":
            return self._json(200, None, raw=b"<html>this is not json</html>")
        content = {"empty": ""}.get(mode) if mode == "empty" else mangle(kind, mode, answer(kind, prompt))
        finish = "length" if mode == "truncated" else "stop"
        if mode == "truncated":
            content = answer(kind, prompt)[:3]
        self._json(200, {"id": "mock-1", "object": "chat.completion", "created": int(time.time()), "model": req.get("model", "mock-model"),
                         "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": finish}],
                         "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}})


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()  # nosec B104 - nur im isolierten Docker-Testnetz
