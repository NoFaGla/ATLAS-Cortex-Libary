"""CLI: atlas-library {resolve,pin,register-asset}. Konfiguration über Umgebungsvariablen/Argumente, keine Secrets im Code."""
from __future__ import annotations

import argparse
import json
import sys

from .assets import AssetStore
from .read import LibraryRead
from .registry import Registry


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="atlas-library")
    ap.add_argument("--registry", required=True, help="Pfad der Registry-SQLite-Datei")
    ap.add_argument("--assets", help="Asset-Store-Wurzel")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("resolve"); s.add_argument("ref")
    s = sub.add_parser("register-asset"); s.add_argument("relative_path")
    sub.add_parser("registry-check", help="Schemaversion + Integrität der Registry prüfen (Exit 1 bei Problemen)")
    sub.add_parser("taxonomy", help="Minimal-Taxonomie in Paperless anlegen (ATLAS_PAPERLESS_URL, ATLAS_PAPERLESS_ADMIN_TOKEN[_FILE])")
    a = ap.parse_args(argv)
    reg = Registry(a.registry)
    assets = AssetStore(a.assets, reg) if a.assets else None
    if a.cmd == "registry-check":
        problems = reg.integrity_check()
        print(json.dumps({"schema_version": reg.schema_version(), "problems": problems}))
        return 1 if problems else 0
    if a.cmd == "taxonomy":
        import os
        from .config import secret
        from .taxonomy import AdminClient, apply_taxonomy
        rep = apply_taxonomy(AdminClient(os.environ["ATLAS_PAPERLESS_URL"], secret("ATLAS_PAPERLESS_ADMIN_TOKEN")))
        print(json.dumps({"created": len(rep["created"]), "existing": len(rep["existing"]), "items": rep["created"]}, ensure_ascii=False))
    elif a.cmd == "resolve":
        print(json.dumps(LibraryRead(reg, None, assets).resolve_atlas_ref(a.ref), indent=2))
    elif a.cmd == "register-asset":
        if not assets:
            print("--assets erforderlich", file=sys.stderr); return 2
        aid = assets.register(a.relative_path)
        print(reg.pin(aid))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
