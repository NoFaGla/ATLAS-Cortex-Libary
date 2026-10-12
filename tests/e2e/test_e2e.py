"""E2E gegen eine ECHTE Paperless-ngx-Instanz (isolierter Teststack, nur synthetische Daten).

Start über tests/integration/run-e2e.sh. Ohne ATLAS_E2E_URL werden alle Tests übersprungen (nicht PASS!).
"""
import base64
import hashlib
import json
import os
import subprocess
import sys
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from atlas_library import http_ingest, http_read
from atlas_library.assets import AssetStore
from atlas_library.ingest import LibraryIngest
from atlas_library.paperless import PaperlessError, ReadClient, WriteClient
from atlas_library.read import LibraryRead
from atlas_library.registry import Registry
from atlas_library.synthetic import write_all
from atlas_library.taxonomy import AdminClient, apply_taxonomy
from tests.unit.test_interfaces import req

URL = os.environ.get("ATLAS_E2E_URL")
pytestmark = pytest.mark.skipif(not URL, reason="ATLAS_E2E_URL nicht gesetzt (kein Paperless-Teststack)")
ADMIN_TOKEN = os.environ.get("ATLAS_E2E_TOKEN", "")
CONSUME = Path(os.environ.get("ATLAS_E2E_CONSUME", "/nonexistent"))
REPORT = os.environ.get("ATLAS_E2E_REPORT")
ING_TOKEN, READ_TOKEN = "i" * 40, "r" * 40
OBS: dict = {}  # Beobachtungen für den Testbericht

TITLES = {"T01": "Verdienstabrechnung 2026-01", "T02": "Verdienstabrechnung 2026-02", "T03": "Dienstleistungsvertrag",
          "T04": "Mietvertrag", "T05": "Betriebskostenabrechnung 2025", "T06": "Steuerbescheid 2026",
          "T07": "Arbeitszeugnis", "T08": "Urkunde", "T09": "Quittung Baumarkt", "T10": "Prüfbericht Müller & Söhne / Größe: Test?",
          "T12": "Verdienstabrechnung 2026-01", "T13": "Dienstleistungsvertrag Nachtrag", "T14": "Gesprächsnotiz Zaunhöhe"}
NO_DATE_HINT = {"T02"}  # Paperless-Auto-Datum beobachten


def hints_for(m):
    h = []
    def add(f, v):
        if v is not None:
            h.append({"field": f, "value": v, "source": "user"})
    add("title", TITLES.get(m["id"]))
    if m["id"] not in NO_DATE_HINT and m.get("date"):
        d = m["date"]
        add("created", d if len(d) == 10 else d + "-01")
        add("date_precision", m["precision"])
    add("correspondent", m.get("correspondent"))
    add("document_type", m.get("doctype"))
    if m.get("tags"):
        add("tags", m["tags"])
    return h


def wait(cond, timeout=240, step=3):
    end = time.time() + timeout
    while time.time() < end:
        r = cond()
        if r:
            return r
        time.sleep(step)
    return None


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("e2e")
    manifest = write_all(tmp / "synth")
    admin = AdminClient(URL, ADMIN_TOKEN)
    rep1 = apply_taxonomy(admin)
    rep2 = apply_taxonomy(admin)
    OBS["taxonomy_first_created"], OBS["taxonomy_second_created"] = len(rep1["created"]), len(rep2["created"])
    for name in sorted({m["correspondent"] for m in manifest.values() if m.get("correspondent")}):
        admin.post("/api/correspondents/", {"name": name, "matching_algorithm": 0})
    # Service-Benutzer mit minimalen Rechten
    def mkuser(name, perms):
        admin.post("/api/users/", {"username": name, "password": "Pw-" + "x" * 24, "user_permissions": perms})
        raw, _ = admin._request("POST", "/api/token/", {"username": name, "password": "Pw-" + "x" * 24})
        return json.loads(raw)["token"]
    view = ["view_document", "view_tag", "view_correspondent", "view_documenttype", "view_customfield", "view_storagepath"]
    read_tok = mkuser("library-read", view)
    ingest_tok = mkuser("library-ingest", view + ["change_document", "add_document"])
    reg = Registry(tmp / "registry.sqlite3")
    (tmp / "consume").mkdir()
    ing = LibraryIngest(reg, CONSUME, tmp / "state", ING_TOKEN, consume_owner=(1000, 1000))
    wc = WriteClient(URL, ingest_tok)
    ids = {}
    for tid in ["T01", "T02", "T03", "T04", "T05", "T06", "T07", "T08", "T09", "T10", "T11", "T12", "T13"]:
        m = manifest[tid]
        f = tmp / "synth" / m["file"]
        out = ing.ingest_document(ING_TOKEN, f.name, f.read_bytes(), hints_for(m))
        ids[tid] = out
    assets_dir = tmp / "synth" / "assets"
    assets = AssetStore(assets_dir, reg)
    asset_ids = {rel: assets.register(rel) for rel in ["logos/muster-logo.svg", "icons/icon.png", "templates/vorlage-brief.txt"]}

    def all_linked():
        ing.reconcile(ING_TOKEN, wc)
        pend = [i["atlas_id"] for i in ids.values() if i["status"] == "queued" and reg.get(i["atlas_id"])["status"] != "active"]
        return not pend
    assert wait(all_linked), "Dokumente wurden nicht rechtzeitig von Paperless konsumiert/zugeordnet"
    return dict(tmp=tmp, manifest=manifest, admin=admin, reg=reg, ing=ing, wc=wc, ids=ids, assets=assets, asset_ids=asset_ids,
                read_tok=read_tok, ingest_tok=ingest_tok)


def doc_of(w, tid):
    aid = w["ids"][tid]["atlas_id"]
    e = w["reg"].get(aid)
    return aid, w["admin"].get_document(e["backend_id"]), w["admin"].get_metadata(e["backend_id"])


def test_taxonomy_idempotent(world):
    assert OBS["taxonomy_first_created"] >= 34 and OBS["taxonomy_second_created"] == 0
    names = {t["name"] for t in world["admin"].list_all("/api/tags/")}
    assert {"Status/Unverarbeitet", "Status/Prüfen", "Status/Verarbeitet", "Thema/Steuern"} <= names
    types = {t["name"] for t in world["admin"].list_all("/api/document_types/")}
    assert len(types) == 9
    # kein automatisches Matching -> keine stille Zuordnung durch Paperless
    assert all(t["matching_algorithm"] == 0 for t in world["admin"].list_all("/api/document_types/"))


def test_atlas_id_on_every_document_and_registry_mapping(world):
    for tid, out in world["ids"].items():
        if out["status"] != "queued":
            continue
        aid, doc, _ = doc_of(world, tid)
        fid = next(f["id"] for f in world["admin"].list_all("/api/custom_fields/") if f["name"] == "ATLAS-ID")
        assert [f["value"] for f in doc["custom_fields"] if f["field"] == fid] == [aid]
        assert "Status/Unverarbeitet" in {t["name"] for t in world["admin"].list_all("/api/tags/") if t["id"] in doc["tags"]}
    assert world["ids"]["T01"]["atlas_id"] != world["ids"]["T12"]["atlas_id"]


def test_ocr_quality_german(world):
    _, d9, _ = doc_of(world, "T09")
    _, d10, _ = doc_of(world, "T10")
    _, d12, _ = doc_of(world, "T12")
    assert "Quittung" in d9["content"]
    for needle in ("Größenänderung", "Seite 6 von 6", "Äpfel", "Fuß"):
        assert needle in d10["content"], needle
    assert "Verdienstabrechnung Januar 2026" in d12["content"]  # zweiter Scan (Bild) -> OCR
    OBS["ocr_bad_scan_chars"] = len(d9["content"])
    OBS["ocr_bad_scan_text"] = d9["content"][:200]


def test_original_unchanged(world):
    for tid in ("T01", "T03", "T09", "T10", "T12"):
        f = world["tmp"] / "synth" / world["manifest"][tid]["file"]
        data = WriteClient(URL, ADMIN_TOKEN).download_original(world["reg"].get(world["ids"][tid]["atlas_id"])["backend_id"])
        assert hashlib.sha256(data).hexdigest() == hashlib.sha256(f.read_bytes()).hexdigest(), tid


def test_dates_precision_and_filenames(world):
    expect = {  # tid -> Anfang des Dateinamens
        "T01": "2026-01-31 - Muster Arbeitgeber GmbH - Abrechnung - Verdienstabrechnung 2026-01",
        "T05": "2026-03 - Beispiel Wohnbau GmbH - Abrechnung - Betriebskostenabrechnung 2025",   # Monat: kein erfundener Tag
        "T07": "2023-06 - Muster Arbeitgeber GmbH - Zeugnis - Arbeitszeugnis",
        "T14": "2025-09-03 - Gartenverein Beispielstadt - ohne Typ - Gesprächsnotiz Zaunhöhe",   # Typ fehlt -> Platzhalter
    }
    for tid, start in expect.items():
        if tid == "T14":
            continue  # T14 wird erst in test_ingest_http_real_paperless angelegt
        _, doc, meta = doc_of(world, tid)
        assert meta["media_filename"].startswith(start), (tid, meta["media_filename"])
        assert "/" not in meta["media_filename"]
    _, d5, _ = doc_of(world, "T05")
    assert d5["created"] == "2026-03-01"  # technisch erster Tag, Präzision steht im Feld + Dateiname
    # Sonderzeichen: '/' im Titel erzeugt kein Unterverzeichnis
    _, _, m10 = doc_of(world, "T10")
    assert "/" not in m10["media_filename"] and "Müller & Söhne - Größe" in m10["media_filename"], m10["media_filename"]
    # Sortierbarkeit: lexikographisch == chronologisch
    names = []
    for tid in ("T04", "T07", "T01", "T05", "T06", "T09"):
        _, d, m = doc_of(world, tid)
        names.append((d["created"], m["media_filename"]))
    assert [n for _, n in sorted(names)] == sorted(n for _, n in names)
    # keine Überschreibung: T01 und T12 haben identische Metadaten/Titel -> eigene Dateien
    _, _, m1 = doc_of(world, "T01")
    _, _, m12 = doc_of(world, "T12")
    assert m1["media_filename"] != m12["media_filename"]
    OBS["filename_collision_example"] = [m1["media_filename"], m12["media_filename"]]


def test_paperless_auto_date_without_hint(world):
    _, d2, _ = doc_of(world, "T02")
    OBS["auto_date_T02"] = d2["created"]
    OBS["auto_date_T02_text_contains"] = ["Februar 2026", "28.02.2026"]
    assert d2["created"] in ("2026-02-01", "2026-02-28")  # dokumentiert: Paperless rät; ATLAS überschreibt per Hinweis


def test_duplicates(world):
    assert world["ids"]["T11"]["status"] == "duplicate" and world["ids"]["T11"]["atlas_id"] == world["ids"]["T01"]["atlas_id"]
    assert world["ids"]["T12"]["status"] == "queued"  # semantisches Duplikat: eigene ID, Mensch entscheidet
    # Paperless-Eigenschutz: direkt konsumiertes bit-identisches Duplikat wird markiert, aber nicht gelöscht
    before = len(world["admin"].list_all("/api/documents/"))
    dup = CONSUME / "direct-duplicate.pdf"
    dup.write_bytes((world["tmp"] / "synth" / world["manifest"]["T11"]["file"]).read_bytes())
    os.chown(dup, 1000, 1000)
    assert wait(lambda: len(world["admin"].list_all("/api/documents/")) == before + 1, 120)
    d1 = world["admin"].get_document(world["reg"].get(world["ids"]["T01"]["atlas_id"])["backend_id"])
    newest = max(world["admin"].list_all("/api/documents/"), key=lambda d: d["id"])
    assert any(x["id"] == d1["id"] for x in world["admin"].get_document(newest["id"])["duplicate_documents"])
    assert world["admin"].get_document(d1["id"])["deleted_at"] is None  # nichts gelöscht
    OBS["direct_duplicate"] = "von Paperless als duplicate_documents markiert, beide Dokumente bleiben"


def test_versions_and_pinned_refs(world):
    reg, ing, wc = world["reg"], world["ing"], world["wc"]
    aid = world["ids"]["T03"]["atlas_id"]
    old_ref = reg.pin(aid)
    v2 = (world["tmp"] / "synth" / world["manifest"]["T13b"]["file"]).read_bytes()
    out = ing.ingest_revision(ING_TOKEN, aid, wc, "T03_v2.pdf", v2, "technische Fassung")
    assert out["status"] == "revision_added" and out["revision"] == 2
    assert world["ids"]["T13"]["atlas_id"] != aid  # fachlich neu = neue ID
    lr = LibraryRead(reg, ReadClient(URL, world["read_tok"]), world["assets"])
    new_file = lr.get_document_file(out["ref"])
    old_file = lr.get_document_file(old_ref)
    v1 = (world["tmp"] / "synth" / world["manifest"]["T03"]["file"]).read_bytes()
    assert new_file["status"] == "ok" and new_file["is_current_revision"] and base64.b64decode(new_file["content_base64"]) == v2
    assert old_file["status"] == "ok" and not old_file["is_current_revision"] and base64.b64decode(old_file["content_base64"]) == v1
    assert lr.resolve_atlas_ref(old_ref)["status"] == "revision_mismatch"
    assert reg.revisions(aid)[0][1] == hashlib.sha256(v1).hexdigest()


def test_library_read_least_privilege_against_real_paperless(world):
    rc = ReadClient(URL, world["read_tok"])
    assert rc.search("Verdienstabrechnung")  # Lesen geht
    with pytest.raises(PaperlessError, match="403"):
        rc._request("PATCH", "/api/documents/1/", {"title": "x"})  # Schreiben nicht
    with pytest.raises(PaperlessError):
        rc._request("DELETE", "/api/documents/1/")
    with pytest.raises(PaperlessError):
        rc._request("POST", "/api/documents/post_document/", {})


def test_library_read_http_real(world):
    reg = world["reg"]
    lr = LibraryRead(reg, ReadClient(URL, world["read_tok"]), world["assets"])
    srv = ThreadingHTTPServer(("127.0.0.1", 0), http_read.make_handler(lr, READ_TOKEN))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_port}"
    try:
        aid = world["ids"]["T06"]["atlas_id"]
        ref = reg.pin(aid)
        assert req(f"{base}/v1/documents/metadata?ref={ref}")[0] == 401
        c, meta = req(f"{base}/v1/documents/metadata?ref={ref}", token=READ_TOKEN)
        assert c == 200 and meta["paperless"]["title"] == "Steuerbescheid 2026" and "AZ-2026-0042" not in json.dumps(meta)
        c, txt = req(f"{base}/v1/documents/text?ref={ref}", token=READ_TOKEN)
        assert c == 200 and "AZ-2026-0042" in txt["text"]
        c, f = req(f"{base}/v1/documents/file?ref={ref}", token=READ_TOKEN)
        assert c == 200 and hashlib.sha256(base64.b64decode(f["content_base64"])).hexdigest() == reg.get(aid)["current_hash"]
        c, s = req(f"{base}/v1/documents/search?q=Verdienstabrechnung", token=READ_TOKEN)
        assert c == 200 and s["count"] >= 2 and s["ambiguous"] and all(h["atlas_id"] for h in s["hits"][:2])
        assert req(f"{base}/v1/documents/file?ref={ref}", "DELETE", READ_TOKEN)[0] == 405
        # Assets: exakt, hash-geprüft
        a = world["asset_ids"]["logos/muster-logo.svg"]
        c, asset = req(f"{base}/v1/assets?ref={reg.pin(a)}", token=READ_TOKEN)
        assert c == 200 and base64.b64decode(asset["content_base64"]).startswith(b"<svg")
        assert req(f"{base}/v1/assets?ref={reg.pin(world['asset_ids']['icons/icon.png'])}", token=READ_TOKEN)[1]["mime_type"] == "image/png"
        assert req(f"{base}/v1/assets?ref={reg.pin(world['asset_ids']['templates/vorlage-brief.txt'])}", token=READ_TOKEN)[0] == 200
    finally:
        srv.shutdown()


def test_mcp_stdio_real(world):
    reg = world["reg"]
    aid = world["ids"]["T06"]["atlas_id"]
    env = {**os.environ, "ATLAS_REGISTRY": reg.path, "ATLAS_PAPERLESS_URL": URL, "ATLAS_PAPERLESS_READ_TOKEN": world["read_tok"],
           "ATLAS_ASSETS": str(world["tmp"] / "synth" / "assets")}
    msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
             "params": {"name": "get_document_text", "arguments": {"ref": f"atlas-library://{aid}"}}}]
    p = subprocess.run([sys.executable, "-m", "atlas_library.mcp_read"], input="\n".join(map(json.dumps, msgs)) + "\n",
                       capture_output=True, text=True, env=env, timeout=60)
    out = [json.loads(l) for l in p.stdout.splitlines()]
    assert out[0]["result"]["serverInfo"]["name"] == "atlas-library-read"
    assert "AZ-2026-0042" in json.loads(out[1]["result"]["content"][0]["text"])["text"]


def test_ingest_http_real_paperless(world):
    reg, ing, wc = world["reg"], world["ing"], world["wc"]
    m = world["manifest"]["T14"]
    data = (world["tmp"] / "synth" / m["file"]).read_bytes()
    srv = ThreadingHTTPServer(("127.0.0.1", 0), http_ingest.make_handler(ing, ING_TOKEN, wc, 50 * 1024 * 1024))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_port}"
    try:
        c, out = req(f"{base}/v1/ingest", "POST", ING_TOKEN, data, {"X-Filename": m["file"], "X-Hints": json.dumps(hints_for({**m, "id": "T14"}))})
        assert c == 200 and out["status"] == "queued"
        assert req(f"{base}/v1/ingest", "POST", ING_TOKEN, data, {"X-Filename": "again.pdf"})[1]["status"] == "duplicate"
        assert wait(lambda: ing.reconcile(ING_TOKEN, wc) is not None and reg.get(out["atlas_id"])["status"] == "active", 180)
        e = reg.get(out["atlas_id"])
        _, meta = None, world["admin"].get_metadata(e["backend_id"])
        assert meta["media_filename"].startswith("2025-09-03 - Gartenverein Beispielstadt - ohne Typ - Gesprächsnotiz Zaunhöhe")
        world["ids"]["T14"] = out
    finally:
        srv.shutdown()


def test_unknown_taxonomy_is_not_created_but_flagged(world):
    reg, ing, wc, admin = world["reg"], world["ing"], world["wc"], world["admin"]
    data = b"%PDF-1.4\n% synthetic unique unknown-taxonomy doc\n"  # kein gültiges PDF -> als TXT ablegen
    data = "Notiz Unbekannt synthetisch eindeutig 4711\n".encode()
    out = ing.ingest_document(ING_TOKEN, "unbekannt.txt", data, [
        {"field": "document_type", "value": "Frei Erfundener Typ", "source": "llm"},
        {"field": "title", "value": "Unbekannte Taxonomie", "source": "user"}])
    assert wait(lambda: ing.reconcile(ING_TOKEN, wc) is not None and reg.get(out["atlas_id"])["status"] == "active", 180)
    assert "Frei Erfundener Typ" not in {t["name"] for t in admin.list_all("/api/document_types/")}  # kein Wildwuchs
    doc = admin.get_document(reg.get(out["atlas_id"])["backend_id"])
    tags = {t["name"] for t in admin.list_all("/api/tags/") if t["id"] in doc["tags"]}
    assert "Status/Prüfen" in tags and doc["document_type"] is None


def test_no_overwrite_on_name_collision(world):
    """Zwei verschiedene Dokumente mit identischen Metadaten (gleicher Dateiname) dürfen sich nicht überschreiben."""
    reg, ing, wc, admin = world["reg"], world["ing"], world["wc"], world["admin"]
    hints = [{"field": "title", "value": "Kollision", "source": "user"}, {"field": "created", "value": "2026-04-01", "source": "user"},
             {"field": "date_precision", "value": "Tag", "source": "user"}, {"field": "correspondent", "value": "Beispiel Wohnbau GmbH", "source": "user"},
             {"field": "document_type", "value": "Rechnung", "source": "user"}]
    outs = [ing.ingest_document(ING_TOKEN, f"kollision{i}.txt", f"Kollisionstest synthetisch Inhalt {i}\n".encode(), hints) for i in (1, 2)]
    assert all(o["status"] == "queued" for o in outs)
    assert wait(lambda: ing.reconcile(ING_TOKEN, wc) is not None and all(reg.get(o["atlas_id"])["status"] == "active" for o in outs), 180)
    names = [admin.get_metadata(reg.get(o["atlas_id"])["backend_id"])["media_filename"] for o in outs]
    assert names[0] != names[1] and all(n.startswith("2026-04-01 - Beispiel Wohnbau GmbH - Rechnung - Kollision") for n in names), names
    for o in outs:
        data = wc.download_original(reg.get(o["atlas_id"])["backend_id"])
        assert hashlib.sha256(data).hexdigest() == reg.get(o["atlas_id"])["current_hash"]
    OBS["name_collision_files"] = names


def test_edge_year_precision_unicode_name_and_corrupt_file(world):
    """Grenzfälle: Jahresgenauigkeit im Dateinamen, Unicode-/Sonderzeichen-Dateiname, nicht verarbeitbare Datei (stale, nie gelöscht)."""
    reg, ing, wc, admin = world["reg"], world["ing"], world["wc"], world["admin"]
    jahr = ing.ingest_document(ING_TOKEN, "Ärger mit ß & Co (final) #1.txt", "Jahresbericht synthetisch 2024 eindeutig 8812\n".encode(), [
        {"field": "title", "value": "Jahresbericht 2024", "source": "user"}, {"field": "created", "value": "2024-01-01", "source": "user"},
        {"field": "date_precision", "value": "Jahr", "source": "user"}, {"field": "correspondent", "value": "Beispiel Wohnbau GmbH", "source": "user"},
        {"field": "document_type", "value": "Sonstiges Dokument", "source": "user"}])
    kaputt = ing.ingest_document(ING_TOKEN, "kaputt.pdf", b"%PDF-1.4 this is definitely not a valid pdf \x00\x01\x02 4711")
    assert wait(lambda: ing.reconcile(ING_TOKEN, wc) is not None and reg.get(jahr["atlas_id"])["status"] == "active", 180)
    name = admin.get_metadata(reg.get(jahr["atlas_id"])["backend_id"])["media_filename"]
    assert name.startswith("2024 - Beispiel Wohnbau GmbH - Sonstiges Dokument - Jahresbericht 2024"), name  # nur Jahr, kein erfundener Monat/Tag
    time.sleep(20)
    res = {r["atlas_id"]: r["status"] for r in ing.reconcile(ING_TOKEN, wc, stale_after_s=5)}
    assert res.get(kaputt["atlas_id"]) == "stale", res
    assert reg.get(kaputt["atlas_id"])["status"] == "pending"  # weder gelöscht noch aktiviert
    OBS["edge_year_filename"] = name


def test_trash_and_tombstone_lifecycle(world):
    reg, ing, wc, admin = world["reg"], world["ing"], world["wc"], world["admin"]
    aid = world["ids"]["T08"]["atlas_id"]
    ref = reg.pin(aid)
    pid = reg.get(aid)["backend_id"]
    admin._request("DELETE", f"/api/documents/{pid}/")  # menschliche Aktion in Paperless (Soft Delete -> Papierkorb)
    assert ing.sync_lifecycle(ING_TOKEN, wc) == [{"atlas_id": aid, "from": "active", "to": "trashed"}]
    lr = LibraryRead(reg, ReadClient(URL, world["read_tok"]), None)
    assert lr.resolve_atlas_ref(ref)["status"] == "trashed" and lr.get_document_file(ref)["status"] == "trashed"
    admin._request("POST", "/api/trash/", {"action": "empty", "documents": [int(pid)]})  # endgültig (menschlich)
    assert wait(lambda: ing.sync_lifecycle(ING_TOKEN, wc) or reg.get(aid)["status"] == "deleted", 60, 2)
    assert lr.resolve_atlas_ref(ref)["status"] == "deleted"
    with pytest.raises(ValueError):
        reg.set_status(aid, "active")
    assert reg.get(aid) is not None  # Tombstone bleibt


def test_write_report(world):
    if REPORT:
        Path(REPORT).write_text(json.dumps(OBS, indent=2, ensure_ascii=False, sort_keys=True))
