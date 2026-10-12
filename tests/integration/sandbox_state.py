#!/usr/bin/env python3
"""Hilfswerkzeug für den Restore-Test: seed (synthetische Daten einspielen) und snapshot (vergleichbarer Zustand).

Aufruf:  sandbox_state.py seed|snapshot --root <repo> --env-file <paperless-gpt.env> [--out datei]
Nur synthetische Daten; Pfade sind die Sandbox-Pfade (/srv/atlas-sandbox/module03 ...).
"""
import argparse
import hashlib
import json
import sys
import tempfile
import time
from pathlib import Path

SRV = Path("/srv/atlas-sandbox/module03")
VAR = Path("/var/lib/atlas-sandbox/module03")
URL = "http://127.0.0.1:18000"


def token(envfile: str) -> str:
    for line in Path(envfile).read_text().splitlines():
        if line.startswith("PAPERLESS_API_TOKEN="):
            return line.split("=", 1)[1]
    raise SystemExit("PAPERLESS_API_TOKEN fehlt")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["seed", "snapshot"])
    ap.add_argument("--root", required=True)
    ap.add_argument("--env-file", required=True)
    ap.add_argument("--out")
    a = ap.parse_args()
    sys.path.insert(0, str(Path(a.root) / "src"))
    from atlas_library.assets import AssetStore, sha256_file
    from atlas_library.ingest import LibraryIngest
    from atlas_library.paperless import WriteClient
    from atlas_library.registry import Registry
    from atlas_library.synthetic import write_all
    from atlas_library.taxonomy import AdminClient, apply_taxonomy

    tok = token(a.env_file)
    reg = Registry(VAR / "registry" / "registry.sqlite3")
    if a.cmd == "seed":
        admin = AdminClient(URL, tok)
        apply_taxonomy(admin)
        tmp = Path(tempfile.mkdtemp())
        manifest = write_all(tmp)
        for name in sorted({m["correspondent"] for m in manifest.values() if m.get("correspondent")}):
            admin.post("/api/correspondents/", {"name": name, "matching_algorithm": 0})
        # Besitzer des Consume-Ordners = Paperless-Benutzer (Bootstrap setzt HOST_UID aus SUDO_USER; auf CI-Runnern 1001)
        st = (SRV / "consume").stat()
        ing = LibraryIngest(reg, SRV / "consume", VAR / "registry" / "state", "s" * 40, consume_owner=(st.st_uid, st.st_gid))
        wc = WriteClient(URL, tok)
        queued = []
        for tid in ["T01", "T02", "T03", "T04", "T05", "T06", "T07", "T11", "T14"]:
            m = manifest[tid]
            hints = [{"field": k, "value": v, "source": "user"} for k, v in
                     (("title", m["file"].rsplit(".", 1)[0]), ("correspondent", m.get("correspondent")), ("document_type", m.get("doctype")),
                      ("created", (m["date"] if len(m["date"]) == 10 else m["date"] + "-01") if m.get("date") else None),
                      ("date_precision", m.get("precision"))) if v]
            out = ing.ingest_document("s" * 40, m["file"], (tmp / m["file"]).read_bytes(), hints)
            if out["status"] == "queued":
                queued.append(out["atlas_id"])
        for _ in range(100):
            ing.reconcile("s" * 40, wc)
            if all(reg.get(i)["status"] == "active" for i in queued):
                break
            time.sleep(3)
        else:
            raise SystemExit("Dokumente nicht konsumiert")
        # technische Fassung (Revision) für T03
        t03 = next(i for i in queued if reg.get(i)["last_title"].startswith("T03"))
        ing.ingest_revision("s" * 40, t03, wc, "T03_v2.pdf", (tmp / manifest["T13b"]["file"]).read_bytes(), "technische Fassung")
        # Assets
        assets = SRV / "assets"
        for rel in ["logos/muster-logo.svg", "icons/icon.png", "templates/vorlage-brief.txt"]:
            (assets / rel).parent.mkdir(parents=True, exist_ok=True)
            (assets / rel).write_bytes((tmp / "assets" / rel).read_bytes())
            AssetStore(assets, reg).register(rel)
        print(f"SEED=PASS documents={len(queued)} assets=3")
        return
    # snapshot
    client = WriteClient(URL, tok)
    names = lambda path: {x["id"]: x["name"] for x in AdminClient(URL, tok).list_all(path)}  # noqa: E731
    tags, corr, types, fields = names("/api/tags/"), names("/api/correspondents/"), names("/api/document_types/"), names("/api/custom_fields/")
    docs = []
    for d in sorted(AdminClient(URL, tok).list_all("/api/documents/"), key=lambda x: x["id"]):
        meta = client.get_metadata(d["id"])
        docs.append({"id": d["id"], "title": d["title"], "created": d["created"], "correspondent": corr.get(d["correspondent"]),
                     "type": types.get(d["document_type"]), "tags": sorted(tags[t] for t in d["tags"]),
                     "fields": {fields[f["field"]]: f["value"] for f in d["custom_fields"]},
                     "versions": sorted(v["checksum"] for v in d["versions"]), "media_filename": meta["media_filename"],
                     "original_sha256": meta["original_checksum"], "content_sha256": hashlib.sha256(d["content"].encode()).hexdigest(),
                     "current_download_sha256": hashlib.sha256(client.download_original(d["id"])).hexdigest()})
    with reg._conn() as c:
        entries = [dict(r) for r in c.execute("SELECT * FROM entries ORDER BY atlas_id")]
        revs = [dict(r) for r in c.execute("SELECT * FROM revisions ORDER BY atlas_id, revision")]
    assets = {p.relative_to(SRV / "assets").as_posix(): sha256_file(p) for p in sorted((SRV / "assets").rglob("*")) if p.is_file()}
    snap = {"documents": docs, "registry_entries": entries, "registry_revisions": revs, "assets": assets,
            "taxonomy": {"tags": sorted(tags.values()), "types": sorted(types.values()), "fields": sorted(fields.values())}}
    Path(a.out).write_text(json.dumps(snap, indent=1, sort_keys=True, ensure_ascii=False))
    print(f"SNAPSHOT docs={len(docs)} entries={len(entries)} revisions={len(revs)} assets={len(assets)}")


if __name__ == "__main__":
    main()
