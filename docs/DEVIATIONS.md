# Dokumentierte Abweichungen von den Spezifikationen

| # | Spec | Abweichung | Begründung |
|---|------|-----------|------------|
| D1 | `services/registry/SCHEMA.md` | Zusätzlicher Status `pending` | Ingest legt die ATLAS-ID vor der Paperless-Konsumierung an; Zuordnung später per MD5 (`reconcile`). |
| D2 | `SCHEMA.md` | Tabelle `revisions` (atlas_id, revision, sha256) | Revisionsgebundene Referenzen müssen ältere Fassungen als „bekannt“ erkennen (`revision_mismatch`, `pinned_revision_known`). |
| D3 | `VERSION_LOCK.md` | Paperless-GPT-Tag ist `v0.29.0`, nicht `0.29.0` | Auf ghcr.io geprüft: `0.29.0` → 404, `v0.29.0` → 200. |
| D4 | `compose/docker-compose.yml` | `PAPERLESS_BIND_ADDR=0.0.0.0` | Paperless 3.3.0 bindet standardmäßig `::`; ohne IPv6 im Container-Host startet der Webserver nicht (real reproduziert). Host-Exposure unverändert nur `127.0.0.1`. |
| D5 | `compose/docker-compose.yml` | `USERMAP_UID/GID` für den Webserver, Valkey-Healthcheck | Bootstrap chownt die Bind-Mounts auf `HOST_UID`; ohne USERMAP liefe Paperless als UID 1000. |
| D6 | `08-restore-sandbox.sh` | Bestätigungsschalter `--i-understand-this-replaces-the-sandbox` | Das Skript löscht Sandbox-Pfade (`rm -rf`) – analog zu Skript 07. |
