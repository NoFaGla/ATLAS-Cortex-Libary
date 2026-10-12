# Claude Code Arbeitsauftrag — ATLAS M03 Cortex-Library

Du arbeitest an einer **Sandbox-Referenzimplementierung**, nicht an Produktion. Lies vor Änderungen in dieser Reihenfolge: `README.md`, `00_DECISIONS.md`, `01_BUILD_PLAN.md`, `VERSION_LOCK.md`, `services/*/*.md`, `tests/TESTPLAN.md`, `CLOUD_WORKFLOW.md`.

## Unverhandelbar
- Kein Zugriff/keine Änderungen an `/srv/cortex`, Modul 00–02 oder produktiven ATLAS-Pfaden.
- Niemals echte Zugangsdaten, Tokens, personenbezogene Originaldokumente oder `.env`-Dateien committen. Nutze synthetische Testdaten.
- Keine ungeschützten öffentlichen Ports; lokale Loopback-Bindung und später Cloudflare Access.
- Keine stillen `latest`-Tags oder Versionsupgrades. Upstream-Kompatibilität prüfen und begründen.
- Keine automatischen Löschungen/Merges; Originale bewahren; Paperless native Funktionen vor Eigenbau.
- Kein behauptetes PASS ohne tatsächlich ausgeführten Test und Log. Docker-unverfügbare Tests als BLOCKED kennzeichnen.
- Backup inkl. Sandbox-Secrets nur verschlüsselt extern; Restore nie auf Produktion.
- Sicherheitskritische/destruktive Befehle nur nach ausdrücklicher Freigabe und Zielpfadkontrolle.

## Ziel und Reihenfolge
1. Repo auditieren: Shell, Compose, Pfade, Secrets, Abhängigkeiten, Versionen. Befunde dokumentieren.
2. Statische GitHub-Actions-CI für Shell, YAML, Secret-Scan, Tests; fehlende Tools als nachvollziehbaren FAIL/BLOCKED melden.
3. Core Paperless/PostgreSQL/Valkey mit synthetischen Daten in geeigneter isolierter Umgebung testen (falls Docker verfügbar).
4. Paperless-GPT getrennt testen, nur mit Dummy-API-Credentials oder freigegebenen Testkonten.
5. Registry UUIDv7, Paperless-ID-Mapping, Asset Store und revisionsfeste Referenzen gemäß Specs implementieren und testen.
6. `library-read` und `library-ingest` mit Least Privilege, sicheren Defaults und automatisierten Tests implementieren.
7. Testplan inkl. Duplicate, Version, Trash/Tombstone, OCR, Dateinamen, Backup und Restore durchgehen. Fehlende Cloud-Infrastruktur offen markieren.
8. Erst bei bestandenem Gate ein installierbares Release-ZIP mit Manifest/Prüfsumme vorbereiten; **kein Deployment** ohne Benutzerfreigabe.

## Kommunikation
Arbeite in kleinen nachvollziehbaren Commits/PRs. Berichte je Phase: Änderungen, echte Tests, PASS/FAIL/BLOCKED, Risiken, nächster Schritt. Stelle Fragen nur bei echten Blockern. Beginne mit Audit und CI, nicht mit Installation auf dem ATLAS-Server.
