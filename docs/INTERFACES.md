# Schnittstellen library-read / library-ingest

Alle Dienste binden **standardmäßig nur an 127.0.0.1** (`ATLAS_ALLOW_NON_LOOPBACK=1` nur bewusst, z. B. hinter Cloudflare Access).
Secrets kommen aus `*_FILE`-Variablen, nie aus dem Code. Zugriff auf Paperless nur mit **eigenen Dienstkonten**:

| Dienst | Paperless-Benutzer | Rechte |
|---|---|---|
| library-read | `library-read` | nur `view_*` (Schreiben → 403, E2E-Nachweis) |
| library-ingest | `library-ingest` | `view_*` + `change_document` + `add_document` |
| Taxonomie-Setup | Admin (einmalig) | Objekte mit `owner=null` anlegen |

## library-read (HTTP, nur GET) — `atlas-library-read-http`
Umgebung: `ATLAS_REGISTRY`, `ATLAS_PAPERLESS_URL`, `ATLAS_PAPERLESS_READ_TOKEN[_FILE]`, `ATLAS_READ_TOKEN[_FILE]`, optional `ATLAS_ASSETS`, `ATLAS_READ_HOST/PORT` (18090).
`Authorization: Bearer <token>`; andere Methoden → 405.

| Pfad | Zweck |
|---|---|
| `/v1/resolve?ref=` | ok / revision_mismatch / trashed / deleted / unknown / pending |
| `/v1/documents/search?q=&limit=` | kompakte Treffer, `ambiguous` |
| `/v1/documents/metadata?ref=` | strukturierte Metadaten (zuerst) |
| `/v1/documents/text?ref=&max_chars=` | Volltext, begrenzt |
| `/v1/documents/file?ref=` | Original (Base64, SHA-256 geprüft; gepinnte ältere Revision → genau diese Fassung) |
| `/v1/assets?ref=` | exaktes Asset |

HTTP-Statuscodes: 400 ungültig, 401, 404 unknown, 409 revision_mismatch/pending, 410 trashed/deleted, 413, 502 Integritäts-/Backendfehler.

## library-read (MCP, stdio) — `atlas-library-read-mcp`
JSON-RPC 2.0 (`initialize`, `tools/list`, `tools/call`). Tools: `search_documents`, `resolve_atlas_ref`, `get_document_metadata`,
`get_document_text`, `get_document_file`, `get_asset` (alle `readOnlyHint`). Keine Schreib-/Löschwerkzeuge.

## library-ingest (HTTP) — `atlas-library-ingest-http`
Umgebung: wie oben plus `ATLAS_INGEST_TOKEN[_FILE]`, `ATLAS_PAPERLESS_INGEST_TOKEN[_FILE]`, `ATLAS_CONSUME_DIR`, `ATLAS_STATE_DIR`,
`ATLAS_INGEST_MAX_BYTES`, `ATLAS_INGEST_PORT` (18091), `ATLAS_RECONCILE_INTERVAL`.
- `POST /v1/ingest` Rohkörper = Datei; Header `X-Filename`, optional `X-Hints` (JSON-Liste `{field,value,source}`; Felder: title, created,
  date_precision, correspondent, document_type, tags, notes; Quellen user > extracted > llm).
  Ergebnis `queued` (neue ATLAS-ID, Datei im Consume-Ordner) oder `duplicate` (bit-identisch: nichts abgelegt, nichts gelöscht).
- `POST /v1/revision` (Header `X-Atlas-Id`): neue **technische** Fassung = gleiche ATLAS-ID, neue Revision (Paperless-Version, Original bleibt).
  Fachlich neue Dokumente → `/v1/ingest` (neue ID).
- Hintergrund-Worker: ordnet Paperless-Dokumente per SHA-256 zu, schreibt das Feld `ATLAS-ID`, wendet Hinweise nur mit **vorhandener**
  Taxonomie an (Unbekanntes wird nicht angelegt → Tag `Status/Prüfen`), spiegelt Papierkorb/Löschung als `trashed`/Tombstone.
- Keine Lösch-, Merge- oder Überschreib-Endpunkte; Größenlimit wird vor dem Lesen geprüft.
