# Testbericht M03 (Cloud-Umgebung, Stand 2026-10-12, Phase 2)

Legende: **PASS** = ausgeführt und erfolgreich · **FAIL** · **BLOCKED** = nicht ausführbar · **NOT RUN**.
Umgebung: Claude-Code-Cloud-Container (Docker 29.8.2, dockerd manuell gestartet), Compose 5.6.0, Python 3.13. Echte Container: Paperless-ngx 3.3.0,
PostgreSQL 18, Valkey 9, Paperless-GPT v0.29.0 (alle per Digest gepinnt). Ausschließlich synthetische Daten. Wegwerf-Umgebung, keine produktiven Pfade.

## Zusammenfassung
| Bereich | Status |
|---|---|
| Statische Prüfungen, Unit-Tests (37) | PASS |
| Core-Stack real (Paperless/PG/Valkey) | PASS |
| E2E gegen echtes Paperless (16 Tests) | PASS |
| Backup → Destroy → Restore → Vergleich | PASS (lokal, ohne Cloud-Upload) |
| Paperless-GPT Start/Verbindung/Loopback | PASS |
| Paperless-GPT LLM-Funktionstest | **BLOCKED** (kein LLM-Zugang) |
| rclone-crypt-Upload / OneDrive-Restore | **BLOCKED** |
| Server-/Hardware-/Cloudflare-Access-Tests | **BLOCKED** (nur auf ATLAS) |
| Gate L / Produktionsreife | **NICHT erreicht** |

## Details
| Bereich | Test | Status | Nachweis |
|---|---|---|---|
| Statik | `bash -n`, shellcheck (scripts + tests/integration) | PASS | clean (lokal v0.11, CI-Runner neuer; SC2015 behoben) |
| Statik | Compose-Config, Ports nur 127.0.0.1, keine `latest`, **Digest-Pins**, nur Sandbox-Pfade, Skript-Rechte, Bestätigungsschalter, Secret-Scan | PASS | `tests/unit/test_repo_static.py` |
| Unit | UUIDv7, Referenzparser, Registry (Status, Tombstone, Revisionen), Asset Store (Traversal/Symlink/Integrität) | PASS | `tests/unit/test_core.py` |
| Unit | HTTP-read (Auth, nur GET, Statuscodes), HTTP-ingest (Auth, Limits, Duplikat), MCP (Protokoll, nur lesende Tools), Bind-Guard | PASS | `tests/unit/test_interfaces.py` (Fake-Paperless) |
| Core | API, PG healthy, Valkey, **Loopback über Docker-Port-Zuordnung**, Login, Upload+OCR, Original bit-identisch, Neustart, `document_sanity_checker` | PASS | `core-smoke.sh` |
| E2E | Taxonomie idempotent (35 Objekte, 2. Lauf 0), keine Auto-Matching (`matching_algorithm=0`) | PASS | `tests/e2e` |
| E2E | ATLAS-ID in jedem Dokument, Registry-Mapping, Tag `Status/Unverarbeitet` | PASS | |
| E2E | OCR deutsch: Umlaute/ß korrekt, 6-seitiges Bild-PDF, schlechter Scan lesbar (128 Zeichen, „Quittung“ erkannt), 2. Scan (PNG) | PASS | Beobachtung `ocr_bad_scan_text` |
| E2E | Originale bit-identisch (SHA-256) nach Import | PASS | |
| E2E | Datumsgenauigkeit + Dateinamen (Tag/Monat, `ohne Typ`, Sonderzeichen, `/` im Titel, Sortierbarkeit) | PASS | `docs/DATUMSGENAUIGKEIT.md` |
| E2E | Keine Überschreibung bei Namenskollision (zwei Dokumente, identische Metadaten → eigene Dateien) | PASS | |
| E2E | Paperless-Auto-Datum ohne Hinweis | PASS (dokumentiert) | Paperless wählte `2026-02-01` statt `28.02.2026` → ATLAS überschreibt per Hinweis |
| E2E | Duplikate: bit-identisch → `duplicate`, nichts geschrieben/gelöscht; direkt konsumiertes Duplikat von Paperless markiert, beide bleiben; 2. Scan = eigene ID | PASS | |
| E2E | Versionen: technische Fassung = gleiche ID/Revision 2; fachlich geänderte = neue ID; **ältere Revision per gepinnter Referenz abrufbar** | PASS | |
| E2E | Unbekannte Taxonomie wird nicht angelegt, Dokument → `Status/Prüfen` | PASS | |
| E2E | Papierkorb → `trashed`, endgültig → Tombstone `deleted`, ID bleibt belegt | PASS | |
| E2E | **Least Privilege**: Dienstkonto `library-read` kann lesen, PATCH/DELETE/POST → 403 | PASS | |
| E2E | library-read HTTP gegen echtes Paperless (Metadaten, Text, Datei hash-geprüft, Suche mehrdeutig, Assets SVG/PNG/Vorlage) | PASS | |
| E2E | library-read MCP (stdio-Subprozess) gegen echtes Paperless | PASS | |
| E2E | library-ingest HTTP gegen echtes Paperless inkl. Reconcile/ATLAS-ID/Dateiname | PASS | |
| Skripte | 00 Preflight, 01 Bootstrap (Rechte 0700/0600), 02 Core, 03 Token, 06 Backup (+SHA256SUMS, Secrets enthalten), 07 Destroy, 08 Restore, 09 Post-Restore-Check | PASS | `restore-e2e.sh` (Guards: keine fremden Container/Volumes, Marker, kein `/srv/cortex`) |
| Restore | Zustand vor/nach identisch: 8 Dokumente (Titel, Datum, Korrespondent, Typ, Tags, Felder, Dateiname, SHA-256, Versionen, Content-Hash), 11 Registry-Einträge, 12 Revisionen, 3 Assets; 8 gepinnte Referenzen lösen auf | PASS | |
| GPT | Image per Digest pullbar, Start ohne Crash-Loop, UI nur 127.0.0.1, Paperless-Verbindung, System-Tags vorhanden | PASS | `gpt-smoke.sh` |
| GPT | LLM-Anreicherung (Titel/Datum/Korrespondent/Custom Fields, Fehlerstatus) | BLOCKED | kein LLM-Zugang; keine Schlüssel im Repo |
| Backup | `--upload`, `rclone crypt`, `rclone check`, Cloud-Restore | BLOCKED | kein rclone/OneDrive; Crypt-Pflicht-Guard im Skript, aber ungetestet |
| Plan | Testplan §3 (GPT-Qualität), §9 Cloudflare Access, echte Scans, Hardware/Performance | BLOCKED / NOT RUN | |
| Release | Reproduzierbares Release-**Kandidaten**-ZIP (zweimal gebaut, identische SHA-256) | PASS | `scripts/10-build-release.sh`; Manifest: `status=RELEASE-CANDIDATE` |

## Korrektur früherer Aussage
Der Loopback-Test in `core-smoke.sh` (Phase 1) nutzte `ss`, das im Testumfeld fehlte, und hätte nie fehlschlagen können. Die statische
Prüfung (Compose-Config) war korrekt; der dynamische Test wurde ersetzt und mit einem Negativtest (`0.0.0.0` wird erkannt) abgesichert.

## Release-Reife
**Nicht produktionsreif.** Offen für Gate L: LLM-Funktionstest, verschlüsselter Offsite-Upload + Cloud-Restore, Dienst-Verpackung (systemd/Compose)
für library-read/-ingest, Cloudflare Access, Hardware-/Performance-Abnahme auf ATLAS, Review der Abweichungen durch den Benutzer.
