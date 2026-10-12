"""library-ingest: kontrollierter, authentifizierter Dokumentimport.

Nur: Authentifizierung, Hinweise, Status, Ablage im Paperless-Consume-Ordner. Keine eigene OCR, keine
Löschung, keine freie Taxonomie. Exakte Duplikate werden gemeldet, nicht gelöscht und nicht erneut abgelegt.
Priorität der Hinweise: explizite Nutzerangabe > deterministisch extrahiert > LLM-Vorschlag.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from pathlib import Path

from .paperless import PaperlessError, WriteClient
from .registry import Registry

ALLOWED_EXT = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".txt"}
DEFAULT_MAX_BYTES = 50 * 1024 * 1024
SOURCE_PRIORITY = {"user": 0, "extracted": 1, "llm": 2}
ALLOWED_HINT_FIELDS = {"title", "created", "correspondent", "document_type", "tags", "notes"}


class IngestError(Exception):
    pass


def sanitize_filename(name: str) -> str:
    base = os.path.basename(name.replace("\\", "/"))
    base = re.sub(r"[\x00-\x1f\x7f/\\:*?\"<>|]", "_", base).strip(" .")
    if not base or base.startswith("."):
        raise IngestError("ungültiger Dateiname")
    return base[:150]


def merge_hints(hints: list[dict]) -> dict:
    """Je Feld gewinnt die Quelle mit höchster Priorität; unbekannte Felder/Quellen werden abgelehnt."""
    best: dict[str, tuple[int, object]] = {}
    for h in hints:
        field, source = h.get("field"), h.get("source")
        if field not in ALLOWED_HINT_FIELDS:
            raise IngestError(f"Hinweisfeld nicht erlaubt: {field!r} (keine freie Taxonomie)")
        if source not in SOURCE_PRIORITY:
            raise IngestError(f"unbekannte Hinweisquelle: {source!r}")
        prio = SOURCE_PRIORITY[source]
        if field not in best or prio < best[field][0]:
            best[field] = (prio, h.get("value"))
    return {k: v for k, (_, v) in best.items()}


class LibraryIngest:
    def __init__(self, registry: Registry, consume_dir: str | Path, state_dir: str | Path, token: str,
                 max_bytes: int = DEFAULT_MAX_BYTES):
        if len(token) < 24:
            raise ValueError("Ingest-Token zu kurz (mind. 24 Zeichen)")
        self.registry = registry
        self.consume = Path(consume_dir)
        self.state = Path(state_dir)
        self._token = token.encode()
        self.max_bytes = max_bytes
        (self.state / "hints").mkdir(parents=True, exist_ok=True)

    def _auth(self, token: str) -> None:
        if not hmac.compare_digest(self._token, (token or "").encode()):
            raise PermissionError("nicht autorisiert")

    def ingest_document(self, token: str, filename: str, data: bytes, hints: list[dict] | None = None) -> dict:
        self._auth(token)
        name = sanitize_filename(filename)
        if Path(name).suffix.lower() not in ALLOWED_EXT:
            raise IngestError(f"Dateityp nicht erlaubt: {Path(name).suffix}")
        if not data or len(data) > self.max_bytes:
            raise IngestError("Datei leer oder zu groß")
        merged = merge_hints(hints or [])
        sha = hashlib.sha256(data).hexdigest()
        existing = self.registry.find_by_hash(sha)
        if existing:
            return {"status": "duplicate", "atlas_id": existing[0], "action": "none",
                    "note": "bit-identisches Duplikat; nichts abgelegt, nichts gelöscht"}
        atlas_id = self.registry.create(kind="document", backend="paperless", sha256=sha, status="pending",
                                        title=merged.get("title") or name)
        target = self.consume / f"{Path(name).stem} [{atlas_id[:8]}]{Path(name).suffix.lower()}"
        tmp = self.consume / f".{atlas_id}.part"
        self.consume.mkdir(parents=True, exist_ok=True)
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640)
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        if target.exists():  # Überschreiben ausgeschlossen
            tmp.unlink()
            raise IngestError("Zieldatei existiert bereits")
        os.replace(tmp, target)
        (self.state / "hints" / f"{atlas_id}.json").write_text(json.dumps(
            {"hints": merged, "md5": hashlib.md5(data, usedforsecurity=False).hexdigest(), "file": target.name}))
        return {"status": "queued", "atlas_id": atlas_id, "ref": self.registry.pin(atlas_id), "consume_file": target.name}

    def reconcile(self, token: str, paperless: WriteClient) -> list[dict]:
        """Ordnet pending-Einträge nach Paperless-MD5 den Paperless-Dokumenten zu und schreibt das ATLAS-ID-Feld."""
        self._auth(token)
        results = []
        for f in sorted((self.state / "hints").glob("*.json")):
            atlas_id = f.stem
            e = self.registry.get(atlas_id)
            if e is None or e["status"] != "pending":
                continue
            md5 = json.loads(f.read_text())["md5"]
            try:
                found = paperless.find_by_checksum(md5)
                if len(found) != 1:
                    results.append({"atlas_id": atlas_id, "status": "waiting" if not found else "ambiguous"})
                    continue
                doc = found[0]
                paperless.set_atlas_id(doc["id"], atlas_id)
                self.registry.link_backend(atlas_id, str(doc["id"]), doc.get("title"))
                results.append({"atlas_id": atlas_id, "status": "linked", "paperless_id": doc["id"]})
            except PaperlessError as exc:
                results.append({"atlas_id": atlas_id, "status": "error", "error": str(exc)})
        return results
