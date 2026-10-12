"""HTTP-Schnittstelle für library-ingest: kontrollierter Import.

POST /v1/ingest   Rohkörper = Dateiinhalt; Header: Authorization: Bearer, X-Filename, X-Hints (JSON-Liste, optional)
POST /v1/revision Header zusätzlich X-Atlas-Id (neue technische Fassung eines aktiven Dokuments)
Es gibt bewusst keine Lösch-, Merge- oder Überschreib-Endpunkte. Ein Hintergrund-Thread führt reconcile und
Lifecycle-Sync aus (ordnet Paperless-Dokumente der ATLAS-ID zu).
"""
from __future__ import annotations

import hmac
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .config import check_bind, secret
from .ingest import IngestError, LibraryIngest
from .paperless import PaperlessError, WriteClient
from .registry import Registry


def make_handler(ing: LibraryIngest, token: str, paperless: WriteClient, max_bytes: int):
    tok = token.encode()

    class H(BaseHTTPRequestHandler):
        server_version = "atlas-library-ingest"
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):
            pass

        def _send(self, code: int, obj: dict):
            body = json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)
            self.close_connection = True

        def _authed(self) -> bool:
            h = self.headers.get("Authorization", "")
            return h.startswith("Bearer ") and hmac.compare_digest(h[7:].encode(), tok)

        def do_POST(self):
            if not self._authed():
                return self._send(401, {"status": "unauthorized"})
            if self.path not in ("/v1/ingest", "/v1/revision"):
                return self._send(404, {"status": "not_found"})
            try:
                n = int(self.headers.get("Content-Length", ""))
            except ValueError:
                return self._send(411, {"status": "length_required"})
            if n <= 0 or n > max_bytes:  # vor dem Lesen ablehnen
                return self._send(413, {"status": "too_large_or_empty"})
            try:
                hints = json.loads(self.headers.get("X-Hints", "[]"))
                if not isinstance(hints, list):
                    raise ValueError
            except ValueError:
                return self._send(400, {"status": "bad_hints"})
            data = self.rfile.read(n)
            name = self.headers.get("X-Filename", "")
            try:
                if self.path == "/v1/ingest":
                    out = ing.ingest_document(token, name, data, hints)
                    return self._send(200, out)
                out = ing.ingest_revision(token, self.headers.get("X-Atlas-Id", ""), paperless, name, data,
                                          self.headers.get("X-Version-Label"))
                return self._send(200, out)
            except IngestError as exc:
                return self._send(422, {"status": "rejected", "error": str(exc)})
            except PaperlessError:
                return self._send(502, {"status": "backend_error"})

        def _deny(self):
            self._send(405, {"status": "method_not_allowed"})

        do_GET = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = _deny

    return H


def worker(ing: LibraryIngest, token: str, paperless: WriteClient, interval: float, stop: threading.Event) -> None:
    while not stop.wait(interval):
        try:
            ing.reconcile(token, paperless)
            ing.sync_lifecycle(token, paperless)
        except Exception:  # Worker darf nie sterben; Fehler erscheinen im nächsten Lauf erneut
            pass


def build_from_env(env=os.environ):
    token = secret("ATLAS_INGEST_TOKEN", env)
    reg = Registry(env["ATLAS_REGISTRY"])
    max_bytes = int(env.get("ATLAS_INGEST_MAX_BYTES", 50 * 1024 * 1024))
    ing = LibraryIngest(reg, env["ATLAS_CONSUME_DIR"], env["ATLAS_STATE_DIR"], token, max_bytes)
    pl = WriteClient(env["ATLAS_PAPERLESS_URL"], secret("ATLAS_PAPERLESS_INGEST_TOKEN", env))
    host = check_bind(env.get("ATLAS_INGEST_HOST", "127.0.0.1"), env)
    srv = ThreadingHTTPServer((host, int(env.get("ATLAS_INGEST_PORT", "18091"))), make_handler(ing, token, pl, max_bytes))
    return srv, ing, token, pl


def main() -> None:
    srv, ing, token, pl = build_from_env()
    stop = threading.Event()
    threading.Thread(target=worker, args=(ing, token, pl, float(os.environ.get("ATLAS_RECONCILE_INTERVAL", "20")), stop),
                     daemon=True).start()
    try:
        srv.serve_forever()
    finally:
        stop.set()


if __name__ == "__main__":
    main()
