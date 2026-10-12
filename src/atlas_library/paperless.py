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

    def download_original(self, doc_id: str | int) -> bytes:
        raw, _ = self._request("GET", f"/api/documents/{int(doc_id)}/download/?original=true")
        return raw

    def find_by_checksum(self, md5: str) -> list[dict]:
        qs = urllib.parse.urlencode({"checksum__iexact": md5})
        return self._get_json(f"/api/documents/?{qs}").get("results", [])


class WriteClient(ReadClient):
    """Einzige Schreiboperation: ATLAS-ID-Custom-Field setzen. Kein Löschen, Mergen oder Überschreiben von Dateien."""

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
