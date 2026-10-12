"""ATLAS-Registry (SQLite): stabile UUIDv7-Identität, revisionsgebundene Referenzen, Tombstones.

Regeln (services/registry/SCHEMA.md):
- ID wird nie wiederverwendet (PRIMARY KEY, Einträge werden nie gelöscht, nur Status wechselt).
- Paperless-ID ist nur Backend-ID.
- Hard Delete -> Tombstone (status=deleted), Eintrag bleibt bestehen.
- Keine Dokumentkopien; die Registry speichert nur Metadaten und Hashes.

Abweichung vom Schema (dokumentiert in docs/DEVIATIONS.md): zusätzlicher Status ``pending`` für
Ingest-Einträge, die noch nicht von Paperless konsumiert und per Prüfsumme zugeordnet wurden.
"""
from __future__ import annotations

import re
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .refs import Ref, parse_ref
from .uuid7 import uuid7

KINDS = ("document", "asset")
BACKENDS = ("paperless", "asset-store")
STATUSES = ("pending", "active", "trashed", "deleted")
_SHA = re.compile(r"^[0-9a-f]{64}$")

SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
  atlas_id      TEXT PRIMARY KEY,
  kind          TEXT NOT NULL CHECK (kind IN ('document','asset')),
  backend       TEXT NOT NULL CHECK (backend IN ('paperless','asset-store')),
  backend_id    TEXT,
  relative_path TEXT,
  status        TEXT NOT NULL CHECK (status IN ('pending','active','trashed','deleted')),
  created_at    TEXT NOT NULL,
  current_hash  TEXT NOT NULL,
  mime_type     TEXT,
  last_title    TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_backend ON entries(backend, backend_id) WHERE backend_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ux_path ON entries(backend, relative_path) WHERE relative_path IS NOT NULL;
CREATE TABLE IF NOT EXISTS revisions (
  atlas_id   TEXT NOT NULL REFERENCES entries(atlas_id),
  revision   INTEGER NOT NULL,
  sha256     TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (atlas_id, revision)
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class Resolution:
    """Ergebnis von resolve(): status ist ok | revision_mismatch | trashed | deleted | unknown | pending."""

    status: str
    atlas_id: str | None = None
    kind: str | None = None
    backend: str | None = None
    backend_id: str | None = None
    relative_path: str | None = None
    current_hash: str | None = None
    pinned_hash: str | None = None
    pinned_revision_known: bool | None = None


class Registry:
    def __init__(self, path: str | Path):
        self.path = str(path)
        with self._conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def _conn(self):
        c = sqlite3.connect(self.path)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        try:
            yield c
            c.commit()
        except Exception:
            c.rollback()
            raise
        finally:
            c.close()

    def create(self, *, kind: str, backend: str, sha256: str, backend_id: str | None = None,
               relative_path: str | None = None, status: str = "active", mime_type: str | None = None,
               title: str | None = None) -> str:
        if kind not in KINDS or backend not in BACKENDS or status not in STATUSES or status == "deleted":
            raise ValueError("ungültige Kombination kind/backend/status")
        if (kind == "document") != (backend == "paperless"):
            raise ValueError("document <-> paperless, asset <-> asset-store")
        if not _SHA.match(sha256):
            raise ValueError("sha256 muss 64 Hex-Zeichen (klein) sein")
        atlas_id = str(uuid7())
        now = _now()
        with self._conn() as c:
            c.execute("INSERT INTO entries VALUES (?,?,?,?,?,?,?,?,?,?)",
                      (atlas_id, kind, backend, backend_id, relative_path, status, now, sha256, mime_type, title))
            c.execute("INSERT INTO revisions VALUES (?,?,?,?)", (atlas_id, 1, sha256, now))
        return atlas_id

    def get(self, atlas_id: str) -> sqlite3.Row | None:
        with self._conn() as c:
            return c.execute("SELECT * FROM entries WHERE atlas_id=?", (atlas_id,)).fetchone()

    def revisions(self, atlas_id: str) -> list[tuple[int, str]]:
        with self._conn() as c:
            return [(r["revision"], r["sha256"]) for r in
                    c.execute("SELECT revision, sha256 FROM revisions WHERE atlas_id=? ORDER BY revision", (atlas_id,))]

    def find_by_hash(self, sha256: str) -> list[str]:
        with self._conn() as c:
            return [r["atlas_id"] for r in c.execute(
                "SELECT DISTINCT atlas_id FROM revisions WHERE sha256=? ORDER BY atlas_id", (sha256,))]

    def find_by_backend(self, backend: str, backend_id: str) -> str | None:
        with self._conn() as c:
            r = c.execute("SELECT atlas_id FROM entries WHERE backend=? AND backend_id=?", (backend, backend_id)).fetchone()
            return r["atlas_id"] if r else None

    def add_revision(self, atlas_id: str, sha256: str) -> int:
        """Neue technische Fassung desselben Dokuments (gleiche ATLAS-ID, neue Revision)."""
        if not _SHA.match(sha256):
            raise ValueError("sha256 ungültig")
        with self._conn() as c:
            e = c.execute("SELECT status, current_hash FROM entries WHERE atlas_id=?", (atlas_id,)).fetchone()
            if e is None:
                raise KeyError(atlas_id)
            if e["status"] == "deleted":
                raise ValueError("Tombstone: keine neue Revision für gelöschte ID")
            if e["current_hash"] == sha256:
                return c.execute("SELECT MAX(revision) m FROM revisions WHERE atlas_id=?", (atlas_id,)).fetchone()["m"]
            n = c.execute("SELECT MAX(revision) m FROM revisions WHERE atlas_id=?", (atlas_id,)).fetchone()["m"] + 1
            c.execute("INSERT INTO revisions VALUES (?,?,?,?)", (atlas_id, n, sha256, _now()))
            c.execute("UPDATE entries SET current_hash=? WHERE atlas_id=?", (sha256, atlas_id))
            return n

    def link_backend(self, atlas_id: str, backend_id: str, title: str | None = None) -> None:
        """Ordnet einen pending-Eintrag der Paperless-ID zu und aktiviert ihn."""
        with self._conn() as c:
            e = c.execute("SELECT status FROM entries WHERE atlas_id=?", (atlas_id,)).fetchone()
            if e is None or e["status"] != "pending":
                raise ValueError("nur pending-Einträge können verknüpft werden")
            c.execute("UPDATE entries SET backend_id=?, status='active', last_title=COALESCE(?, last_title) WHERE atlas_id=?",
                      (backend_id, title, atlas_id))

    def set_status(self, atlas_id: str, status: str) -> None:
        """active <-> trashed; deleted ist ein Tombstone und endgültig. Löscht nie den Eintrag selbst."""
        if status not in ("active", "trashed", "deleted"):
            raise ValueError(status)
        with self._conn() as c:
            e = c.execute("SELECT status FROM entries WHERE atlas_id=?", (atlas_id,)).fetchone()
            if e is None:
                raise KeyError(atlas_id)
            if e["status"] == "deleted":
                raise ValueError("Tombstone ist endgültig")
            c.execute("UPDATE entries SET status=? WHERE atlas_id=?", (status, atlas_id))

    def update_title(self, atlas_id: str, title: str) -> None:
        with self._conn() as c:
            c.execute("UPDATE entries SET last_title=? WHERE atlas_id=?", (title, atlas_id))

    def resolve(self, ref: Ref | str) -> Resolution:
        """Löst eine (ggf. revisionsgebundene) Referenz auf. Rät nie: Unbekanntes bleibt ``unknown``."""
        r = parse_ref(ref) if isinstance(ref, str) else ref
        e = self.get(r.atlas_id)
        if e is None:
            return Resolution("unknown", atlas_id=r.atlas_id)
        base = dict(atlas_id=e["atlas_id"], kind=e["kind"], backend=e["backend"], backend_id=e["backend_id"],
                    relative_path=e["relative_path"], current_hash=e["current_hash"], pinned_hash=r.sha256)
        if e["status"] in ("deleted", "trashed", "pending"):
            return Resolution(e["status"], **base)
        if r.sha256 is not None and r.sha256 != e["current_hash"]:
            known = any(h == r.sha256 for _, h in self.revisions(r.atlas_id))
            return Resolution("revision_mismatch", pinned_revision_known=known, **base)
        return Resolution("ok", **base)

    def pin(self, atlas_id: str) -> str:
        """Gibt die SHA-gepinnte Referenz der aktuellen Revision zurück."""
        e = self.get(atlas_id)
        if e is None:
            raise KeyError(atlas_id)
        return str(Ref(atlas_id, e["current_hash"]))
