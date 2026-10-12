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
import time
from pathlib import Path

from .paperless import PaperlessError, WriteClient
from .registry import Registry

ALLOWED_EXT = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".txt"}
DEFAULT_MAX_BYTES = 50 * 1024 * 1024
SOURCE_PRIORITY = {"user": 0, "extracted": 1, "llm": 2}
ALLOWED_HINT_FIELDS = {"title", "created", "date_precision", "correspondent", "document_type", "tags", "notes"}
DATE_PRECISIONS = {"Tag", "Monat", "Jahr"}


class IngestError(Exception):
    pass


def sanitize_filename(name: str) -> str:
    base = os.path.basename(name.replace("\\", "/"))
    base = re.sub(r"[\x00-\x1f\x7f/\\:*?\"<>|]", "_", base).strip(" .")
    if not base or base.startswith("."):
        raise IngestError("ungültiger Dateiname")
    return base[:150]


def safe_title(title: str) -> str:
    """Paperless nutzt den Titel im Dateinamen; '/' würde dort ein Unterverzeichnis erzeugen."""
    t = re.sub(r"[\x00-\x1f\x7f]", " ", str(title)).replace("/", "-").replace("\\", "-")
    return re.sub(r"\s+", " ", t).strip()[:200]


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


def user_fields(hints: list[dict]) -> list[str]:
    """Felder, deren Gewinner-Hinweis eine explizite Nutzerangabe ist (Priorität Nutzer > extrahiert > LLM)."""
    merged_prio: dict[str, int] = {}
    for h in hints:
        f, src = h.get("field"), h.get("source")
        if f in ALLOWED_HINT_FIELDS and src in SOURCE_PRIORITY:
            merged_prio[f] = min(merged_prio.get(f, 99), SOURCE_PRIORITY[src])
    return sorted(f for f, p in merged_prio.items() if p == 0)


class LibraryIngest:
    def __init__(self, registry: Registry, consume_dir: str | Path, state_dir: str | Path, token: str,
                 max_bytes: int = DEFAULT_MAX_BYTES, consume_owner: tuple[int, int] | None = None):
        if len(token) < 24:
            raise ValueError("Ingest-Token zu kurz (mind. 24 Zeichen)")
        self.registry = registry
        self.consume = Path(consume_dir)
        self.state = Path(state_dir)
        self._token = token.encode()
        self.max_bytes = max_bytes
        self.consume_owner = consume_owner  # (uid, gid), falls der Dienst nicht als Paperless-Benutzer läuft
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
        if merged.get("title"):
            merged["title"] = safe_title(merged["title"])
        if merged.get("date_precision") not in (None, *DATE_PRECISIONS):
            raise IngestError("date_precision muss Tag, Monat oder Jahr sein")
        if merged.get("created") is not None and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(merged["created"])):
            raise IngestError("created muss YYYY-MM-DD sein (bei Monats-/Jahresangaben den ersten Tag + date_precision)")
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
        if self.consume_owner:
            os.chown(tmp, *self.consume_owner)
        if target.exists():  # Überschreiben ausgeschlossen
            tmp.unlink()
            raise IngestError("Zieldatei existiert bereits")
        os.replace(tmp, target)
        (self.state / "hints" / f"{atlas_id}.json").write_text(json.dumps(
            {"hints": merged, "user_fields": user_fields(hints or []), "sha256": sha, "file": target.name, "finalized": False}))
        return {"status": "queued", "atlas_id": atlas_id, "ref": self.registry.pin(atlas_id), "consume_file": target.name}

    def reconcile(self, token: str, paperless: WriteClient, queue_for_gpt: bool = False) -> list[dict]:
        """Ordnet pending-Einträge nach Paperless-MD5 den Paperless-Dokumenten zu und schreibt das ATLAS-ID-Feld."""
        self._auth(token)
        results = []
        for f in sorted((self.state / "hints").glob("*.json")):
            atlas_id = f.stem
            e = self.registry.get(atlas_id)
            if e is None or e["status"] != "pending":
                continue
            info = json.loads(f.read_text())
            sha = info["sha256"]
            try:
                found = paperless.find_by_checksum(sha)
                if len(found) != 1:
                    results.append({"atlas_id": atlas_id, "status": "waiting" if not found else "ambiguous"})
                    continue
                doc = found[0]
                paperless.set_atlas_id(doc["id"], atlas_id)
                self.registry.link_backend(atlas_id, str(doc["id"]), doc.get("title"))
                # Reihenfolge laut Lifecycle: OCR (Paperless) -> ATLAS-ID -> (Paperless-GPT) -> Verarbeitet | Prüfen
                extra = ["Status/Unverarbeitet"] + (["System/Paperless-GPT-Queue"] if queue_for_gpt else [])
                applied = paperless.apply_hints(doc["id"], info.get("hints", {}), extra)
                if applied["unresolved"]:
                    paperless.apply_hints(doc["id"], {}, ["Status/Prüfen"])
                results.append({"atlas_id": atlas_id, "status": "linked", "paperless_id": doc["id"],
                                "unresolved": applied["unresolved"]})
            except PaperlessError as exc:
                results.append({"atlas_id": atlas_id, "status": "error", "error": str(exc)})
        return results

    def ingest_revision(self, token: str, atlas_id: str, paperless: WriteClient, filename: str, data: bytes,
                        label: str | None = None) -> dict:
        """Neue *technische* Fassung desselben Dokuments: gleiche ATLAS-ID, neue Revision (Paperless-Version).

        Das alte Original bleibt als Paperless-Version erhalten. Fachlich neue Dokumente gehen über ingest_document.
        """
        self._auth(token)
        name = sanitize_filename(filename)
        if Path(name).suffix.lower() not in ALLOWED_EXT or not data or len(data) > self.max_bytes:
            raise IngestError("Datei ungültig")
        e = self.registry.get(atlas_id)
        if e is None or e["kind"] != "document" or e["status"] != "active":
            raise IngestError("ATLAS-ID unbekannt oder nicht aktiv")
        sha = hashlib.sha256(data).hexdigest()
        if sha == e["current_hash"]:
            return {"status": "unchanged", "atlas_id": atlas_id}
        if sha in {h for _, h in self.registry.revisions(atlas_id)}:
            raise IngestError("Diese Fassung existiert bereits als ältere Revision")
        paperless.upload_version(e["backend_id"], name, data, label)
        # erst übernehmen, wenn Paperless die Version tatsächlich führt (asynchrone Verarbeitung)
        for _ in range(60):
            doc = paperless.get_document(e["backend_id"])
            if any(v.get("checksum") == sha for v in doc.get("versions", [])):
                rev = self.registry.add_revision(atlas_id, sha)
                return {"status": "revision_added", "atlas_id": atlas_id, "revision": rev, "ref": self.registry.pin(atlas_id)}
            time.sleep(1)
        return {"status": "pending", "atlas_id": atlas_id, "note": "Version noch nicht in Paperless sichtbar"}

    def sync_lifecycle(self, token: str, paperless: WriteClient) -> list[dict]:
        """Spiegelt Paperless-Status (aktiv/Papierkorb/endgültig gelöscht -> Tombstone) in die Registry. Löscht nie selbst."""
        self._auth(token)
        out = []
        with self.registry._conn() as c:
            rows = c.execute("SELECT atlas_id, backend_id, status FROM entries WHERE kind='document' AND backend_id IS NOT NULL "
                             "AND status IN ('active','trashed')").fetchall()
        for r in rows:
            st = paperless.document_exists(r["backend_id"])
            new = {"active": "active", "trashed": "trashed", "gone": "deleted"}[st]
            if new != r["status"]:
                self.registry.set_status(r["atlas_id"], new)
                out.append({"atlas_id": r["atlas_id"], "from": r["status"], "to": new})
        return out

    def finalize(self, token: str, paperless: WriteClient) -> list[dict]:
        """Nach Paperless-GPT: explizite Nutzerhinweise haben Vorrang vor LLM-Vorschlägen und werden erneut gesetzt;
        Status-Tag wird nachgeführt (Done -> Status/Verarbeitet, Failed -> Status/Prüfen). Ohne GPT-Ergebnis passiert nichts."""
        self._auth(token)
        out = []
        for f in sorted((self.state / "hints").glob("*.json")):
            info = json.loads(f.read_text())
            e = self.registry.get(f.stem)
            if info.get("finalized") or e is None or e["status"] != "active":
                continue
            doc = paperless.get_document(e["backend_id"])
            names = paperless.tag_names(doc)
            if "System/Paperless-GPT-Failed" in names:
                paperless.apply_hints(doc["id"], {}, ["Status/Prüfen"], ["Status/Unverarbeitet", "System/Paperless-GPT-Queue"])
                outcome = "needs_review"
            elif "System/Paperless-GPT-Done" in names:
                mine = {k: v for k, v in info.get("hints", {}).items() if k in info.get("user_fields", []) and k in ("title", "created", "date_precision", "tags")}
                paperless.apply_hints(doc["id"], mine, ["Status/Verarbeitet"], ["Status/Unverarbeitet"])
                outcome = "processed"
            else:
                continue
            info["finalized"] = True
            f.write_text(json.dumps(info))
            out.append({"atlas_id": f.stem, "status": outcome})
        return out
