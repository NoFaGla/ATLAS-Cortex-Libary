# Testbericht M03 — Cloud-Abschluss (2026-10-12), Stand nach D20 + G7b

Statuswerte: **PASS** tatsächlich ausgeführt und bestanden · **FAIL** ausgeführt, fehlgeschlagen · **BLOCKED** externe Abhängigkeit fehlt · **NOT RUN** nicht ausgeführt.
Umgebung: Claude-Code-Cloud-Container (Docker 29.8.2, Compose 5.6.0, Python 3.13, rclone 1.75.2) **und** GitHub-Actions-Runner (ubuntu-24.04). Echte Container:
Paperless-ngx 3.3.0, PostgreSQL 18, Valkey 9, Paperless-GPT **v0.30.0** (alle per Digest gepinnt; Update von v0.29.0 siehe D22). Ausschließlich synthetische Daten; destruktive Tests nur in Wegwerf-Umgebungen mit Guards.
Reproduktion: `sudo M03_ISOLATED_TEST_ENV=1 bash tests/run-all.sh` (Logs in `$LOGDIR`).

## Nachtrag D20 + G7b (Commit `20a5fbc`)
Änderungen: `AUTO_GENERATE_CORRESPONDENTS=false` (D20), paperless-gpt `v0.29.0` → `v0.30.0` (D22), Sicherheitsscan neu bewertet (`SECURITY_SCAN.md`).
Vollständiger lokaler Lauf (`tests/run-all.sh`, Logs `/tmp/claude-0/logs`) auf dem Endstand: shellcheck, unit (62), bandit, rclone-crypt (22), core-smoke (9), e2e, gpt-smoke (7), **gpt-mock (12, inkl. D20-Prüfung: Korrespondentenmenge nach jedem Szenario unverändert; T02 behält keinen erfundenen Korrespondenten)** = PASS;
`restore-e2e` = PASS (beim Sammellauf zunächst BLOCKED: der Guard „fremde Docker-Volumes“ erkannte ein von mir angelegtes Trivy-Cache-Volume – Volume entfernt, Test einzeln wiederholt, PASS); `gpt-real-llm` = BLOCKED (kein Zugang, erwartet).
Zusätzlich: der GPT-Mock-Lauf wurde vorab mit v0.30.0 per Image-Override ausgeführt (12 passed, 808 s) bevor der Digest übernommen wurde. CI siehe PR #1 (Commit `20a5fbc` bzw. Folgecommit).
Ergebnisse Scan (Trivy 0.58.0, eindeutige CVE-IDs): paperless-ngx 3.3.0 → 3 HIGH · paperless-gpt v0.30.0 → 2 HIGH (vorher 8) · valkey 0 · postgres 18.6 → 1 CRITICAL + 24 HIGH (alle in `gosu`).

## Gesamtergebnis (Lauf auf Commit `2c4cc21`, lokal + CI, vor D20/G7b)
| Suite | Lokal | CI (PR #1) | Umfang |
|---|---|---|---|
| shellcheck (install.sh, scripts, tests) | PASS | PASS | alle Skripte |
| Unit-/Konfigurationstests | PASS | PASS | 62 Tests |
| bandit / pip-audit / Secret-Scan inkl. Git-Historie | PASS | PASS | 0 Funde |
| `rclone-crypt.sh` | PASS | PASS | 22 Prüfungen |
| `core-smoke.sh` | PASS | PASS | 9 Prüfungen |
| E2E gegen echtes Paperless (`tests/e2e/test_e2e.py`) | PASS | PASS | 17 Tests |
| `gpt-smoke.sh` (Start/Verbindung/Loopback) | PASS | PASS | 7 PASS (+1 BLOCKED, s. u.) |
| Paperless-GPT gegen Mock-LLM (`run-gpt-mock.sh`) | PASS | PASS | 12 Tests (~14 min) |
| Installer + Backup + Upgrade + Destroy + Cloud-Restore (`restore-e2e.sh`) | PASS | PASS | 47 Prüfungen |
| Release-Kandidat: reproduzierbar, Manifest, Manipulationstest, Artefakt | PASS (lokal) | PASS | CI-Job `release` |
| Echter LLM (`gpt-real-llm.sh`) | **BLOCKED** | BLOCKED (erwartet, Gate-Job PASS) | kein Zugang/keine Freigabe |
| Echtes OneDrive | **BLOCKED** | – | kein Konto |
| Trivy-Image-Scan | PASS (ausgeführt, Funde dokumentiert) | informativ | siehe `SECURITY_SCAN.md` |

## 1. Backup und Verschlüsselung (`rclone-crypt.sh`, `restore-e2e.sh`)
| Test | Status |
|---|---|
| Setup erzeugt Konfiguration + Recovery-Key (0600), Klartext-Passwort nie in Log/Konfiguration, überschreibt nichts | PASS |
| Dateinamen **und** Verzeichnisnamen im Cloud-Speicher verschlüsselt (kein Klartextname) | PASS |
| Inhalte verschlüsselt (Secret-Marker nirgends im Klartext) | PASS |
| Upload + Verifikation per Rück-Download; Download bit-identisch (inkl. Sonderzeichen-Dateinamen) | PASS |
| Änderung → zweiter Upload; ersetzte Datei als Vorversion erhalten | PASS |
| Falsches Passwort → Restore scheitert, kein Klartext erzeugt | PASS |
| Beschädigte Cloud-Datei erkannt; erneuter Upload repariert sie | PASS |
| Abgeschnittene Cloud-Datei erkannt | PASS |
| Unterbrochener Transfer (SIGKILL) → kein scheinbar gültiges Backup; Wiederaufnahme vollendet; Restore bit-identisch | PASS |
| Konfiguration aus extern gesichertem Recovery-Key neu aufgebaut → Cloud-Restore ohne alte Server-Konfiguration | PASS |
| Guards: Upload in unverschlüsseltes Remote / ohne Dateinamenverschlüsselung verweigert | PASS |
| Alle Sandbox-Secrets im verschlüsselten Backup (im Cloud-Restore wiedergefunden), nicht im Klartext in Cloud/Log | PASS |
| OneDrive-Konfiguration (Dummy-Token) korrekt generiert | PASS (nur Konfiguration) |
| **Echter OneDrive-Upload/-Restore** | **BLOCKED** (Konto/OAuth) |

## 2. Paperless-GPT und LLM
Gegen den lokalen OpenAI-kompatiblen Mock (`tests/mockllm`) mit dem echten, gepinnten GPT-Image und echtem Paperless:
| Szenario | Ergebnis |
|---|---|
| Kommunikation GPT ↔ LLM; Titel, Datum (korrigiert Paperless-Raten `2026-02-01` → `2026-02-28`), Korrespondent, Tags aus der Taxonomie | PASS |
| Dokumenttyp wird nie automatisch gesetzt (0 Typ-Anfragen an das LLM) | PASS |
| Explizite Nutzerhinweise (Korrespondent, Datum, Titel, Tags, Monatsgenauigkeit) haben Vorrang vor dem LLM | PASS |
| ATLAS-ID erhalten, Original bit-identisch, Status `Unverarbeitet → Verarbeitet`, Queue-Tag entfernt | PASS |
| Erfundene Tags/Typen/Datumswerte (`invented`): nichts angelegt, ungültiges Datum verworfen, ausufernder Titel → `Status/Prüfen` | PASS |
| Chat-Prosa statt Wert (`prose`): **zunächst FAIL** (Müll-Korrespondent angelegt) → Plausibilitätsschranke → `Prüfen`, Korrespondent entfernt | PASS (nach Fix) |
| HTTP 500, HTTP 429, ungültiges JSON: 3 Wiederholungen → `Failed` + `Prüfen`, Dokument unverändert, danach keine weiteren Anfragen (keine Endlosschleife) | PASS |
| Leere Antwort, abgeschnittene Antwort: GPT meldet „Done“ → ATLAS-Schranke → `Prüfen` | PASS |
| Hängender Endpunkt (Timeout): Dokument bleibt unverändert in der Queue; Erholung per Neustart des GPT-Containers | PASS (Verhalten dokumentiert; Watchdog offen) |
| Nicht erreichbarer Endpunkt: `Failed`, GPT-Container läuft weiter; Wiederanlauf per Re-Queue funktioniert | PASS |
| Start/Verbindung/Loopback/System-Tags mit gepinntem Image (`gpt-smoke.sh`) | PASS |
| **Qualität mit echtem OpenAI/Anthropic** | **BLOCKED** (`gpt-real-llm.sh` vorbereitet, Exit 77 ohne Freigabe/Schlüssel) |

## 3. Dokumente T01–T14 und Grenzfälle (E2E, echtes Paperless)
Taxonomie idempotent (35 Objekte → 0) · ATLAS-ID in jedem Dokument + Registry-Mapping · OCR deutsch (Umlaute/ß, 6-seitiges Bild-PDF, schlechter Scan: „Quittung“ erkannt) ·
Originale bit-identisch · Datumsgenauigkeit & Dateinamen (Tag/Monat/**Jahr**, Platzhalter, Sonderzeichen, `/` im Titel, Unicode-Dateiname, Sortierbarkeit, Kollision ohne Überschreiben) ·
Duplikate (bit-identisch gemeldet statt gelöscht; direkt konsumiertes von Paperless markiert; zweiter Scan eigener Eintrag; 12-Thread-Race → genau 1 Eintrag) ·
Versionen (technisch = gleiche ID/Revision 2; fachlich neu = neue ID; **ältere gepinnte Revision abrufbar**) · unbekannte Taxonomie nicht angelegt → `Prüfen` ·
Papierkorb → `trashed`, endgültig → Tombstone, ID unwiederverwendbar · nicht verarbeitbare Datei → `stale`, nie gelöscht · UUIDv7 (monoton, Format), Referenz-Fuzzing (SQL-/Pfad-Muster abgewiesen) — **alle PASS**.
Asset Store (SVG/PNG/Vorlage): exakt, Hash-Integrität, Traversal/Symlink-Abwehr — **PASS**.

## 4. Schnittstellen und Rechte
library-read HTTP (Auth, nur GET, 405 bei Schreibmethoden, Statuscodes, Hash-geprüfte Datei, Suche mehrdeutig) · library-read MCP (Protokoll, nur lesende Tools, Subprozess gegen echtes Paperless) ·
library-ingest HTTP (Auth, Größen-/Typlimit, Hinweisvalidierung, Duplikat, Revision, Worker ordnet zu) · **Least Privilege**: `library-read` PATCH/DELETE → 403, `library-ingest` DELETE → 403 — **PASS**
(auch mit den vom Installer erzeugten Konten/Tokens als echte Prozesse).

## 5. Sicherheit und Infrastruktur
| Prüfung | Status |
|---|---|
| Docker-Isolation live (nicht privilegiert, no-new-privileges, keine Caps, kein docker.sock/Wurzel-Mount), Ports nur 127.0.0.1, Digest-Pins | PASS (`14-security-check.sh`, Installer-`validate`) |
| Loopback-Test mit Negativtest (`0.0.0.0` wird erkannt) | PASS |
| Secret-Dateirechte 0700/0600 root | PASS |
| Keine Secrets in Logs/Commits (Historie)/CI-Artefakt/Release-ZIP | PASS |
| systemd-Units: Härtungsdirektiven, `systemd-analyze verify`, Exposure 1.5 | PASS (statisch; **kein Echtstart**) |
| Cloudflare Tunnel/Access: automatische Konfigurationsprüfung (nur Loopback-Ursprung, 404-Catch-all, Passkey/MFA, kein Bypass, Service-Token nur benannt) | PASS (Konfiguration); **Live-Durchsetzung BLOCKED/extern** |
| bandit 0, pip-audit 0 | PASS |
| Trivy auf gepinnten Upstream-Images | ausgeführt; fixbare Funde behoben (gpt 8→2), Rest ohne Upstream-Fix mit Risiko/Maßnahmen dokumentiert → `SECURITY_SCAN.md` (G7b: PASS mit Restrisiko) |

## 6. Installation, Neustart, Upgrade, Recovery (`restore-e2e.sh`, Sandbox im Container-Host)
preflight · install (verweigert Überschreiben) · validate · Neustart (Core-Smoke: Daten erhalten; GPT-Neustart) · upgrade (verweigert ohne Backup / mit 72 h altem Backup / aus installierter Kopie; mit frischem Backup erfolgreich, Daten unverändert) ·
destroy (Pfade, Volumes, Secrets weg) · Cloud-Restore + `recover` (verweigert ohne Bestätigungsschalter) · Zustand vor/nach identisch (Dokumente inkl. Hashes/Versionen/Metadaten/Dateinamen, Registry, Assets) · 8 gepinnte Referenzen lösen auf — **PASS**.
Die Guards (keine fremden Container/Volumes, Marker, kein `/srv/cortex`) haben im Entwicklungsverlauf einmal korrekt abgebrochen und einmal als BLOCKED gemeldet.

## 7. Release
`scripts/10-build-release.sh`: zweimal gebaut → identische SHA-256; `RELEASE_MANIFEST.txt` wird vom Installer geprüft; manipulierte Datei → Preflight lehnt ab; Artefakt `m03-release-candidate` im CI-Job `release`. Status: **RELEASE-CANDIDATE**.

## 8. Während der Tests gefundene und behobene Fehler (Auswahl, vollständig in `docs/AUDIT.md`)
Race beim gleichzeitigen Import · Race zwischen GPT-Updates und Nutzerhinweisen (Ruhezeit) · Müll-Korrespondent bei Prosa-Antworten · „Done“ ohne Inhalt · absolute Pfade in SHA256SUMS · nicht reparierte Cloud-Korruption ·
falsches PASS beim Loopback-Test · Quoting-Fehler in `14-security-check.sh` · Upgrade aus der installierten Kopie · CI-UID 1001 · Backup meldete zu früh „fertig“ · unsichtbare Taxonomie (`owner`).

## 9. Nicht ausgeführt / extern
Echter LLM · echtes OneDrive · Cloudflare live · systemd-Echtstart · Hardware-/Performance-/Lasttest · reale Scans · Auswahl der Betreiberentscheidungen (D20) — siehe `docs/RELEASE_GATES.md` (G5b, G6b, G10).
