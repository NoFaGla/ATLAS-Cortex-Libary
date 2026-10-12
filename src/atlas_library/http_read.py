"""HTTP-Schnittstelle für library-read: strikt read-only (nur GET), Bearer-Token, Loopback-Bind per Default."""
from __future__ import annotations

import argparse
import hmac
import json
import os
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .assets import AssetStore
from .config import check_bind, secret
from .paperless import ReadClient
from .read import LibraryRead
from .registry import Registry

ROUTES = {
    "/v1/resolve": lambda lr, q: lr.resolve_atlas_ref(q["ref"]),
    "/v1/documents/search": lambda lr, q: lr.search_documents(q["q"], int(q.get("limit", 10))),
    "/v1/documents/metadata": lambda lr, q: lr.get_document_metadata(q["ref"]),
    "/v1/documents/text": lambda lr, q: lr.get_document_text(q["ref"], int(q.get("max_chars", 20000))),
    "/v1/documents/file": lambda lr, q: lr.get_document_file(q["ref"]),
    "/v1/assets": lambda lr, q: lr.get_asset(q["ref"]),
}
STATUS_HTTP = {"ok": 200, "invalid_ref": 400, "unknown": 404, "deleted": 410, "trashed": 410, "revision_mismatch": 409,
               "pending": 409, "unsupported": 422, "integrity_error": 502, "too_large": 413, "asset_error": 502,
               "revision_unavailable": 409}


def make_handler(lr: LibraryRead, token: str):
    tok = token.encode()

    class H(BaseHTTPRequestHandler):
        server_version = "atlas-library-read"
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):  # keine Query-Strings/Refs in Logs
            pass

        def _send(self, code: int, obj: dict):
            body = json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _authed(self) -> bool:
            h = self.headers.get("Authorization", "")
            return h.startswith("Bearer ") and hmac.compare_digest(h[7:].encode(), tok)

        def do_GET(self):
            if not self._authed():
                return self._send(401, {"status": "unauthorized"})
            u = urllib.parse.urlsplit(self.path)
            q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
            if u.path == "/healthz":
                return self._send(200, {"status": "ok"})
            fn = ROUTES.get(u.path)
            if fn is None:
                return self._send(404, {"status": "not_found"})
            try:
                out = fn(lr, q)
            except KeyError as exc:
                return self._send(400, {"status": "missing_parameter", "parameter": str(exc.args[0])})
            except ValueError:
                return self._send(400, {"status": "bad_parameter"})
            except Exception:  # Backend-Fehler ohne interne Details nach außen
                return self._send(502, {"status": "backend_error"})
            self._send(STATUS_HTTP.get(out.get("status"), 200 if out.get("status") == "ok" else 422), out)

        def _deny(self):
            self._send(405, {"status": "method_not_allowed", "note": "library-read ist read-only"})

        do_POST = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = _deny

    return H


def build_from_env(env=os.environ) -> tuple[ThreadingHTTPServer, LibraryRead]:
    reg = Registry(env["ATLAS_REGISTRY"])
    assets = AssetStore(env["ATLAS_ASSETS"], reg) if env.get("ATLAS_ASSETS") else None
    pl = ReadClient(env["ATLAS_PAPERLESS_URL"], secret("ATLAS_PAPERLESS_READ_TOKEN", env))
    lr = LibraryRead(reg, pl, assets)
    host = check_bind(env.get("ATLAS_READ_HOST", "127.0.0.1"), env)
    srv = ThreadingHTTPServer((host, int(env.get("ATLAS_READ_PORT", "18090"))), make_handler(lr, secret("ATLAS_READ_TOKEN", env)))
    return srv, lr


def main() -> None:
    argparse.ArgumentParser(prog="atlas-library-read-http", description=__doc__).parse_args()
    srv, _ = build_from_env()
    srv.serve_forever()


if __name__ == "__main__":
    main()
