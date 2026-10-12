"""Asset Store: Dateien unter einer festen Wurzel, über die Registry mit ATLAS-ID aufgelöst."""
from __future__ import annotations

import hashlib
import mimetypes
from pathlib import Path

from .registry import Registry


class AssetError(Exception):
    pass


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class AssetStore:
    def __init__(self, root: str | Path, registry: Registry):
        self.root = Path(root).resolve()
        self.registry = registry

    def _safe(self, relative_path: str) -> Path:
        """Verhindert Traversal, absolute Pfade und Symlink-Ausbrüche."""
        if not relative_path or Path(relative_path).is_absolute() or "\x00" in relative_path:
            raise AssetError("ungültiger relativer Pfad")
        candidate = self.root / relative_path
        resolved = candidate.resolve()
        if self.root != resolved and self.root not in resolved.parents:
            raise AssetError("Pfad außerhalb des Asset Stores")
        cur = self.root
        for part in Path(relative_path).parts:
            cur = cur / part
            if cur.is_symlink():
                raise AssetError("Symlinks im Asset Store nicht erlaubt")
        return resolved

    def register(self, relative_path: str, title: str | None = None) -> str:
        p = self._safe(relative_path)
        if not p.is_file():
            raise AssetError("Datei existiert nicht")
        mime = mimetypes.guess_type(p.name)[0]
        return self.registry.create(kind="asset", backend="asset-store", sha256=sha256_file(p),
                                    relative_path=p.relative_to(self.root).as_posix(), mime_type=mime,
                                    title=title or p.name)

    def open_exact(self, atlas_id: str) -> tuple[Path, str | None]:
        """Liefert die exakte registrierte Datei. Stimmt der Hash nicht mehr, wird NICHT neu erzeugt/geraten."""
        e = self.registry.get(atlas_id)
        if e is None or e["kind"] != "asset":
            raise AssetError("unbekanntes Asset")
        if e["status"] != "active":
            raise AssetError(f"Asset-Status: {e['status']}")
        p = self._safe(e["relative_path"])
        if not p.is_file():
            raise AssetError("Datei fehlt im Asset Store")
        if sha256_file(p) != e["current_hash"]:
            raise AssetError("Integritätsfehler: Dateiinhalt weicht von der Registry ab (neue Revision bewusst registrieren)")
        return p, e["mime_type"]
