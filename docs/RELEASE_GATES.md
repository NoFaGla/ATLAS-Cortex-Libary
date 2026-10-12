# Release-Gates M03

Regel: Ein **Produktionsrelease (Gate L)** ist erst zulässig, wenn alle Gates PASS sind. Heute: **Release-Kandidat** (RC), nicht produktionsreif.

| Gate | Inhalt | Status | Nachweis |
|---|---|---|---|
| G1 Repo & Statik | ZIP-Extraktion, shellcheck, Compose, Digest-Pins, keine Secrets (inkl. Historie), bandit, pip-audit | **PASS** | `tests/run-all.sh`, CI `static` |
| G2 Core | Paperless 3.3.0 + PG 18 + Valkey 9: Start, Login, Upload/OCR, Neustart, Sanity-Check, nur Loopback | **PASS** | `core-smoke.sh` (9 Prüfungen) |
| G3 Dokumente | Taxonomie, T01–T14 + Grenzfälle, OCR, Dateinamen/Datumsgenauigkeit, Duplikate, Versionen, UUIDv7, SHA-Referenzen, Tombstones | **PASS** | `tests/e2e/test_e2e.py` (17 Tests, echtes Paperless) |
| G4 Schnittstellen & Rechte | library-read (HTTP/MCP), library-ingest, Asset Store, Auth, Least Privilege (403 bei Schreib-/Löschversuch), ungültige Eingaben | **PASS** | E2E + Unit (62) + `services_check.py` |
| G5 Paperless-GPT | Start/Verbindung/Loopback; Kommunikation, Metadaten, Fehlerpfade, Erholung gegen Mock-LLM | **PASS** (Mock) | `gpt-smoke.sh`, `run-gpt-mock.sh` (12 Szenarien) |
| G5b Paperless-GPT mit echtem LLM | Qualität/Kosten mit OpenAI oder Anthropic | **BLOCKED** | `gpt-real-llm.sh` vorbereitet |
| G6 Backup & Restore (lokales Crypt-Remote) | Verschlüsselung Namen/Inhalt, Upload/Download, falsches Passwort, Korruption, Abbruch, Recovery-Key, Totalverlust-Restore | **PASS** | `rclone-crypt.sh` (22), `restore-e2e.sh` |
| G6b Echtes OneDrive | Auth, Limits, Restore aus echtem OneDrive | **BLOCKED** | `docs/ONEDRIVE.md` |
| G7 Sicherheit/Infra (automatisierbar) | Container-Isolation live, Secret-Rechte, systemd-Härtung, Cloudflare-Konfigurationsprüfung, Image-Scan dokumentiert | **PASS** mit offenen Upstream-Funden | `14-security-check.sh`, `test_deploy.py`, `SECURITY_SCAN.md` |
| G7b Upstream-CVEs bereinigt | Digest-Update + Rescan | **OFFEN** | `SECURITY_SCAN.md` |
| G8 Installer/Upgrade/Recovery | preflight/install/validate/upgrade/recover inkl. Verweigerungsfälle, Datenerhalt | **PASS** (Sandbox, Container-Host) | `restore-e2e.sh` |
| G9 Reproduzierbares Release & CI | zweimal gleiche SHA-256, Manifest-Verifikation + Manipulationstest, Artefakt | **PASS** (lokal); CI-Lauf siehe PR | `10-build-release.sh`, CI-Job `release` |
| G10 Abnahme auf ATLAS | Hardware/Performance, Cloudflare Access live, systemd real, OneDrive real, echter LLM, Betreiberentscheidungen (D20) | **NOT RUN** | — |

Produktionsfreigabe (Gate L) = G1–G10 PASS + G5b/G6b/G7b erledigt + Benutzerfreigabe. Cloud-grün bedeutet nicht produktionsreif.
