"""Minimaler Paperless-ngx-API-Client. ReadClient kann technisch nur GET; WriteClient nur gezieltes ATLAS-ID-Feld."""
from __future__ import annotations

import json
import urllib.parse
import urllib.request

API_ACCEPT = "application/json; version=10"


class PaperlessError(Exception):
    pass


class ReadClient:
    def __init__(self, base_url: str, token: str, timeout: float = 15.0):
        if not base_url.startswith(("http://", "https://")):
            raise ValueError("base_url muss http(s) sein")
        self.base = base_url.rstrip("/")
        self._token = token
        self.timeout = timeout

    def _request(self, method: str, path: str, body: dict | None = None) -> tuple[bytes, dict]:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method, headers={
            "Authorization": f"Token {self._token}", "Accept": API_ACCEPT,
            **({"Content-Type": "application/json"} if data else {})})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:  # noqa: S310 (Basis-URL ist Konfiguration)
                return r.read(), dict(r.headers)
        except Exception as exc:  # urllib.error.* , Timeouts
            raise PaperlessError(f"{method} {path}: {exc}") from exc

    def _get_json(self, path: str) -> dict:
        raw, _ = self._request("GET", path)
        return json.loads(raw)

    def search(self, query: str, limit: int = 10) -> list[dict]:
        qs = urllib.parse.urlencode({"query": query, "page_size": max(1, min(limit, 50))})
        return self._get_json(f"/api/documents/?{qs}").get("results", [])

    def get_document(self, doc_id: str | int) -> dict:
        return self._get_json(f"/api/documents/{int(doc_id)}/")

    def get_metadata(self, doc_id: str | int) -> dict:
        return self._get_json(f"/api/documents/{int(doc_id)}/metadata/")

    def download_original(self, doc_id: str | int, version_id: str | int | None = None) -> bytes:
        """Original (nicht Archiv-PDF). Ohne version_id die aktuelle Fassung, sonst genau diese Version."""
        q = "original=true" + (f"&version={int(version_id)}" if version_id is not None else "")
        raw, _ = self._request("GET", f"/api/documents/{int(doc_id)}/download/?{q}")
        return raw

    def find_by_checksum(self, sha256: str) -> list[dict]:
        """Paperless 3.x führt SHA-256 als Dokument-Checksum (verifiziert gegen 3.3.0)."""
        qs = urllib.parse.urlencode({"checksum__iexact": sha256})
        return self._get_json(f"/api/documents/?{qs}").get("results", [])

    def document_exists(self, doc_id: str | int) -> str:
        """'active' | 'trashed' | 'gone' (Soft-Delete landet im Papierkorb, siehe PAPERLESS_EMPTY_TRASH_DELAY)."""
        try:
            self._get_json(f"/api/documents/{int(doc_id)}/")
            return "active"
        except PaperlessError as exc:
            if "404" not in str(exc):
                raise
        page = self._get_json("/api/trash/?page_size=100")
        return "trashed" if any(d.get("id") == int(doc_id) for d in page.get("results", [])) else "gone"


def _multipart(fields: dict[str, str], filename: str, data: bytes) -> tuple[bytes, str]:
    import uuid
    b = uuid.uuid4().hex
    parts = []
    for k, v in fields.items():
        parts.append(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    parts.append(f'--{b}\r\nContent-Disposition: form-data; name="document"; filename="{filename}"\r\n'
                 f'Content-Type: application/octet-stream\r\n\r\n'.encode() + data + b"\r\n")
    parts.append(f"--{b}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={b}"


class WriteClient(ReadClient):
    """Schreibende Operationen, bewusst eng: ATLAS-ID setzen, validierte Hinweise anwenden, neue Version hochladen.

    Kein Löschen, kein Mergen, kein Überschreiben von Dateien, keine Neuanlage von Taxonomie-Objekten.
    """

    FIELD_NAME = "ATLAS-ID"

    def _field_id(self) -> int:
        for f in self._get_json("/api/custom_fields/").get("results", []):
            if f.get("name") == self.FIELD_NAME:
                return f["id"]
        raise PaperlessError("Custom Field 'ATLAS-ID' fehlt (Taxonomie Gate F)")

    def set_atlas_id(self, doc_id: str | int, atlas_id: str) -> None:
        doc = self.get_document(doc_id)
        fid = self._field_id()
        fields = [f for f in doc.get("custom_fields", []) if f.get("field") != fid]
        existing = [f for f in doc.get("custom_fields", []) if f.get("field") == fid and f.get("value") not in (None, "")]
        if existing and existing[0]["value"] != atlas_id:
            raise PaperlessError("Dokument trägt bereits eine andere ATLAS-ID; wird nicht überschrieben")
        fields.append({"field": fid, "value": atlas_id})
        self._request("PATCH", f"/api/documents/{int(doc_id)}/", {"custom_fields": fields})

    # -- neue technische Fassung ----------------------------------------------------------------
    def upload_version(self, doc_id: str | int, filename: str, data: bytes, label: str | None = None) -> None:
        body, ctype = _multipart({"version_label": label or ""}, filename, data)
        req = urllib.request.Request(f"{self.base}/api/documents/{int(doc_id)}/update_version/", data=body, method="POST",
                                     headers={"Authorization": f"Token {self._token}", "Accept": API_ACCEPT,
                                              "Content-Type": ctype})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout):  # noqa: S310
                return
        except Exception as exc:
            raise PaperlessError(f"update_version {doc_id}: {exc}") from exc

    # -- Hinweise anwenden (nur vorhandene Taxonomie) -----------------------------------------------
    def _lookup(self, path: str, name: str) -> int | None:
        qs = urllib.parse.urlencode({"name__iexact": name})
        res = self._get_json(f"{path}?{qs}").get("results", [])
        return res[0]["id"] if len(res) == 1 else None

    def tag_names(self, doc: dict) -> set[str]:
        by_id = {t["id"]: t["name"] for t in self._get_json("/api/tags/?page_size=200").get("results", [])}
        return {by_id[i] for i in doc.get("tags", []) if i in by_id}

    def apply_hints(self, doc_id: str | int, hints: dict, extra_tags: list[str] | None = None,
                    remove_tags: list[str] | None = None) -> dict:
        """Wendet freigegebene Hinweise an. Unbekannte Korrespondenten/Typen/Tags werden NICHT angelegt,
        sondern als ``unresolved`` gemeldet (Dokument bekommt dann Status/Prüfen)."""
        body: dict = {}
        unresolved: list[str] = []
        if hints.get("title"):
            body["title"] = hints["title"]
        if hints.get("created"):
            body["created_date"] = hints["created"]
        for key, path, field in (("correspondent", "/api/correspondents/", "correspondent"),
                                 ("document_type", "/api/document_types/", "document_type")):
            if hints.get(key):
                found = self._lookup(path, hints[key])
                if found is None:
                    unresolved.append(f"{key}:{hints[key]}")
                else:
                    body[field] = found
        tag_ids = []
        for name in [*(hints.get("tags") or []), *(extra_tags or [])]:
            tid = self._lookup("/api/tags/", name)
            if tid is None:
                unresolved.append(f"tag:{name}")
            else:
                tag_ids.append(tid)
        doc = self.get_document(doc_id)
        drop = set()
        for name in remove_tags or []:
            tid = self._lookup("/api/tags/", name)
            if tid is not None:
                drop.add(tid)
        body["tags"] = sorted((set(doc.get("tags", [])) | set(tag_ids)) - drop)
        fields = list(doc.get("custom_fields", []))
        prec = hints.get("date_precision")
        if prec:
            fdef = next((f for f in self._get_json("/api/custom_fields/?page_size=100")["results"]
                         if f["name"] == "Datumsgenauigkeit"), None)
            opt = next((o["id"] for o in (fdef or {}).get("extra_data", {}).get("select_options", []) if o["label"] == prec), None)
            if fdef is None or opt is None:
                unresolved.append(f"date_precision:{prec}")
            else:
                fields = [f for f in fields if f.get("field") != fdef["id"]] + [{"field": fdef["id"], "value": opt}]
                body["custom_fields"] = fields
        sp = self._lookup("/api/storage_paths/", "ATLAS-Standard")
        if sp is not None:
            body["storage_path"] = sp
        self._request("PATCH", f"/api/documents/{int(doc_id)}/", body)
        return {"applied": sorted(body), "unresolved": unresolved}
