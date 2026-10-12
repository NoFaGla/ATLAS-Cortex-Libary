"""Vereinbarte Minimal-Taxonomie (01_BUILD_PLAN.md Gate F), idempotent per Paperless-API anlegen.

Ausschließlich Anlegen fehlender Objekte; bestehende werden nie verändert oder gelöscht.
``matching_algorithm=0`` (kein automatisches Matching) verhindert stille Auto-Zuordnung durch Paperless.
"""
from __future__ import annotations

import json

from .paperless import PaperlessError, ReadClient

DOCUMENT_TYPES = ["Abrechnung", "Vertrag", "Bescheid", "Bescheinigung", "Zeugnis", "Urkunde", "Rechnung",
                  "Korrespondenz", "Sonstiges Dokument"]
TAGS = ["Status/Unverarbeitet", "Status/Prüfen", "Status/Verarbeitet", "Kontext/Privat", "Kontext/Arbeit",
        "Kontext/Wohnen", "Thema/Finanzen", "Thema/Steuern", "Thema/Wohnen",
        # Arbeits-Tags von Paperless-GPT (siehe compose/docker-compose.yml)
        "System/Paperless-GPT-Manual", "System/Paperless-GPT-Queue", "System/Paperless-GPT-Done",
        "System/Paperless-GPT-Failed"]
# (Name, data_type, extra_data)
CUSTOM_FIELDS = [
    ("ATLAS-ID", "string", None),
    ("Bezugszeitraum von", "date", None),
    ("Bezugszeitraum bis", "date", None),
    ("Gültig ab", "date", None),
    ("Gültig bis", "date", None),
    ("Aktenzeichen", "string", None),
    ("Vertragsnummer", "string", None),
    ("Rechnungsnummer", "string", None),
    ("Betrag", "monetary", None),
    ("Fälligkeitsdatum", "date", None),
    ("Verknüpfte Dokumente", "documentlink", None),
    # Datumspräzision: Paperless kennt nur volle Daten. Bei Monats-/Jahresangaben wird created auf den
    # ersten Tag gesetzt und die Genauigkeit hier festgehalten (siehe docs/DATUMSGENAUIGKEIT.md).
    ("Datumsgenauigkeit", "select", {"select_options": [{"label": "Tag"}, {"label": "Monat"}, {"label": "Jahr"}]}),
]


# Dateiname: YYYY[-MM[-DD]] - Korrespondent - Dokumenttyp - Titel. Monat/Tag nur, wenn die Datumsgenauigkeit es hergibt
# (Custom Field "Datumsgenauigkeit"; ohne Eintrag gilt "Tag"). Fehlt Korrespondent/Typ, steht ein expliziter Platzhalter.
_CF = "(custom_fields | get_cf_value('Datumsgenauigkeit', 'Tag'))"
FILENAME_TEMPLATE = (
    "{{ created_year }}{% if " + _CF + " in ('Tag', 'Monat') %}-{{ created_month }}{% endif %}"
    "{% if " + _CF + " == 'Tag' %}-{{ created_day }}{% endif %}"
    " - {{ correspondent or 'ohne Korrespondent' }} - {{ document_type or 'ohne Typ' }} - {{ title }}"
)
STORAGE_PATH_NAME = "ATLAS-Standard"


class AdminClient(ReadClient):
    """Nur für Setup-Werkzeuge; library-read/-ingest verwenden diese Klasse nicht."""

    def post(self, path: str, body: dict) -> dict:
        # owner=None: Taxonomie ist global sichtbar. Sonst gehören die Objekte dem anlegenden Admin und sind für die
        # Least-Privilege-Dienstkonten (library-read/-ingest) unsichtbar (im E2E-Test real beobachtet).
        raw, _ = self._request("POST", path, {"owner": None, **body})
        return json.loads(raw)

    def list_all(self, path: str) -> list[dict]:
        out, url = [], f"{path}?page_size=100"
        while url:
            data = self._get_json(url)
            out += data["results"]
            nxt = data.get("next")
            url = nxt.replace(self.base, "") if nxt else None
        return out


def apply_taxonomy(client: AdminClient) -> dict[str, list[str]]:
    """Legt fehlende Objekte an. Gibt {'created': [...], 'existing': [...]} zurück."""
    report: dict[str, list[str]] = {"created": [], "existing": []}
    have_types = {d["name"] for d in client.list_all("/api/document_types/")}
    for name in DOCUMENT_TYPES:
        if name in have_types:
            report["existing"].append(f"type:{name}"); continue
        client.post("/api/document_types/", {"name": name, "matching_algorithm": 0})
        report["created"].append(f"type:{name}")
    have_tags = {t["name"] for t in client.list_all("/api/tags/")}
    for name in TAGS:
        if name in have_tags:
            report["existing"].append(f"tag:{name}"); continue
        client.post("/api/tags/", {"name": name, "matching_algorithm": 0, "is_inbox_tag": False})
        report["created"].append(f"tag:{name}")
    have_fields = {f["name"] for f in client.list_all("/api/custom_fields/")}
    for name, dtype, extra in CUSTOM_FIELDS:
        if name in have_fields:
            report["existing"].append(f"field:{name}"); continue
        body = {"name": name, "data_type": dtype}
        if extra:
            body["extra_data"] = extra
        try:
            client.post("/api/custom_fields/", body)
        except PaperlessError as exc:
            raise PaperlessError(f"Custom Field {name!r} ({dtype}) konnte nicht angelegt werden: {exc}") from exc
        report["created"].append(f"field:{name}")
    if STORAGE_PATH_NAME in {sp["name"] for sp in client.list_all("/api/storage_paths/")}:
        report["existing"].append(f"storage_path:{STORAGE_PATH_NAME}")
    else:
        client.post("/api/storage_paths/", {"name": STORAGE_PATH_NAME, "path": FILENAME_TEMPLATE, "matching_algorithm": 0})
        report["created"].append(f"storage_path:{STORAGE_PATH_NAME}")
    return report
