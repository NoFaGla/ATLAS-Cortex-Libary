# Betrieb

## Dienste und Ports (alle nur 127.0.0.1)
| Dienst | Port | Start |
|---|---|---|
| Paperless-ngx 3.3.0 | 18000 | Compose (`scripts/02-up-core.sh`) |
| Paperless-GPT v0.30.0 | 18080 | Compose-Profil `ai` (`scripts/05-up-ai.sh`) |
| library-read (HTTP) | 18090 | systemd `atlas-library-read` |
| library-ingest (HTTP) | 18091 | systemd `atlas-library-ingest` |
| library-read (MCP) | stdio | vom Client gestartet: `python3 -m atlas_library.mcp_read` mit `ATLAS_*`-Umgebung |

## Täglich/Regelmäßig
- Status: `scripts/04-status.sh`; Gesundheit/Sicherheit: `sudo ./install.sh validate`.
- Backup mindestens täglich: `scripts/06-backup-sandbox.sh --upload` (Cron/Timer, root). **Hinweis:** Das Backup stoppt die Container kurz (konsistenter Snapshot).
- Alle 30 Tage: Test-Restore auf separater Sandbox (`tests/integration/restore-e2e.sh` zeigt den Ablauf) und `rclone`-Token-Gültigkeit prüfen.
- Registry: `python3 -m atlas_library.cli --registry .../registry.sqlite3 registry-check`.

## Dokumenten-Lifecycle
`Status/Unverarbeitet` → (Paperless-OCR) → ATLAS-ID gesetzt → optional Paperless-GPT (`ATLAS_GPT_ENABLED=1`) → `Status/Verarbeitet` oder `Status/Prüfen`.
`Status/Prüfen` heißt: Mensch muss prüfen (GPT fehlgeschlagen, nichts geändert, unplausibler Titel, unbekannte Taxonomie-Hinweise, nicht verarbeitbare Datei).
Fehlgeschlagene GPT-Dokumente: `System/Paperless-GPT-Failed` entfernen und `System/Paperless-GPT-Queue` setzen, um erneut zu versuchen.

## Korrespondenten (D20)
Paperless-GPT legt **keine** Korrespondenten an (`AUTO_GENERATE_CORRESPONDENTS=false`). Fehlt ein Korrespondent, bleibt das Feld leer und der Dateiname enthält `ohne Korrespondent`.
Neue Korrespondenten legt der Mensch in Paperless an (Matching `Kein`/manuell) und weist sie zu; ab dann kann Paperless-GPT sie für weitere Dokumente vorschlagen.

## Duplikate, Versionen, Löschen
- Bit-identische Duplikate: `library-ingest` meldet `duplicate`; Paperless markiert direkt konsumierte Duplikate. **Nie automatisch gelöscht.**
- Technische Fassung desselben Dokuments → `POST /v1/revision` (gleiche ATLAS-ID, Revision+1, Original bleibt als Version). Fachlich neues Dokument → neuer Ingest.
- Löschen passiert nur durch Menschen in Paperless (Papierkorb, `PAPERLESS_EMPTY_TRASH_DELAY=90`). Die Registry spiegelt `trashed` und danach den Tombstone `deleted`;
  ATLAS-IDs werden nie wiederverwendet.

## Störungen
| Symptom | Maßnahme |
|---|---|
| Dokument bleibt `pending` | `reconcile` meldet `stale`: Datei prüfen (Paperless-Fehlerlog/„consume“-Ordner), nicht löschen; ggf. neu ingestieren |
| GPT hängt (kein Fortschritt, LLM antwortet nicht) | `docker compose --profile ai restart paperless-gpt` (getestet: Erholung nach Neustart) |
| library-read liefert `integrity_error` | Original/Hash passen nicht → Backup-Vergleich, **nicht** Hash in der Registry ändern |
| `revision_mismatch` | gepinnte Referenz ist veraltet; `pinned_revision_known=true` → ältere Fassung per gepinnter Referenz weiterhin abrufbar |
