# Festgezogene Architekturentscheidungen

## Trennung

- **Cortex** = Wissen, Synthesen, Wiki, qmd, MCP.
- **Cortex-Library** = Originaldokumente + Assets.
- Originaldokumente werden nicht zu normalen Cortex-Markdown-Dateien.

## Dokumente

- Paperless-ngx ist das primäre DMS.
- PostgreSQL als Datenbank, Valkey als Broker.
- Paperless-GPT ist Enrichment/OCR-/Klassifikations-Erweiterung, nicht Dokumentenwahrheit.
- Originale werden zuerst archiviert; KI entscheidet nicht, ob etwas archivierungswürdig ist.

## Lifecycle

```text
Unverarbeitet -> OCR -> ATLAS-ID -> Paperless-GPT -> Verarbeitet | Prüfen
```

## IDs

- logische Identität: UUIDv7
- Referenz: `atlas-library://<uuidv7>`
- konkrete Fassung: `atlas-library://<uuidv7>@sha256:<hash>`
- Paperless-interne ID ist nicht die externe Identität.

## Metadaten

- Dokumenttyp = was ist es?
- Korrespondent = mit wem/von wem?
- Tags = Kontext/Thema/Status
- Custom Fields = strukturierte Fakten
- universell verpflichtend: `ATLAS-ID`

## Dateinamen

Angenommenes Schema:

```text
YYYY-MM[-DD] - Korrespondent - Dokumenttyp [- Titelrest].ext
```

Der Sandbox-Test muss klären, wie Datumspräzision in Paperless sauber abgebildet wird, ohne künstlich einen unbekannten Tag zu erfinden.

## Duplikate / Versionen

- Duplikate nicht automatisch löschen.
- technische Fassung desselben Dokuments = gleiche ATLAS-ID, neue Revision.
- fachlich/rechtlich neues Dokument = neue ATLAS-ID.
- KI darf nicht löschen oder Merge erzwingen.

## Zugriff

- Web: Cloudflare Tunnel + Access + Passkey/MFA.
- Admin/SSH: WireGuard + SSH-Key.
- Paperless-GPT nie nackt ins Internet/LAN exponieren.
- Claude/GPT bekommen keine breite Paperless-API; Zugriff später nur über `library-read` / `library-ingest`.

## Assets

Wiederverwendbare Grounding-/Produktionsdateien liegen im separaten Asset Store:

```text
/srv/cortex-library/assets/
```

Dokumente bleiben in Paperless. Assets und Dokumente werden über dieselbe ATLAS-ID-Registry aufgelöst.

## Backup

- OneDrive ist zentrales Offsite-Ziel für **ATLAS vollständig**, inklusive Secrets.
- Cloud-Backup clientseitig verschlüsselt über `rclone crypt`.
- Der Recovery-Key für die Verschlüsselung muss zusätzlich außerhalb ATLAS/OneDrive verfügbar sein.
- Sandbox beweist dies zunächst nur für M03; Produktion erweitert dasselbe Muster auf ganz ATLAS.
