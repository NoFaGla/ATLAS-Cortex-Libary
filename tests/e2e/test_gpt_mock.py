"""Paperless-GPT v0.29.0 (echtes Image) gegen einen lokalen Mock-LLM (OpenAI-kompatibel) und echtes Paperless.

Prüft Metadatenextraktion (Titel, Datum, Korrespondent, Dokumenttyp, Tags), Vorrang von Nutzerhinweisen, Fehlerbehandlung
(ungültige Antworten, HTTP-Fehler, Timeout, nicht erreichbarer Endpunkt) und Erholung. Ein ECHTER LLM ist hier nicht beteiligt.
Start über tests/integration/run-gpt-mock.sh.
"""
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

import pytest

from atlas_library.ingest import LibraryIngest
from atlas_library.paperless import WriteClient
from atlas_library.registry import Registry
from atlas_library.synthetic import write_all
from atlas_library.taxonomy import DOCUMENT_TYPES, TAGS, AdminClient, apply_taxonomy

URL = os.environ.get("ATLAS_E2E_URL")
pytestmark = pytest.mark.skipif(not URL, reason="ATLAS_E2E_URL nicht gesetzt")
TOKEN = os.environ.get("ATLAS_E2E_TOKEN", "")
CONSUME = Path(os.environ.get("ATLAS_E2E_CONSUME", "/nonexistent"))
COMPOSE = os.environ.get("ATLAS_E2E_COMPOSE", "")
REPORT = os.environ.get("ATLAS_E2E_REPORT")
ING = "i" * 40
OBS: dict = {}
QUEUE, DONE, FAILED = "System/Paperless-GPT-Queue", "System/Paperless-GPT-Done", "System/Paperless-GPT-Failed"


def sh(*cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=kw.pop("timeout", 120), cwd=kw.pop("cwd", None), **kw)


def mock_mode(mode):
    r = sh("docker", "exec", "m03-ci-mockllm", "python3", "-c",
           "import sys,json,urllib.request;urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8000/_mode',data=json.dumps({'mode':sys.argv[1]}).encode(),method='POST'),timeout=5)", mode)
    assert r.returncode == 0, r.stderr


def mock_stats():
    r = sh("docker", "exec", "m03-ci-mockllm", "python3", "-c", "import urllib.request;print(urllib.request.urlopen('http://127.0.0.1:8000/_stats',timeout=5).read().decode())")
    return json.loads(r.stdout)


def wait(cond, timeout=240, step=3):
    end = time.time() + timeout
    while time.time() < end:
        r = cond()
        if r:
            return r
        time.sleep(step)
    return None


@pytest.fixture(scope="module")
def w(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("gptmock")
    manifest = write_all(tmp / "synth")
    admin = AdminClient(URL, TOKEN)
    apply_taxonomy(admin)
    for name in ("Beispiel Wohnbau GmbH",):
        admin.post("/api/correspondents/", {"name": name, "matching_algorithm": 0})
    reg = Registry(tmp / "reg.sqlite3")
    ing = LibraryIngest(reg, CONSUME, tmp / "state", ING, consume_owner=(1000, 1000))
    wc = WriteClient(URL, TOKEN)
    types_before = {t["name"] for t in admin.list_all("/api/document_types/")}
    tags_before = {t["name"] for t in admin.list_all("/api/tags/")}
    return dict(tmp=tmp, manifest=manifest, admin=admin, reg=reg, ing=ing, wc=wc, types_before=types_before, tags_before=tags_before)


def ingest(w, tid, hints=()):
    m = w["manifest"][tid]
    data = (w["tmp"] / "synth" / m["file"]).read_bytes()
    out = w["ing"].ingest_document(ING, m["file"], data, list(hints))
    assert out["status"] == "queued", out
    return out["atlas_id"], hashlib.sha256(data).hexdigest()


def link(w, aids, queue=True, timeout=240):
    def done():
        w["ing"].reconcile(ING, w["wc"], queue_for_gpt=queue)
        return all(w["reg"].get(a)["status"] == "active" for a in aids)
    assert wait(done, timeout), "Paperless hat die Dokumente nicht konsumiert"


def state(w, aid):
    d = w["admin"].get_document(w["reg"].get(aid)["backend_id"])
    corr = {c["id"]: c["name"] for c in w["admin"].list_all("/api/correspondents/")}
    typ = {c["id"]: c["name"] for c in w["admin"].list_all("/api/document_types/")}
    return {"title": d["title"], "created": d["created"], "correspondent": corr.get(d["correspondent"]), "type": typ.get(d["document_type"]),
            "tags": w["wc"].tag_names(d), "fields": d["custom_fields"], "id": d["id"]}


def settle(w, aids, timeout=300):
    """reconcile + finalize bis alle Dokumente Done oder Failed sind und finalisiert wurden."""
    def ok():
        w["ing"].reconcile(ING, w["wc"], queue_for_gpt=True)
        w["ing"].finalize(ING, w["wc"])
        return all(json.loads((w["tmp"] / "state" / "hints" / f"{a}.json").read_text()).get("finalized") for a in aids)
    return wait(ok, timeout, 4)


def h(field, value):
    return {"field": field, "value": value, "source": "user"}


def assert_taxonomy_intact(w):
    assert {t["name"] for t in w["admin"].list_all("/api/document_types/")} == w["types_before"]  # kein Typ-Wildwuchs
    assert {t["name"] for t in w["admin"].list_all("/api/tags/")} == w["tags_before"]  # keine neuen Tags


def test_happy_path_metadata_and_user_priority(w):
    mock_mode("ok")
    a1, s1 = ingest(w, "T01", [h("correspondent", "Beispiel Wohnbau GmbH"), h("created", "2026-01-31"), h("date_precision", "Tag")])
    a2, s2 = ingest(w, "T02")
    a3, s3 = ingest(w, "T05", [h("title", "Betriebskostenabrechnung 2025"), h("created", "2026-03-01"), h("date_precision", "Monat"), h("tags", ["Kontext/Wohnen"])])
    link(w, [a1, a2, a3])
    assert settle(w, [a1, a2, a3]), "GPT-Verarbeitung/Finalisierung nicht abgeschlossen"
    s_1, s_2, s_3 = state(w, a1), state(w, a2), state(w, a3)
    OBS["happy_T01"], OBS["happy_T02"], OBS["happy_T05"] = ({k: (sorted(v) if isinstance(v, set) else v) for k, v in s.items() if k != "fields"} for s in (s_1, s_2, s_3))
    # Metadaten aus dem LLM
    assert s_2["title"] == "Verdienstabrechnung Februar 2026" and s_2["created"] == "2026-02-28"  # korrigiert das Paperless-Raten (2026-02-01)
    assert s_2["correspondent"] == "Muster Arbeitgeber GmbH" and "Thema/Finanzen" in s_2["tags"]
    assert s_1["title"] == "Verdienstabrechnung Januar 2026"
    # Vorrang expliziter Nutzerangaben vor dem LLM
    assert s_1["correspondent"] == "Beispiel Wohnbau GmbH" and s_1["created"] == "2026-01-31"
    assert s_3["title"] == "Betriebskostenabrechnung 2025" and "Kontext/Wohnen" in s_3["tags"]
    assert w["admin"].get_metadata(w["reg"].get(a3)["backend_id"])["media_filename"].startswith("2026-03 - ")  # Monatsgenauigkeit bleibt
    # Dokumenttyp: nie automatisch (AUTO_GENERATE_DOCUMENT_TYPE=false)
    assert s_2["type"] is None and mock_stats()["by_kind"].get("document_type", 0) == 0
    # Lifecycle-Tags, Queue entfernt, ATLAS-ID erhalten
    for s, a in ((s_1, a1), (s_2, a2), (s_3, a3)):
        assert DONE in s["tags"] and QUEUE not in s["tags"]
        assert "Status/Verarbeitet" in s["tags"] and "Status/Unverarbeitet" not in s["tags"]
        assert a in [str(f["value"]) for f in s["fields"]]
    # Originale unverändert
    for a, sha in ((a1, s1), (a2, s2), (a3, s3)):
        assert hashlib.sha256(w["wc"].download_original(w["reg"].get(a)["backend_id"])).hexdigest() == sha
    assert_taxonomy_intact_except_correspondents(w)


def assert_taxonomy_intact_except_correspondents(w):
    assert_taxonomy_intact(w)


def test_invented_values_are_contained(w):
    mock_mode("invented")
    a, sha = ingest(w, "T04")
    link(w, [a])
    assert settle(w, [a])
    s = state(w, a)
    OBS["invented"] = {"title": s["title"][:60], "title_len": len(s["title"]), "created": s["created"], "tags": sorted(s["tags"]), "type": s["type"]}
    assert_taxonomy_intact(w)  # erfundene Tags/Dokumenttypen werden nicht angelegt
    assert s["type"] is None
    assert s["created"] and len(s["created"]) == 10 and s["created"][4] == "-"  # gültiges Datum, kein 'not-a-date'
    assert len(s["title"]) <= 128
    assert ("Status/Verarbeitet" in s["tags"]) != ("Status/Prüfen" in s["tags"])  # genau ein Endstatus
    assert hashlib.sha256(w["wc"].download_original(s["id"])).hexdigest() == sha


@pytest.mark.parametrize("mode", ["http500", "http429", "invalid_json", "empty", "truncated"])
def test_llm_failure_modes_end_in_failed_not_in_a_loop(w, mode):
    mock_mode(mode)
    tid = {"http500": "T06", "http429": "T07", "invalid_json": "T08", "empty": "T14", "truncated": "T03"}[mode]
    a, sha = ingest(w, tid)
    link(w, [a])
    before_title = state(w, a)["title"]
    assert settle(w, [a], 420), f"{mode}: kein Endzustand (Endlosschleife?)"
    s = state(w, a)
    OBS[f"mode_{mode}"] = {"tags": sorted(s["tags"]), "title_changed": s["title"] != before_title, "requests": mock_stats()["requests"]}
    if mode in ("http500", "http429", "invalid_json"):
        assert FAILED in s["tags"] and "Status/Prüfen" in s["tags"] and QUEUE not in s["tags"]
        assert s["title"] == before_title  # Dokument unverändert
    # in jedem Modus: stabil (keine weiteren Anfragen nach Endzustand), Taxonomie und Original intakt
    n = mock_stats()["requests"]
    time.sleep(25)
    assert mock_stats()["requests"] == n, "weitere LLM-Anfragen nach Endzustand (Schleife)"
    assert hashlib.sha256(w["wc"].download_original(s["id"])).hexdigest() == sha
    assert_taxonomy_intact(w)


def test_recovery_after_failure_requeue(w):
    """Menschlicher Wiederanlauf: Failed-Tag entfernen, Queue setzen, LLM wieder ok."""
    mock_mode("ok")
    failed = [a for a in [r["atlas_id"] for r in _all_entries(w)] if FAILED in state(w, a)["tags"]]
    assert failed, "kein fehlgeschlagenes Dokument vorhanden"
    a = failed[0]
    d = w["admin"].get_document(w["reg"].get(a)["backend_id"])
    tags = {t["name"]: t["id"] for t in w["admin"].list_all("/api/tags/")}
    w["wc"]._request("PATCH", f"/api/documents/{d['id']}/", {"tags": [i for i in d["tags"] if i not in (tags[FAILED], tags["Status/Prüfen"])] + [tags[QUEUE]]})
    info = Path(w["tmp"] / "state" / "hints" / f"{a}.json")
    j = json.loads(info.read_text()); j["finalized"] = False; info.write_text(json.dumps(j))
    assert settle(w, [a], 300)
    s = state(w, a)
    assert DONE in s["tags"] and FAILED not in s["tags"] and "Status/Verarbeitet" in s["tags"]


def _all_entries(w):
    with w["reg"]._conn() as c:
        return [dict(r) for r in c.execute("SELECT atlas_id FROM entries WHERE kind='document' AND status='active'")]


def test_timeout_hang_and_restart_recovery(w):
    """Hängender LLM-Endpunkt: dokumentiert das Verhalten und die Erholung per Neustart des GPT-Containers."""
    mock_mode("timeout")
    a, sha = ingest(w, "T10")
    link(w, [a])
    time.sleep(60)
    s = state(w, a)
    OBS["timeout_after_60s"] = {"tags": sorted(s["tags"])}
    assert QUEUE in s["tags"] and hashlib.sha256(w["wc"].download_original(s["id"])).hexdigest() == sha  # unverändert, nicht beschädigt
    mock_mode("ok")
    assert COMPOSE, "ATLAS_E2E_COMPOSE fehlt"
    r = sh("docker", "compose", "--profile", "ai", "restart", "paperless-gpt", cwd=COMPOSE, timeout=120)
    assert r.returncode == 0, r.stderr
    assert settle(w, [a], 300), "Erholung nach Neustart fehlgeschlagen"
    assert DONE in state(w, a)["tags"]


def test_unreachable_endpoint_then_recovery(w):
    mock_mode("ok")
    sh("docker", "stop", "m03-ci-mockllm")
    try:
        a, sha = ingest(w, "T13")
        link(w, [a])
        assert settle(w, [a], 420), "unerreichbarer LLM: kein Endzustand"
        s = state(w, a)
        assert FAILED in s["tags"] and "Status/Prüfen" in s["tags"]
        r = sh("docker", "compose", "--profile", "ai", "ps", "paperless-gpt", "--format", "{{.State}}", cwd=COMPOSE)
        assert r.stdout.strip() == "running"  # GPT-Container überlebt den Ausfall
        assert hashlib.sha256(w["wc"].download_original(s["id"])).hexdigest() == sha
    finally:
        sh("docker", "start", "m03-ci-mockllm")
        time.sleep(3)


def test_write_report(w):
    if REPORT:
        Path(REPORT).write_text(json.dumps(OBS, indent=2, ensure_ascii=False, sort_keys=True))
