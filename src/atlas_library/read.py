"""library-read: read-only Adapter. Keine Lösch-/Merge-/Edit-/User-/Workflow-Funktionen.

Retrieval-Reihenfolge: ID -> strukturierte Metadaten -> Volltext -> Snippet -> OCR -> Datei.
"""
from __future__ import annotations

import base64

from .assets import AssetError, AssetStore
from .paperless import ReadClient
from .refs import InvalidRef, parse_ref
from .registry import Registry

MAX_TEXT_CHARS = 20000
MAX_FILE_BYTES = 25 * 1024 * 1024


class LibraryRead:
    def __init__(self, registry: Registry, paperless: ReadClient | None, assets: AssetStore | None):
        self.registry, self.paperless, self.assets = registry, paperless, assets

    # -- Auflösung ---------------------------------------------------------------------------
    def resolve_atlas_ref(self, ref: str) -> dict:
        try:
            r = self.registry.resolve(ref)
        except InvalidRef as exc:
            return {"status": "invalid_ref", "error": str(exc)}
        out = {"status": r.status, "atlas_id": r.atlas_id}
        if r.status in ("ok", "revision_mismatch"):
            out.update(kind=r.kind, current_hash=r.current_hash)
            if r.status == "revision_mismatch":
                out.update(pinned_hash=r.pinned_hash, pinned_revision_known=r.pinned_revision_known)
        return out

    def _require_ok(self, ref: str):
        res = self.registry.resolve(ref) if self._valid(ref) else None
        if res is None:
            return None, {"status": "invalid_ref"}
        if res.status != "ok":
            return None, self.resolve_atlas_ref(ref)
        return res, None

    @staticmethod
    def _valid(ref: str) -> bool:
        try:
            parse_ref(ref)
            return True
        except InvalidRef:
            return False

    # -- Metadaten / Text / Datei -------------------------------------------------------------
    def get_document_metadata(self, ref: str) -> dict:
        res, err = self._require_ok(ref)
        if err:
            return err
        e = self.registry.get(res.atlas_id)
        out = {"status": "ok", "atlas_id": res.atlas_id, "kind": res.kind, "current_hash": res.current_hash,
               "mime_type": e["mime_type"], "title": e["last_title"], "pinned_ref": self.registry.pin(res.atlas_id),
               "revisions": len(self.registry.revisions(res.atlas_id))}
        if res.kind == "document" and self.paperless:
            d = self.paperless.get_document(res.backend_id)
            out["paperless"] = {k: d.get(k) for k in ("title", "created", "correspondent", "document_type", "tags", "custom_fields")}
        return out

    def get_document_text(self, ref: str, max_chars: int = MAX_TEXT_CHARS) -> dict:
        res, err = self._require_ok(ref)
        if err:
            return err
        if res.kind != "document" or not self.paperless:
            return {"status": "unsupported", "error": "Text nur für Dokumente mit Paperless-Backend"}
        text = self.paperless.get_document(res.backend_id).get("content") or ""
        cap = max(1, min(max_chars, MAX_TEXT_CHARS))
        return {"status": "ok", "atlas_id": res.atlas_id, "truncated": len(text) > cap, "text": text[:cap]}

    def get_document_file(self, ref: str) -> dict:
        res, err = self._require_ok(ref)
        if err:
            return err
        if res.kind != "document" or not self.paperless:
            return {"status": "unsupported"}
        data = self.paperless.download_original(res.backend_id)
        if len(data) > MAX_FILE_BYTES:
            return {"status": "too_large", "size": len(data)}
        import hashlib
        if hashlib.sha256(data).hexdigest() != res.current_hash:
            return {"status": "integrity_error", "error": "Original weicht vom registrierten Hash ab"}
        return {"status": "ok", "atlas_id": res.atlas_id, "sha256": res.current_hash,
                "content_base64": base64.b64encode(data).decode()}

    def get_asset(self, ref: str) -> dict:
        res, err = self._require_ok(ref)
        if err:
            return err
        if res.kind != "asset" or not self.assets:
            return {"status": "unsupported"}
        try:
            path, mime = self.assets.open_exact(res.atlas_id)
        except AssetError as exc:
            return {"status": "asset_error", "error": str(exc)}
        data = path.read_bytes()
        if len(data) > MAX_FILE_BYTES:
            return {"status": "too_large", "size": len(data)}
        return {"status": "ok", "atlas_id": res.atlas_id, "sha256": res.current_hash, "mime_type": mime,
                "content_base64": base64.b64encode(data).decode()}

    # -- Suche: kompakte Treffer, Mehrdeutigkeit sichtbar ----------------------------------------
    def search_documents(self, query: str, limit: int = 10) -> dict:
        if not self.paperless:
            return {"status": "unsupported"}
        hits = []
        for d in self.paperless.search(query, limit):
            aid = self.registry.find_by_backend("paperless", str(d["id"]))
            hits.append({"atlas_id": aid, "title": d.get("title"), "created": d.get("created"),
                         "registered": aid is not None})
        return {"status": "ok", "count": len(hits), "ambiguous": len(hits) > 1, "hits": hits}
