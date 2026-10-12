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
| offen | Paperless-GPT: Umgebungsvariablennamen (`LLM_PROVIDER`, `AUTO_TAG_COMPLETE`, `FAIL_TAG`, …) sind nur gegen das Image-Manifest, nicht gegen die Doku/Laufzeit verifiziert; Funktionstest braucht LLM-Zugang. | BLOCKED |
| offen | `01-bootstrap.sh` kopiert bei fehlendem rsync auch `.git` nach `/opt/...`. Harmlos, aber unsauber. | offen (niedrig) |
| offen | Dateinamensschema/Datumspräzision (`{{ created }}` liefert immer einen Tag) ist ungeklärt. | offen (braucht Paperless-Test mit Testdokumenten, Gate G/H) |
| offen | Postgres-Image-Pull von Docker Hub lief in der Cloud-Umgebung in HTTP 429; Image wurde über `mirror.gcr.io` bezogen und lokal getaggt (gleicher Tag `postgres:18`). Digests nicht gepinnt. | offen: Digest-Pinning vor Release |

## Priorisierte TODO-Liste (nächste Schritte)
1. Digests der vier Images in `VERSION_LOCK.md` ergänzen.
2. Taxonomie (Gate F) per API-Skript anlegen und im Core-Test prüfen (Dokumenttypen, Tags, Custom Fields inkl. ATLAS-ID).
3. Synthetische Testdokumente T01–T14 generieren (PDF mit deutschem Text, schlechter Scan, Duplikat, Fassungen) und Plan §2/§4/§5 abarbeiten.
4. Paperless-GPT-Funktionstest mit freigegebenem Testkonto/Dummy-Endpoint.
5. HTTP-/MCP-Schicht für `library-read` (Loopback, Token) – aktuell nur Python-API.
6. Backup→Destroy→Restore auf separater Sandbox (braucht ausdrückliche Freigabe), rclone-crypt-Test mit Testremote.
