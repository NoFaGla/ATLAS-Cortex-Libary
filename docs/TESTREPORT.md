# Testbericht M03 (Cloud-Umgebung, 2026-10-12)

Legende: PASS = ausgeführt und erfolgreich · FAIL · BLOCKED = nicht ausführbar · NOT RUN.
Umgebung: Claude-Code-Cloud-Container, Docker 29.8.2 (dockerd manuell gestartet), Compose 5.6.0, Python 3.13. Nur synthetische Daten.

| Bereich | Test | Status | Nachweis / Anmerkung |
|---|---|---|---|
| Archiv | ZIP-Integrität, keine unsicheren Pfade, Extraktion identisch (`diff -r`) | PASS | `unzip -t`, Pfadprüfung |
| Statik | `bash -n` + shellcheck (alle Skripte) | PASS | clean |
| Statik | `docker compose --profile ai config` (Dummy-Secrets), Ports nur 127.0.0.1, keine `latest`-Tags | PASS | pytest `test_repo_static` |
| Statik | Secret-/Private-File-Scan der getrackten Dateien | PASS | pytest |
| Version | Manifest `paperless-ngx:3.3.0`, `paperless-gpt:v0.29.0` auf ghcr.io vorhanden | PASS | Registry-API (`0.29.0` ohne v: 404) |
| Unit | UUIDv7, Referenzparser, Registry (ok/revision_mismatch/trashed/deleted/unknown, Tombstone, Revisionen) | PASS | 31 pytest-Tests gesamt |
| Unit | Asset Store (exakte Datei, Hash-Integrität, Traversal/Symlink-Abwehr) | PASS | pytest |
| Unit | library-read (nur GET, Hash-Prüfung des Originals, keine Mutations-API) | PASS | gegen lokalen **Fake**-Paperless-Server, nicht gegen echtes Paperless |
| Unit | library-ingest (Auth, Typ/Größe, Dateinamen, Duplikat ohne Löschung, Hinweis-Priorität, Reconcile/ATLAS-ID-Feld) | PASS | Fake-Paperless |
| Integration | Core-Stack real: API, PostgreSQL healthy, Valkey, Port nur Loopback, Adminlogin, Upload+OCR/Index, Original bit-identisch, Neustart ohne Datenverlust, `document_sanity_checker` | PASS | `tests/integration/core-smoke.sh` (Paperless 3.3.0 bestätigt) |
| Skripte | `00-preflight` (rclone/rsync nur INFO), `01-bootstrap` (Rechte 0700/0600), `02-up-core`, `03-create-api-token`, `04-status` | PASS | real ausgeführt in Wegwerf-Container |
| Backup | `06-backup-sandbox.sh` lokal: Export, pg_dump (767 TOC-Einträge, `pg_restore -l`), Volumes, Secrets, SHA256SUMS verifiziert | PASS | ohne `--upload` |
| Backup | `--upload` (rclone crypt), `rclone check` | BLOCKED | kein rclone, kein OneDrive/Zugangsdaten |
| Restore | `07-destroy` / `08-restore` / `09-post-restore-check` | NOT RUN | destruktiv, keine ausdrückliche Freigabe |
| GPT | Paperless-GPT Image pullbar | PASS | Pull erfolgreich |
| GPT | Paperless-GPT Start, API-Verbindung, Titel/Datum/Korrespondent/Custom Fields | BLOCKED | kein LLM-Zugang / Testkonto |
| Plan | Taxonomie, Dateinamen, Duplikate/Versionen in Paperless, OCR-Qualität (T01–T14) | NOT RUN | Testdokumente fehlen noch |
| Plan | Cloudflare Access, Hardware-/Performance-Test, OneDrive-Restore | BLOCKED | nur auf echtem ATLAS-Server |
| Release | Reproduzierbares ZIP (`10-build-release.sh`), zweimal gebaut → identische SHA-256 | PASS | Manifest + `.sha256`; **kein Deployment**, Gate L nicht erfüllt |

Cloud-grün ≠ produktionsreif (CLOUD_WORKFLOW.md). Muss-Kriterien „verschlüsseltes Vollbackup“ und „kompletter Restore PASS“ sind NICHT erfüllt.
