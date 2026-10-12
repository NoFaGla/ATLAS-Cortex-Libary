# Audit M03 Cortex-Library (Stand 2026-10-12)

## Befunde und Status

| Prio | Befund | Status |
|------|--------|--------|
| P1 | Paperless 3.3.0 startet nicht auf Docker-Hosts ohne IPv6 (Default-Bind `::`, `RuntimeError: Address family not supported`). Real reproduziert. | **behoben** (`PAPERLESS_BIND_ADDR=0.0.0.0`, D4) |
| P1 | `08-restore-sandbox.sh` löschte Sandbox-Pfade (`rm -rf`) ohne Bestätigungsschalter. | **behoben** (D6) |
| P1 | `06 --upload` prüfte nicht, dass `atlascrypt` ein crypt-Remote ist; das Backup enthält alle Sandbox-Secrets → Risiko unverschlüsselten Uploads. | **behoben** (Abbruch, wenn Remote-Typ ≠ `crypt`) |
| P2 | Paperless-GPT-Tag in Doku `0.29.0`, real nur `v0.29.0` vorhanden. | **behoben** (Doku, D3) |
| P2 | Webserver ohne `USERMAP_UID/GID`, obwohl Bootstrap Bind-Mounts auf `HOST_UID` chownt. | **behoben** (D5) |
| P2 | `07-destroy` prüfte die Backup-Prüfsummen nicht vor dem Löschen. | **behoben** (`sha256sum -c`) |
| P2 | Backup-Staging mit Standard-umask (Secrets-Kopie in 0755-Verzeichnissen). | **behoben** (`umask 077`) |
| P3 | `.gitignore` ohne `rclone.conf`, Dumps, Archive. | **behoben** |
| P3 | CI nur Syntax/YAML. | **behoben** (shellcheck, Compose-Config, Secret-Scan, pytest, Core-Integration) |
| P3 | Skripte `03`/`09` überschrieben die Shell-Variable `USER`; SC2015 in `05`. | **behoben** |
| P3 | Valkey ohne Healthcheck (`service_started`). | **behoben** |
| P1 | `core-smoke.sh` und der erste GPT-Test prüften „nur Loopback“ mit `ss`, das im Runner/Container fehlt → **falsches PASS** möglich (in dieser Phase entdeckt). | **behoben** (`assert_loopback_only` über Docker-Port-Zuordnung, Negativtest: erkennt `0.0.0.0`) |
| P1 | Von Admin angelegte Taxonomie gehört dem Admin (`owner`) und ist für Dienstkonten unsichtbar → Hinweise würden still ignoriert. | **behoben** (D12) |
| P1 | CI-Fehler Run #2/#3: SC2015 in `07-destroy` (neuere shellcheck-Version). | **behoben** |
| P2 | Paperless-Auto-Datum erfindet/rät Tage (`2026-02-01` statt `28.02.2026`), Dateiname `none`-Platzhalter, `/` im Titel → Unterverzeichnis. | **behoben/entschärft** (`docs/DATUMSGENAUIGKEIT.md`) |
| P2 | Consume-Datei muss für den Paperless-Benutzer lesbar sein (root-owned 0640 wurde nicht konsumiert). | **behoben** (`consume_owner`, im Betrieb Dienst als `HOST_UID`) |
| P2 | Paperless-GPT-Variablennamen gegen Upstream-README v0.29.0 geprüft; `OCR_PROVIDER=llm` ohne Vision-Modell fehlerhaft. | **behoben** (D8) |
| offen | Paperless-GPT: LLM-gestützte Anreicherung ungetestet (kein LLM-Zugang). Image-Default `OCR_PROVIDER=llm` deaktiviert OCR nur mit Warnung. | BLOCKED |
| offen | `01-bootstrap.sh` kopiert bei fehlendem rsync auch `.git` nach `/opt/...`. | offen (niedrig) |
| offen | Semantische Duplikate (T12 zweiter Scan) werden nicht automatisch erkannt – nur bit-identische. Bewusst: Mensch entscheidet, keine KI-Löschung/Merge. | akzeptiert |
| offen | `rclone`-crypt-Upload/`rclone check` und OneDrive-Restore ungetestet (kein rclone/Konto). | BLOCKED |
| offen | `library-read`/`-ingest` laufen noch nicht als Systemdienste (kein Compose-/systemd-Unit, kein Cloudflare Access). | offen |
| offen | Postgres-Pull von Docker Hub lief in der Cloud in HTTP 429; Digest ist identisch zum `mirror.gcr.io`-Pull (verifiziert). | akzeptiert (D11) |

## Priorisierte TODO-Liste (nächste Schritte)
1. LLM-Testkonto/Dummy-Endpoint für Paperless-GPT-Funktionstest (Titel/Datum/Korrespondent/Custom Fields, Fehlerstatus statt Endlosschleife).
2. rclone-crypt-Upload + `rclone check` + Cloud-Restore gegen Testremote (lokal `crypt` über `local`-Backend möglich → als nächster Schritt prüfen).
3. systemd-Units/Compose-Dienste für library-read/-ingest (Loopback, eigene Benutzer), Cloudflare Access vor den UIs.
4. Echte-Scan-Qualität (OCR) mit anonymisierten Beispielen; Jahres-Genauigkeit mit Testdokument.
5. Hardware-/Performance-Test und Abnahme auf dem ATLAS-Server (Gate L).
