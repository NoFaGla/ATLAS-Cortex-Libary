# Sicherheitskonzept M03 (Sandbox-Referenz)

## Kontrollen und ihr Nachweis
| Kontrolle | Umsetzung | Nachweis |
|---|---|---|
| Keine öffentlichen Ports | alle Ports `127.0.0.1`; Zugriff später nur Cloudflare Tunnel + Access | `test_repo_static`, `14-security-check.sh` (live über Docker-Inspect), `assert_loopback_only` (mit Negativtest) |
| Container-Isolation | nicht privilegiert, `no-new-privileges`, keine zusätzlichen Capabilities, kein Host-Netz/PID/IPC, kein `docker.sock`, keine Wurzel-Mounts; DB/Broker ohne veröffentlichte Ports | `14-security-check.sh` im Installer-`validate` (PASS im Restore-E2E), `test_deploy.py` |
| Image-Integrität | alle Images per `@sha256` gepinnt, kein `latest` | `test_images_pinned_by_digest`, Installer-Preflight |
| Secrets | zufällig erzeugt (`secrets`), Dateien 0600/Verzeichnis 0700 (root), Dienste lesen sie via `*_FILE`/systemd `LoadCredential`, nie als Argument/Umgebung im Klartext | `install.sh validate`, `test_deploy.py`, Log-Scans in `rclone-crypt.sh`/`restore-e2e.sh` |
| Keine Secrets im Repo/CI | Secret-Scan über **gesamte Git-Historie**, verbotene Dateien (`rclone.conf`, `*.key`, `.env`, Dumps), CI ohne `secrets.*`, ohne `pull_request_target` | `test_repo_static.py` |
| Least Privilege (Paperless) | Dienstkonten `library-read` (nur `view_*`) und `library-ingest` (ohne Löschrecht) | E2E + `services_check.py`: PATCH/DELETE → 403 |
| library-read | nur GET, Bearer-Token (konstante Zeit), Loopback-Bind-Guard, hash-geprüfte Auslieferung, keine internen Fehlerdetails | Unit-/E2E-Tests |
| library-ingest | Token, Größenlimit vor dem Lesen, Dateityp-Allowlist, Dateinamen-/Titel-Bereinigung, Hinweisfelder nur aus Allowlist, kein Anlegen von Taxonomie, kein Löschen/Überschreiben, atomare Duplikaterkennung | Unit-/E2E-/Concurrency-Tests |
| Backup | `rclone crypt` (Namen + Inhalte), Upload-Guard gegen unverschlüsselte Remotes, Rück-Download-Verifikation, Recovery-Key außerhalb ATLAS | `rclone-crypt.sh`, `restore-e2e.sh` |
| systemd-Härtung | `NoNewPrivileges`, `ProtectSystem=strict`, leere Capability-Bounding-Set, Seccomp-Filter, `IPAddressDeny=any`+`localhost`, kein Schreibzugriff für library-read | `systemd-analyze security --offline`: Exposure 1.5 (OK), Unit-Tests |
| Statische Analyse | bandit (src): 0 Funde; pip-audit (Test-Abhängigkeiten): keine bekannten Schwachstellen; Paket hat **keine Laufzeitabhängigkeiten** | CI-Job `static` |
| Image-Scan | Trivy über gepinnte Upstream-Images | `docs/SECURITY_SCAN.md` |

## Restrisiken / bewusste Grenzen
- **Upstream-Schwachstellen** in den gepinnten Images (HIGH, 1× CRITICAL in `gosu` von postgres) – siehe `SECURITY_SCAN.md`; Updates nur bewusst nach Sandbox-Test.
- **Paperless-GPT hat keine eigene Authentifizierung** (Upstream-Hinweis): nie nackt ins Netz/LAN; nur Loopback + Cloudflare Access.
- **LLM-Ausgaben sind nicht vertrauenswürdig**: sie dürfen nur vorhandene Tags/Typen verwenden (kein Anlegen), keine Dokumenttypen automatisch setzen, Nutzerangaben haben Vorrang, Plausibilitätsprüfung → `Status/Prüfen`. Prompt-Injection in Dokumenten kann Titel/Tags beeinflussen, aber weder löschen noch Dateien ändern.
- Externe LLM-Aufrufe senden Dokumentinhalt an den Anbieter – bei echten Dokumenten Datenschutz prüfen (nicht Teil dieses Tests).
- Das Backup enthält alle Sandbox-Secrets (gewollt) – deshalb nur verschlüsselt extern; der Recovery-Key ist der kritischste Einzelwert.
- Nicht automatisiert prüfbar: Cloudflare-Access-Durchsetzung, OneDrive-Konto-Sicherheit, physische Serversicherheit, Host-Härtung (SSH/WireGuard laut ATLAS-Basis).

## Meldung
Sicherheitsrelevante Funde bitte nicht öffentlich im PR diskutieren, sondern direkt an den Betreiber.
