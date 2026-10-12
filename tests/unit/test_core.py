import hashlib
import json
import threading
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from atlas_library.assets import AssetError, AssetStore
from atlas_library.ingest import IngestError, LibraryIngest, merge_hints, sanitize_filename
from atlas_library.paperless import PaperlessError, ReadClient, WriteClient
from atlas_library.read import LibraryRead
from atlas_library.refs import InvalidRef, parse_ref
from atlas_library.registry import Registry
from atlas_library.uuid7 import is_uuid7, uuid7

H1 = hashlib.sha256(b"one").hexdigest()
H2 = hashlib.sha256(b"two").hexdigest()


@pytest.fixture
def reg(tmp_path):
    return Registry(tmp_path / "reg.sqlite3")


# ---- UUIDv7 -------------------------------------------------------------------------------
def test_uuid7_format_and_monotonic():
    ids = [uuid7() for _ in range(5000)]
    assert all(u.version == 7 and u.variant == uuid.RFC_4122 for u in ids)
    assert ids == sorted(ids) and len(set(ids)) == len(ids)
    assert is_uuid7(str(ids[0])) and not is_uuid7(str(uuid.uuid4())) and not is_uuid7("x")


# ---- Referenzen ---------------------------------------------------------------------------
def test_ref_parsing(reg):
    aid = str(uuid7())
    assert parse_ref(f"atlas-library://{aid}").sha256 is None
    assert str(parse_ref(f"atlas-library://{aid}@sha256:{H1}")) == f"atlas-library://{aid}@sha256:{H1}"
    for bad in ["", f"atlas-library://{uuid.uuid4()}", f"http://{aid}", f"atlas-library://{aid}@sha256:zz",
                f"atlas-library://{aid.upper()}", f"atlas-library://{aid}@sha256:{H1.upper()}"]:
        with pytest.raises(InvalidRef):
            parse_ref(bad)


# ---- Registry -----------------------------------------------------------------------------
def test_resolve_statuses(reg):
    aid = reg.create(kind="document", backend="paperless", backend_id="7", sha256=H1)
    assert reg.resolve(f"atlas-library://{aid}").status == "ok"
    assert reg.resolve(f"atlas-library://{aid}@sha256:{H1}").status == "ok"
    assert reg.resolve(f"atlas-library://{uuid7()}").status == "unknown"
    mm = reg.resolve(f"atlas-library://{aid}@sha256:{H2}")
    assert mm.status == "revision_mismatch" and mm.pinned_revision_known is False
    reg.set_status(aid, "trashed")
    assert reg.resolve(f"atlas-library://{aid}").status == "trashed"
    reg.set_status(aid, "active")
    reg.set_status(aid, "deleted")
    assert reg.resolve(f"atlas-library://{aid}").status == "deleted"
    with pytest.raises(ValueError):
        reg.set_status(aid, "active")  # Tombstone endgültig
    with pytest.raises(ValueError):
        reg.add_revision(aid, H2)
    assert reg.get(aid) is not None  # Eintrag bleibt -> ID nie wiederverwendbar


def test_revision_pinning(reg):
    aid = reg.create(kind="document", backend="paperless", backend_id="7", sha256=H1)
    old = reg.pin(aid)
    assert reg.add_revision(aid, H2) == 2
    assert reg.add_revision(aid, H2) == 2  # idempotent
    r = reg.resolve(old)
    assert r.status == "revision_mismatch" and r.pinned_revision_known is True and r.current_hash == H2
    assert reg.resolve(reg.pin(aid)).status == "ok"
    assert reg.revisions(aid) == [(1, H1), (2, H2)]


def test_registry_constraints(reg):
    reg.create(kind="document", backend="paperless", backend_id="7", sha256=H1)
    with pytest.raises(Exception):
        reg.create(kind="document", backend="paperless", backend_id="7", sha256=H2)  # Backend-ID eindeutig
    with pytest.raises(ValueError):
        reg.create(kind="asset", backend="paperless", sha256=H1)
    with pytest.raises(ValueError):
        reg.create(kind="document", backend="paperless", sha256="abc")
    with pytest.raises(ValueError):
        reg.create(kind="document", backend="paperless", sha256=H1, status="deleted")


# ---- Asset Store --------------------------------------------------------------------------
def test_asset_store(tmp_path, reg):
    root = tmp_path / "assets"; root.mkdir()
    (root / "logo.svg").write_bytes(b"<svg/>")
    store = AssetStore(root, reg)
    aid = store.register("logo.svg")
    p, mime = store.open_exact(aid)
    assert p.read_bytes() == b"<svg/>" and mime == "image/svg+xml"
    (root / "logo.svg").write_bytes(b"<svg>changed</svg>")
    with pytest.raises(AssetError, match="Integritätsfehler"):
        store.open_exact(aid)  # keine stille Ersetzung / Neugenerierung


def test_asset_path_confinement(tmp_path, reg):
    root = tmp_path / "assets"; root.mkdir()
    (tmp_path / "secret.txt").write_text("s")
    (root / "link").symlink_to(tmp_path / "secret.txt")
    store = AssetStore(root, reg)
    for bad in ["../secret.txt", "/etc/passwd", "link", "a/../../secret.txt", ""]:
        with pytest.raises(AssetError):
            store.register(bad)


# ---- Fake Paperless (lokaler HTTP-Server; KEIN echtes Paperless) ----------------------------------
class FakePaperless:
    def __init__(self):
        self.docs = {1: {"id": 1, "title": "Rechnung 2026-01", "content": "Synthetischer OCR-Text", "created": "2026-01-15",
                         "correspondent": None, "document_type": None, "tags": [], "custom_fields": [], "checksum": "m1"}}
        self.original = {1: b"%PDF-synthetic-1"}
        self.requests = []
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a): pass

            def _send(self, obj, raw=False):
                body = obj if raw else json.dumps(obj).encode()
                self.send_response(200); self.end_headers(); self.wfile.write(body)

            def do_GET(self):
                outer.requests.append(("GET", self.path))
                assert self.headers["Authorization"] == "Token tok"
                if self.path.split("/")[2] in ("tags", "correspondents", "document_types", "storage_paths"):
                    return self._send({"results": []})
                if self.path.startswith("/api/custom_fields"):
                    return self._send({"results": [{"id": 9, "name": "ATLAS-ID"}]})
                if "/download/" in self.path:
                    return self._send(outer.original[int(self.path.split("/")[3])], raw=True)
                if "checksum__iexact" in self.path:
                    c = self.path.split("=")[1]
                    return self._send({"results": [d for d in outer.docs.values() if d["checksum"] == c]})
                if self.path.startswith("/api/documents/?"):
                    return self._send({"results": list(outer.docs.values())})
                return self._send(outer.docs[int(self.path.split("/")[3])])

            def do_PATCH(self):
                outer.requests.append(("PATCH", self.path))
                n = int(self.headers["Content-Length"])
                outer.docs[int(self.path.split("/")[3])].update(json.loads(self.rfile.read(n)))
                self._send({})

        self.srv = HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.srv.server_port}"

    def close(self):
        self.srv.shutdown()


@pytest.fixture
def fake():
    f = FakePaperless(); yield f; f.close()


def test_library_read_is_get_only_and_integrity_checked(tmp_path, reg, fake):
    orig = fake.original[1]
    aid = reg.create(kind="document", backend="paperless", backend_id="1", sha256=hashlib.sha256(orig).hexdigest(),
                     title="Rechnung")
    lr = LibraryRead(reg, ReadClient(fake.url, "tok"), None)
    ref = reg.pin(aid)
    assert lr.get_document_metadata(ref)["paperless"]["title"] == "Rechnung 2026-01"
    assert lr.get_document_text(ref)["text"].startswith("Synthetisch")
    assert lr.get_document_file(ref)["status"] == "ok"
    s = lr.search_documents("rechnung")
    assert s["hits"][0]["atlas_id"] == aid
    assert {m for m, _ in fake.requests} == {"GET"}  # library-read schreibt nie
    fake.original[1] = b"tampered"
    assert lr.get_document_file(ref)["status"] == "integrity_error"
    assert lr.get_document_metadata("garbage")["status"] == "invalid_ref"
    reg.set_status(aid, "trashed")
    assert lr.get_document_text(ref)["status"] == "trashed"


def test_library_read_has_no_mutating_api():
    public = {n for n in dir(LibraryRead) if not n.startswith("_")}
    assert not any(w in n for n in public for w in ("delete", "merge", "update", "write", "edit", "remove", "create"))


def test_read_client_rejects_non_http():
    with pytest.raises(ValueError):
        ReadClient("file:///etc/passwd", "t")


# ---- Ingest -------------------------------------------------------------------------------
TOKEN = "t" * 32


@pytest.fixture
def ing(tmp_path, reg):
    return LibraryIngest(reg, tmp_path / "consume", tmp_path / "state", TOKEN, max_bytes=1000)


def test_ingest_auth_and_validation(ing):
    with pytest.raises(PermissionError):
        ing.ingest_document("wrong", "a.pdf", b"x")
    with pytest.raises(IngestError):
        ing.ingest_document(TOKEN, "a.exe", b"x")
    with pytest.raises(IngestError):
        ing.ingest_document(TOKEN, "a.pdf", b"x" * 1001)
    with pytest.raises(IngestError):
        ing.ingest_document(TOKEN, "a.pdf", b"")
    with pytest.raises(ValueError):
        LibraryIngest(Registry(":memory:"), "c", "s", "short")


def test_ingest_duplicate_not_deleted_not_rewritten(ing, tmp_path):
    r1 = ing.ingest_document(TOKEN, "Scan.pdf", b"%PDF-synthetic")
    assert r1["status"] == "queued"
    files = sorted(p.name for p in (tmp_path / "consume").iterdir())
    assert len(files) == 1 and files[0].startswith("Scan [")
    r2 = ing.ingest_document(TOKEN, "andere.pdf", b"%PDF-synthetic")
    assert r2["status"] == "duplicate" and r2["atlas_id"] == r1["atlas_id"] and r2["action"] == "none"
    assert sorted(p.name for p in (tmp_path / "consume").iterdir()) == files
    assert (tmp_path / "consume" / files[0]).read_bytes() == b"%PDF-synthetic"


@pytest.mark.parametrize("name,expected", [("../../etc/passwd.pdf", "passwd.pdf"), ("a\\b\\c.pdf", "c.pdf"),
                                           ("x:y*z?.pdf", "x_y_z_.pdf")])
def test_filename_sanitizing(name, expected):
    assert sanitize_filename(name) == expected


def test_filename_rejects_empty_and_strips_leading_dots():
    for bad in ["", "...", "/", "  "]:
        with pytest.raises(IngestError):
            sanitize_filename(bad)
    assert sanitize_filename(".hidden.pdf") == "hidden.pdf"


def test_hint_priority_and_no_free_taxonomy():
    m = merge_hints([{"field": "correspondent", "value": "LLM GmbH", "source": "llm"},
                     {"field": "correspondent", "value": "Extrahiert AG", "source": "extracted"},
                     {"field": "correspondent", "value": "Nutzer KG", "source": "user"},
                     {"field": "title", "value": "T", "source": "llm"}])
    assert m == {"correspondent": "Nutzer KG", "title": "T"}
    with pytest.raises(IngestError):
        merge_hints([{"field": "new_document_type", "value": "x", "source": "user"}])
    with pytest.raises(IngestError):
        merge_hints([{"field": "title", "value": "x", "source": "robot"}])


def test_reconcile_links_and_sets_atlas_id(ing, reg, fake):
    data = b"%PDF-synthetic-reconcile"
    r = ing.ingest_document(TOKEN, "r.pdf", data)
    assert reg.resolve(r["ref"]).status == "pending"
    wc = WriteClient(fake.url, "tok")
    assert ing.reconcile(TOKEN, wc)[0]["status"] == "waiting"  # Paperless hat es noch nicht
    fake.docs[2] = {"id": 2, "title": "r", "content": "", "custom_fields": [], "tags": [], "checksum": hashlib.sha256(data).hexdigest()}
    res = ing.reconcile(TOKEN, wc)
    assert res[0]["status"] == "linked"
    assert fake.docs[2]["custom_fields"] == [{"field": 9, "value": r["atlas_id"]}]
    assert "tag:Status/Unverarbeitet" in res[0]["unresolved"]  # Taxonomie fehlt im Fake -> nicht angelegt, nur gemeldet
    assert reg.resolve(r["ref"]).status == "ok" and reg.get(r["atlas_id"])["backend_id"] == "2"
    assert ing.reconcile(TOKEN, wc) == []  # idempotent


def test_write_client_never_overwrites_foreign_atlas_id(fake):
    fake.docs[1]["custom_fields"] = [{"field": 9, "value": "other"}]
    with pytest.raises(PaperlessError):
        WriteClient(fake.url, "tok").set_atlas_id(1, "mine")
