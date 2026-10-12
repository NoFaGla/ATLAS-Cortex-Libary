# Dokumentierte Abweichungen von den Spezifikationen

| # | Spec | Abweichung | Begründung |
|---|------|-----------|------------|
| D1 | `services/registry/SCHEMA.md` | Zusätzlicher Status `pending` | Ingest legt die ATLAS-ID vor der Paperless-Konsumierung an; Zuordnung später per MD5 (`reconcile`). |
| D2 | `SCHEMA.md` | Tabelle `revisions` (atlas_id, revision, sha256) | Revisionsgebundene Referenzen müssen ältere Fassungen als „bekannt“ erkennen (`revision_mismatch`, `pinned_revision_known`). |
| D3 | `VERSION_LOCK.md` | Paperless-GPT-Tag ist `v0.29.0`, nicht `0.29.0` | Auf ghcr.io geprüft: `0.29.0` → 404, `v0.29.0` → 200. |
| D4 | `compose/docker-compose.yml` | `PAPERLESS_BIND_ADDR=0.0.0.0` | Paperless 3.3.0 bindet standardmäßig `::`; ohne IPv6 im Container-Host startet der Webserver nicht (real reproduziert). Host-Exposure unverändert nur `127.0.0.1`. |
| D5 | `compose/docker-compose.yml` | `USERMAP_UID/GID` für den Webserver, Valkey-Healthcheck | Bootstrap chownt die Bind-Mounts auf `HOST_UID`; ohne USERMAP liefe Paperless als UID 1000. |
| D6 | `08-restore-sandbox.sh` | Bestätigungsschalter `--i-understand-this-replaces-the-sandbox` | Das Skript löscht Sandbox-Pfade (`rm -rf`) – analog zu Skript 07. |
| D7 | `compose/*.yml` | Alle vier Images zusätzlich per `@sha256:` Digest gepinnt | Reproduzierbarkeit (VERSION_LOCK.md); Digests am 2026-10-12 verifiziert. |
| D8 | `compose/paperless-gpt.env.example` | `OCR_PROVIDER=llm` entfernt; `CREATE_NEW_TAGS=false`, `LISTEN_INTERFACE` ergänzt | `OCR_PROVIDER=llm` verlangt `VISION_LLM_*` (Upstream-README v0.29.0) und widerspricht „Paperless-Standard zuerst“. Image-Default `llm` ohne Vision-Modell deaktiviert OCR nur mit Warnung (real beobachtet). |
| D9 | `PAPERLESS_FILENAME_FORMAT` | Maßgeblich ist der Storage Path `ATLAS-Standard` (Jinja + Feld `Datumsgenauigkeit`) | `{{ created }}` erfindet Tage und liefert `none`; siehe `docs/DATUMSGENAUIGKEIT.md`. |
| D10 | `services/*/SPEC.md` | `library-ingest` hat zusätzlich `ingest_revision` und `sync_lifecycle`; `library-read` erzeugt kein Schreibzugriff | Revisionsbindung und Papierkorb/Tombstone-Spiegelung (Testplan §5/§7). |
| D11 | `scripts/02-up-core.sh` | `pull --ignore-pull-failures` | Registry-Rate-Limits (Docker Hub HTTP 429 real aufgetreten) sollen bei lokal vorhandenen, digest-gepinnten Images nicht abbrechen. |
| D12 | Paperless-Objekte | Taxonomie wird mit `owner=null` angelegt | Sonst für Dienstkonten unsichtbar (E2E-Fund). |
