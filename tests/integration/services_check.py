#!/usr/bin/env python3
"""Startet library-read (HTTP) und library-ingest (HTTP) als echte Prozesse mit den vom Installer erzeugten Least-Privilege-
Konten/Tokens (*_FILE-Konfiguration) gegen das laufende Sandbox-Paperless und prüft Funktion, Auth und Rechtegrenzen."""
import argparse
import base64
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--root", required=True); ap.add_argument("--sec", required=True); ap.add_argument("--state-before", required=True)
a = ap.parse_args()
sec = Path(a.sec); var = Path("/var/lib/atlas-sandbox/module03"); srv = Path("/srv/atlas-sandbox/module03")
env = {**os.environ, "PYTHONPATH": str(Path(a.root) / "src"), "ATLAS_REGISTRY": str(var / "registry/registry.sqlite3"), "ATLAS_ASSETS": str(srv / "assets"),
       "ATLAS_PAPERLESS_URL": "http://127.0.0.1:18000", "ATLAS_STATE_DIR": str(var / "registry/state"), "ATLAS_CONSUME_DIR": str(srv / "consume"),
       "ATLAS_READ_TOKEN_FILE": str(sec / "library-read-token"), "ATLAS_PAPERLESS_READ_TOKEN_FILE": str(sec / "library-read-paperless-token"),
       "ATLAS_INGEST_TOKEN_FILE": str(sec / "library-ingest-token"), "ATLAS_PAPERLESS_INGEST_TOKEN_FILE": str(sec / "library-ingest-paperless-token"),
       "ATLAS_READ_PORT": "18090", "ATLAS_INGEST_PORT": "18091", "ATLAS_RECONCILE_INTERVAL": "3"}
fail = 0


def check(ok, msg):
    global fail
    print(("PASS: " if ok else "FAIL: ") + msg)
    fail += 0 if ok else 1


def req(url, method="GET", token=None, data=None, headers=None):
    r = urllib.request.Request(url, data=data, method=method, headers={**({"Authorization": f"Bearer {token}"} if token else {}), **(headers or {})})
    try:
        with urllib.request.urlopen(r, timeout=20) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def tok(name):
    return (sec / name).read_text().strip()


procs = [subprocess.Popen([sys.executable, "-m", m], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
         for m in ("atlas_library.http_read", "atlas_library.http_ingest")]
try:
    for port in (18090, 18091):
        for _ in range(40):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=1)
            except urllib.error.HTTPError:
                break  # 401 = Server antwortet
            except Exception:
                time.sleep(0.5)
            else:
                break
    before = json.loads(Path(a.state_before).read_text())
    ent = next(e for e in before["registry_entries"] if e["kind"] == "document")
    ref = f"atlas-library://{ent['atlas_id']}@sha256:{ent['current_hash']}"
    r, t = "http://127.0.0.1:18090", tok("library-read-token")
    check(req(f"{r}/v1/resolve?ref={ref}")[0] == 401, "library-read ohne Token: 401")
    c, b = req(f"{r}/v1/resolve?ref={ref}", token=t); check(c == 200 and b["status"] == "ok", "library-read löst gepinnte Referenz auf")
    c, b = req(f"{r}/v1/documents/file?ref={ref}", token=t)
    check(c == 200 and hashlib.sha256(base64.b64decode(b["content_base64"])).hexdigest() == ent["current_hash"], "library-read liefert hash-geprüftes Original")
    check(req(f"{r}/v1/documents/file?ref={ref}", "DELETE", t)[0] == 405, "library-read: DELETE → 405")
    asset = next(e for e in before["registry_entries"] if e["kind"] == "asset")
    c, b = req(f"{r}/v1/assets?ref=atlas-library://{asset['atlas_id']}@sha256:{asset['current_hash']}", token=t); check(c == 200, "library-read liefert Asset")
    # Rechtegrenze des Paperless-Dienstkontos library-read
    ptok = tok("library-read-paperless-token")
    for method, path in (("PATCH", f"/api/documents/{ent['backend_id']}/"), ("DELETE", f"/api/documents/{ent['backend_id']}/")):
        rq = urllib.request.Request("http://127.0.0.1:18000" + path, data=b"{}", method=method,
                                    headers={"Authorization": f"Token {ptok}", "Content-Type": "application/json", "Accept": "application/json; version=10"})
        try:
            urllib.request.urlopen(rq, timeout=10); code = 200
        except urllib.error.HTTPError as e:
            code = e.code
        check(code == 403, f"Paperless-Konto library-read: {method} → {code} (erwartet 403)")
    # Ingest-Dienst
    i, it = "http://127.0.0.1:18091", tok("library-ingest-token")
    body = ("Dienst-Test synthetisch eindeutig " + os.urandom(6).hex() + "\n").encode()
    check(req(f"{i}/v1/ingest", "POST", None, body, {"X-Filename": "svc.txt"})[0] == 401, "library-ingest ohne Token: 401")
    c, out = req(f"{i}/v1/ingest", "POST", it, body, {"X-Filename": "svc.txt", "X-Hints": json.dumps([{"field": "title", "value": "Dienst-Test", "source": "user"}])})
    check(c == 200 and out["status"] == "queued", "library-ingest nimmt Dokument an")
    check(req(f"{i}/v1/ingest", "POST", it, body, {"X-Filename": "svc2.txt"})[1].get("status") == "duplicate", "library-ingest: Duplikat erkannt, nichts gelöscht")
    check(req(f"{i}/v1/ingest", "DELETE", it)[0] == 405, "library-ingest: DELETE → 405")
    for _ in range(60):  # Hintergrund-Worker ordnet zu (ATLAS-ID), setzt Hinweise
        c, m = req(f"{r}/v1/documents/metadata?ref=atlas-library://{out['atlas_id']}", token=t)
        if c == 200:
            break
        time.sleep(3)
    check(c == 200 and m["paperless"]["title"] == "Dienst-Test", "Worker hat das Dokument zugeordnet (ATLAS-ID) und den Titelhinweis angewendet")
    ptok2 = tok("library-ingest-paperless-token")
    rq = urllib.request.Request(f"http://127.0.0.1:18000/api/documents/{m['paperless'] and ent['backend_id']}/", method="DELETE",
                                headers={"Authorization": f"Token {ptok2}", "Accept": "application/json; version=10"})
    try:
        urllib.request.urlopen(rq, timeout=10); code = 200
    except urllib.error.HTTPError as e:
        code = e.code
    check(code == 403, f"Paperless-Konto library-ingest darf nicht löschen: DELETE → {code}")
finally:
    for p in procs:
        p.terminate()
    for p in procs:
        p.wait(timeout=10)
sys.exit(1 if fail else 0)
