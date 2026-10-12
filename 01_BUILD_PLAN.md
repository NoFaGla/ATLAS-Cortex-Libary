# Buildplan M03-CORTEX-LIBRARY-SANDBOX

## Status (Cloud-Abschluss 2026-10-12)

Maßgeblich: `docs/RELEASE_GATES.md` (Gate-Status), `docs/TESTREPORT.md` (Nachweise), `docs/AUDIT.md` (Befunde/offene Punkte), `docs/DEVIATIONS.md`,
`docs/INSTALL.md`, `docs/OPERATIONS.md`, `docs/RECOVERY.md`, `docs/SECURITY.md`, `docs/INTERFACES.md`.
Die Gates A–K sind in isolierter Cloud-Umgebung automatisiert durchgespielt (`tests/run-all.sh`); Installation läuft über `./install.sh`.
Offen/extern: echter LLM (G5b), echtes OneDrive (G6b), Upstream-CVE-Bereinigung (G7b), Abnahme auf ATLAS (G10). **Gate L (Produktionsrelease) ist nicht erfüllt.**

## Gate A — Preflight

```bash
bash scripts/00-preflight.sh
```

STOP bei:

- Docker/Compose nicht verfügbar
- unerwarteten produktiven Daten unter Sandbox-Pfaden
- weniger als 20 GiB freiem Platz
- Port 18000 oder 18080 belegt
- vorhandener `m03-sandbox`-Stack unbekannter Herkunft

`rclone` und `rsync` sind für den Core kein Blocker, aber vor Backup erforderlich.

## Gate B — Bootstrap

```bash
sudo bash scripts/01-bootstrap.sh
```

Erzeugt Sandbox-Pfade und zufällige Secrets, sofern noch nicht vorhanden.

## Gate C — Core

```bash
sudo /opt/atlas-sandbox/module03/scripts/02-up-core.sh
```

Startet nur PostgreSQL, Valkey und Paperless. Paperless-GPT bleibt aus.

## Gate D — API-Token

```bash
sudo /opt/atlas-sandbox/module03/scripts/03-create-api-token.sh
```

Der Token wird nur in `/etc/atlas/secrets/module03-sandbox/paperless-gpt.env` abgelegt.

## Gate E — Paperless-GPT

1. `/etc/atlas/secrets/module03-sandbox/paperless-gpt.env` bearbeiten.
2. Provider (`anthropic` oder `openai`) und Modell setzen.
3. API-Key eintragen.
4. keine automatische Dokumenttyp-Erzeugung aktivieren.

Dann:

```bash
sudo /opt/atlas-sandbox/module03/scripts/05-up-ai.sh
```

Wenn das gepinnte v0.29.0-Image (Digest siehe `VERSION_LOCK.md`) nicht pullbar ist: STOP. Nicht auf `latest` wechseln. Version bewusst prüfen und dokumentieren.

## Gate F — Minimal-Taxonomie

Dokumenttypen: Abrechnung, Vertrag, Bescheid, Bescheinigung, Zeugnis, Urkunde, Rechnung, Korrespondenz, Sonstiges Dokument.

Tags:

```text
Status/Unverarbeitet
Status/Prüfen
Status/Verarbeitet
Kontext/Privat
Kontext/Arbeit
Kontext/Wohnen
Thema/Finanzen
Thema/Steuern
Thema/Wohnen
```

Custom Fields:

- ATLAS-ID (Text)
- Bezugszeitraum von/bis (Date)
- Gültig ab/bis (Date)
- Aktenzeichen (Text)
- Vertragsnummer (Text)
- Rechnungsnummer (Text)
- Betrag (Monetary)
- Fälligkeitsdatum (Date)
- Verknüpfte Dokumente (Document Link)

## Gate G — Testdaten

Siehe `tests/TESTDATA_MANIFEST.csv`. Nur Kopien verwenden.

## Gate H — Core-/GPT-Abnahme

Siehe `tests/TESTPLAN.md`.

## Gate I — ATLAS-Erweiterungen

Implementiert (Python-Paket `atlas_library`, Sandbox-Referenz; Details `docs/INTERFACES.md`):

- Registry
- `library-read`
- `library-ingest`
- Asset Resolver

Spezifikation unter `services/`. Die Dienste (`atlas-library-read-http`, `atlas-library-read-mcp`, `atlas-library-ingest-http`) sind noch
nicht als systemd-/Compose-Dienste verpackt (siehe TODO in `docs/AUDIT.md`).

Taxonomie anlegen (Gate F), nach `03-create-api-token.sh` mit Admin-Token:

```bash
ATLAS_PAPERLESS_URL=http://127.0.0.1:18000 ATLAS_PAPERLESS_ADMIN_TOKEN_FILE=<datei> \
  python3 -m atlas_library.cli --registry /var/lib/atlas-sandbox/module03/registry/registry.sqlite3 taxonomy
```

## Gate J — Backup

```bash
sudo /opt/atlas-sandbox/module03/scripts/06-backup-sandbox.sh
sudo /opt/atlas-sandbox/module03/scripts/06-backup-sandbox.sh --upload
```

Backup enthält logischen Paperless-Export, pg_dump, rohe Pfade, Docker-Volumes, Assets, Registry, Config und **sämtliche Sandbox-Secrets**.

## Gate K — Destructive Restore

```bash
sudo /opt/atlas-sandbox/module03/scripts/07-destroy-sandbox.sh --i-understand-this-deletes-the-sandbox
```

Danach Cloud-Backup lokal holen oder eine bewusst bereitgelegte Testkopie verwenden und:

```bash
sudo bash scripts/08-restore-sandbox.sh /pfad/zum/current-backup --i-understand-this-replaces-the-sandbox
```

## Gate L — Referenzrelease

Nur bei vollständigem PASS:

1. Versionen/Digests dokumentieren.
2. Abweichungen dokumentieren.
3. `ATLAS_Modul_03_Cortex-Library.md` erstellen.
4. danach Modul 02 um Library-Anbindung erweitern.
