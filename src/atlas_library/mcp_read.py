"""MCP-Server (stdio, JSON-RPC 2.0) für library-read. Nur lesende Tools; keine Schreib-/Löschwerkzeuge.

Der Server liest nur die Registry und spricht Paperless ausschließlich über den read-only ReadClient.
"""
from __future__ import annotations

import json
import os
import sys

from .assets import AssetStore
from .config import secret
from .paperless import ReadClient
from .read import LibraryRead
from .registry import Registry

PROTOCOL_VERSION = "2025-06-18"
_REF = {"type": "object", "properties": {"ref": {"type": "string", "description": "atlas-library://<uuidv7>[@sha256:<hash>]"}},
        "required": ["ref"], "additionalProperties": False}
TOOLS = {
    "search_documents": ("Kompakte Trefferliste (ATLAS-ID, Titel, Datum); Mehrdeutigkeit wird gekennzeichnet.",
                         {"type": "object", "properties": {"query": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 50}},
                          "required": ["query"], "additionalProperties": False}),
    "resolve_atlas_ref": ("Löst eine Referenz auf: ok | revision_mismatch | trashed | deleted | unknown | pending.", _REF),
    "get_document_metadata": ("Strukturierte Metadaten zuerst (vor Volltext).", _REF),
    "get_document_text": ("OCR-/Volltext (begrenzt).", {**_REF, "properties": {**_REF["properties"], "max_chars": {"type": "integer"}}}),
    "get_document_file": ("Originaldatei (Base64, hash-geprüft); mit gepinnter älterer Revision genau diese Fassung.", _REF),
    "get_asset": ("Exaktes Asset (Base64, hash-geprüft); keine Neugenerierung.", _REF),
}


def call_tool(lr: LibraryRead, name: str, a: dict) -> dict:
    if name == "search_documents":
        return lr.search_documents(a["query"], int(a.get("limit", 10)))
    if name == "resolve_atlas_ref":
        return lr.resolve_atlas_ref(a["ref"])
    if name == "get_document_metadata":
        return lr.get_document_metadata(a["ref"])
    if name == "get_document_text":
        return lr.get_document_text(a["ref"], int(a.get("max_chars", 20000)))
    if name == "get_document_file":
        return lr.get_document_file(a["ref"])
    if name == "get_asset":
        return lr.get_asset(a["ref"])
    raise KeyError(name)


def handle(lr: LibraryRead, msg: dict) -> dict | None:
    mid, method = msg.get("id"), msg.get("method")
    if method is not None and mid is None:  # Notification (z. B. notifications/initialized)
        return None
    def ok(result): return {"jsonrpc": "2.0", "id": mid, "result": result}
    def err(code, text): return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": text}}
    if method == "initialize":
        return ok({"protocolVersion": PROTOCOL_VERSION, "capabilities": {"tools": {"listChanged": False}},
                   "serverInfo": {"name": "atlas-library-read", "version": "0.2.0"}})
    if method == "ping":
        return ok({})
    if method == "tools/list":
        return ok({"tools": [{"name": n, "description": d, "inputSchema": s, "annotations": {"readOnlyHint": True, "destructiveHint": False}}
                             for n, (d, s) in TOOLS.items()]})
    if method == "tools/call":
        p = msg.get("params") or {}
        if p.get("name") not in TOOLS:
            return err(-32602, f"unbekanntes Tool: {p.get('name')}")
        try:
            out = call_tool(lr, p["name"], p.get("arguments") or {})
            return ok({"content": [{"type": "text", "text": json.dumps(out, ensure_ascii=False)}],
                       "isError": False})  # Domänenstatus steht im JSON
        except KeyError as exc:
            return err(-32602, f"fehlendes Argument: {exc.args[0]}")
        except Exception:
            return ok({"content": [{"type": "text", "text": json.dumps({"status": "backend_error"})}], "isError": True})
    return err(-32601, "Method not found")


def serve(lr: LibraryRead, stdin=sys.stdin, stdout=sys.stdout) -> None:
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            stdout.write(json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}) + "\n")
            stdout.flush(); continue
        resp = handle(lr, msg)
        if resp is not None:
            stdout.write(json.dumps(resp, ensure_ascii=False) + "\n"); stdout.flush()


def main() -> None:
    env = os.environ
    reg = Registry(env["ATLAS_REGISTRY"])
    assets = AssetStore(env["ATLAS_ASSETS"], reg) if env.get("ATLAS_ASSETS") else None
    serve(LibraryRead(reg, ReadClient(env["ATLAS_PAPERLESS_URL"], secret("ATLAS_PAPERLESS_READ_TOKEN")), assets))


if __name__ == "__main__":
    main()
