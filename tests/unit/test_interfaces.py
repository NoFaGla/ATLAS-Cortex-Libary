"""HTTP-/MCP-Schnittstellen gegen lokalen Fake-Paperless (echte Paperless-Tests: tests/e2e)."""
import hashlib
import io
import json
import threading
import urllib.error
import urllib.request

import pytest

from atlas_library import http_ingest, http_read, mcp_read
from atlas_library.config import check_bind, secret
from atlas_library.ingest import LibraryIngest
from atlas_library.paperless import ReadClient, WriteClient
from atlas_library.read import LibraryRead
from atlas_library.registry import Registry
from tests.unit.test_core import FakePaperless

RT, IT = "r" * 32, "i" * 32


@pytest.fixture
def fake():
    f = FakePaperless(); yield f; f.close()


@pytest.fixture
def env(tmp_path, fake):
    reg = Registry(tmp_path / "r.sqlite3")
    sha = hashlib.sha256(fake.original[1]).hexdigest()
    aid = reg.create(kind="document", backend="paperless", backend_id="1", sha256=sha, title="x")
    lr = LibraryRead(reg, ReadClient(fake.url, "tok"), None)
    return reg, lr, aid, sha


def serve(handler):
    from http.server import ThreadingHTTPServer
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_port}"


def req(url, method="GET", token=None, data=None, headers=None):
    r = urllib.request.Request(url, data=data, method=method, headers={**({"Authorization": f"Bearer {token}"} if token else {}), **(headers or {})})
    try:
        with urllib.request.urlopen(r, timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_read_http_auth_methods_and_status_codes(env):
    reg, lr, aid, sha = env
    srv, base = serve(http_read.make_handler(lr, RT))
    try:
        assert req(f"{base}/v1/resolve?ref=x")[0] == 401
        assert req(f"{base}/v1/resolve?ref=x", token="wrong")[0] == 401
        assert req(f"{base}/v1/resolve?ref=garbage", token=RT)[0] == 400
        assert req(f"{base}/v1/resolve", token=RT)[0] == 400  # Parameter fehlt
        code, body = req(f"{base}/v1/resolve?ref=atlas-library://{aid}@sha256:{sha}", token=RT)
        assert code == 200 and body["status"] == "ok"
        assert req(f"{base}/v1/resolve?ref=atlas-library://{aid}@sha256:{'0' * 64}", token=RT)[0] == 409
        assert req(f"{base}/v1/documents/file?ref=atlas-library://{aid}", token=RT)[0] == 200
        for m in ("POST", "PUT", "PATCH", "DELETE"):
            assert req(f"{base}/v1/documents/file?ref=atlas-library://{aid}", method=m, token=RT, data=b"x" if m != "DELETE" else None)[0] == 405
        reg.set_status(aid, "trashed")
        assert req(f"{base}/v1/documents/text?ref=atlas-library://{aid}", token=RT)[0] == 410
    finally:
        srv.shutdown()


def test_bind_guard_and_secret_loading(tmp_path, monkeypatch):
    assert check_bind("127.0.0.1", {}) == "127.0.0.1" and check_bind("::1", {}) == "::1"
    for h in ("0.0.0.0", "192.168.1.5", "example.org"):
        with pytest.raises(SystemExit):
            check_bind(h, {})
    assert check_bind("0.0.0.0", {"ATLAS_ALLOW_NON_LOOPBACK": "1"}) == "0.0.0.0"
    f = tmp_path / "s"; f.write_text("abc\n")
    assert secret("X", {"X_FILE": str(f)}) == "abc"
    with pytest.raises(SystemExit):
        secret("X", {})


def test_ingest_http(tmp_path, fake):
    reg = Registry(tmp_path / "r.sqlite3")
    ing = LibraryIngest(reg, tmp_path / "consume", tmp_path / "state", IT, max_bytes=1000)
    srv, base = serve(http_ingest.make_handler(ing, IT, WriteClient(fake.url, "tok"), 1000))
    try:
        h = {"X-Filename": "a.pdf", "Content-Length": "5"}
        assert req(f"{base}/v1/ingest", "POST", data=b"hello", headers=h)[0] == 401
        code, body = req(f"{base}/v1/ingest", "POST", IT, b"hello", h)
        assert code == 200 and body["status"] == "queued"
        assert req(f"{base}/v1/ingest", "POST", IT, b"hello", h)[1]["status"] == "duplicate"
        assert req(f"{base}/v1/ingest", "POST", IT, b"x" * 1001, {"X-Filename": "a.pdf"})[0] == 413
        assert req(f"{base}/v1/ingest", "POST", IT, b"zz", {"X-Filename": "a.exe"})[0] == 422
        assert req(f"{base}/v1/ingest", "POST", IT, b"zz", {"X-Filename": "b.pdf", "X-Hints": "{"})[0] == 400
        bad = json.dumps([{"field": "document_type_new", "value": "x", "source": "user"}])
        assert req(f"{base}/v1/ingest", "POST", IT, b"zz", {"X-Filename": "b.pdf", "X-Hints": bad})[0] == 422
        for m in ("GET", "DELETE", "PUT"):
            assert req(f"{base}/v1/ingest", m, IT)[0] == 405
        assert len(list((tmp_path / "consume").iterdir())) == 1  # nichts überschrieben/gelöscht
    finally:
        srv.shutdown()


def mcp_call(lr, *msgs):
    out = io.StringIO()
    mcp_read.serve(lr, io.StringIO("\n".join(json.dumps(m) for m in msgs) + "\n"), out)
    return [json.loads(l) for l in out.getvalue().splitlines()]


def test_mcp_protocol_and_tools(env):
    reg, lr, aid, sha = env
    r = mcp_call(lr,
                 {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                 {"jsonrpc": "2.0", "method": "notifications/initialized"},
                 {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                 {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "resolve_atlas_ref", "arguments": {"ref": f"atlas-library://{aid}"}}},
                 {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "delete_document", "arguments": {}}},
                 {"jsonrpc": "2.0", "id": 5, "method": "nope"})
    assert [x["id"] for x in r] == [1, 2, 3, 4, 5]  # Notification ohne Antwort
    assert r[0]["result"]["capabilities"]["tools"] is not None
    tools = {t["name"]: t for t in r[1]["result"]["tools"]}
    assert set(tools) == set(mcp_read.TOOLS) and all(t["annotations"]["readOnlyHint"] for t in tools.values())
    assert not any(w in n for n in tools for w in ("delete", "write", "update", "merge", "create", "ingest"))
    assert json.loads(r[2]["result"]["content"][0]["text"])["status"] == "ok"
    assert r[3]["error"]["code"] == -32602 and r[4]["error"]["code"] == -32601


def test_mcp_parse_error(env):
    out = io.StringIO()
    mcp_read.serve(env[1], io.StringIO("{not json\n"), out)
    assert json.loads(out.getvalue())["error"]["code"] == -32700
