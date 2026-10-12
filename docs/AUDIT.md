# Audit M03 Cortex-Library (Stand 2026-10-12, Abschluss der Cloud-Phase)

Status: **behoben** · **akzeptiert** (bewusst, begründet) · **offen** · **extern** (nur auf ATLAS/mit Konto lösbar).

## Befunde aus Phase 0/1 (alle behoben)
IPv6-Bind von Paperless 3.3.0; Restore ohne Bestätigungsschalter; Upload ohne Crypt-Pflicht; GPT-Tag `v0.29.0`; `USERMAP_UID/GID`; Prüfsummen vor Destroy;
`umask` im Staging; `.gitignore`; Valkey-Healthcheck; falsches PASS beim Loopback-Test (`ss` fehlte); Taxonomie-`owner` (unsichtbar für Dienstkonten);
Consume-Dateien nicht lesbar für Paperless; `OCR_PROVIDER=llm` ohne Vision-Modell; Datumsgenauigkeit/Dateinamen (`docs/DATUMSGENAUIGKEIT.md`).

## Neue Befunde in dieser Phase
| Prio | Befund | Status |
|---|---|---|
| P1 | `SHA256SUMS` enthielt absolute Pfade → nach Cloud-Download an anderem Ort wertlos | **behoben** (relative Pfade) |
| P1 | `rclone sync` repariert bei Cloud-Bit-Rot (gleiche Größe/Zeit) nichts; `check --checksum` bei Crypt unzuverlässig | **behoben** (Verifikation per Download, Reparatur-Upload mit `--ignore-times`) |
| P1 | Unterbrochener Upload konnte ein scheinbar gültiges Backup hinterlassen | **behoben** (Daten zuerst, `SHA256SUMS` zuletzt; Restore prüft Summen + Dateianzahl) — getestet |
| P1 | Race: gleichzeitiger Import desselben Dokuments konnte zwei ATLAS-IDs erzeugen | **behoben** (`BEGIN IMMEDIATE`, 12-Thread-Test) |
| P1 | Paperless-GPT erzeugte bei Chat-Prosa einen **Müll-Korrespondenten** (echter FAIL im Mock-Test) | **behoben** (Plausibilitätsschranke → `Status/Prüfen`); seit D20 entstehen solche Objekte gar nicht mehr; Altbestände räumt der Mensch auf |
| P2 | GPT meldet leere/abgeschnittene LLM-Antworten als „Done“ | **behoben** (D21) |
| P2 | Hängender LLM-Endpunkt blockiert GPT-Worker dauerhaft (kein Client-Timeout konfigurierbar) | **akzeptiert/dokumentiert**: Dokument bleibt unverändert in der Queue; Erholung per `restart paperless-gpt` getestet. **Offen:** externer Watchdog (siehe unten) |
| P2 | `06-backup` meldete „fertig“, während Container noch starteten | **behoben** (D15) |
| P2 | `upgrade` aus der installierten Kopie hätte die eigenen Quellen gelöscht | **behoben** (Guard + Kopieren-dann-Tauschen) |
| P2 | `14-security-check.sh`: Quoting-Fehler im eingebetteten Python (vom Installer-`validate` entdeckt, nicht still) | **behoben** |
| P2 | CI-Runner-UID 1001 ≠ 1000: Paperless konnte importierte Dateien nicht lesen | **behoben** (Besitzer vom Consume-Ordner / `ATLAS_CONSUME_UID`) |
| P3 | `sanitize_filename` kürzte die Dateiendung weg | **behoben** |
| P3 | Dienste meldeten Worker-Fehler nicht | **behoben** (nur Exception-Typ auf stderr, keine Inhalte) |
| – | Restore-Guards haben im Test korrekt abgebrochen (fremde Container/Volumes durch parallelen Dev-Stack) | funktioniert wie vorgesehen |

## Sicherheit / Abhängigkeiten
- bandit: 0 Funde (2 begründete `nosec`). pip-audit: keine bekannten Schwachstellen (Paket ohne Laufzeitabhängigkeiten).
- Trivy (`docs/SECURITY_SCAN.md`): Upstream-Images mit fixbaren HIGH-Funden (paperless-ngx 9, paperless-gpt 10, postgres 24 + 1 CRITICAL in `gosu`, valkey 0). **offen/akzeptiert bis zum bewussten Digest-Update** vor Produktivnutzung.
- Secret-Scan über die gesamte Git-Historie: sauber. CI ohne Secrets.

## Offen / extern
| Punkt | Status |
|---|---|
| Echter LLM-Test (OpenAI/Anthropic) | **extern/BLOCKED** — Skript vorbereitet (`gpt-real-llm.sh`, `docs/GPT_REAL_LLM_TEST.md`) |
| Echter OneDrive-Upload/-Restore | **extern/BLOCKED** — Konfiguration + gesamte Kette mit lokalem Crypt-Remote getestet |
| Cloudflare Access live (Tunnel, IdP/MFA, Durchsetzung) | **extern** — Konfiguration automatisch geprüft |
| Hardware-/Performance-/Lasttest, Host-Härtung auf ATLAS | **extern** |
| systemd-Dienste real starten (kein systemd im Testcontainer) | **extern** — Units statisch + `systemd-analyze` (Exposure 1.5) geprüft; Dienste als Prozesse E2E-getestet |
| GPT-Watchdog bei hängendem LLM | **offen** (Empfehlung: systemd-Timer, der `System/Paperless-GPT-Queue`-Dokumente älter als N Minuten erkennt und `restart` auslöst) |
| Entscheidung D20 (Korrespondenten automatisch anlegen) | **entschieden: nein** (`AUTO_GENERATE_CORRESPONDENTS=false`, siehe `DEVIATIONS.md`) |
| Reale Scans (OCR-Qualität), Jahres-/Mehrsprachigkeitsfälle jenseits Deutsch/Englisch | **offen** |
| `01-bootstrap.sh` kopiert bei fehlendem rsync `.git` mit | offen (niedrig) |
| Semantische Duplikate (zweiter Scan) | akzeptiert: eigener Eintrag, Mensch entscheidet |
