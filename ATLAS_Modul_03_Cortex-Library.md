# ATLAS – Modul 03: Cortex-Library

**Status: Release-Kandidat 0.2.0 (nicht produktionsreif).** Maßgeblich für Freigabe: `docs/RELEASE_GATES.md`. Nachweise: `docs/TESTREPORT.md`.
Abgrenzung: Modul 00–02 und `/srv/cortex` bleiben unverändert; diese Referenz läuft ausschließlich in Sandbox-Pfaden. Die Anbindung an Modul 02 folgt erst nach Gate L.

## 1. Zweck und Trennung
- **Cortex** = Wissen, Synthesen, Wiki, qmd, MCP. **Cortex-Library** = Originaldokumente + Assets (Logos, Icons, SVG, Vorlagen).
- Originale werden nie zu normalen Markdown-Dateien und durch KI **nie stillschweigend verändert**; Löschen und Zusammenführen sind menschliche Aktionen in Paperless.
- Paperless-ngx ist das primäre DMS (native Funktionen vor Eigenbau); Paperless-GPT ist Anreicherung, nicht Dokumentenwahrheit.

## 2. Komponenten (alle per Digest gepinnt, siehe `VERSION_LOCK.md`)
| Komponente | Version | Zugang |
|---|---|---|
| Paperless-ngx | 3.3.0 | 127.0.0.1:18000 |
| PostgreSQL / Valkey | 18 / 9-alpine | nur internes Docker-Netz |
| Paperless-GPT (optional) | v0.29.0 | 127.0.0.1:18080 (ohne eigene Auth → nur hinter Cloudflare Access) |
| library-read (HTTP / MCP stdio) | 0.2.0 | 127.0.0.1:18090 / stdio |
| library-ingest (HTTP) | 0.2.0 | 127.0.0.1:18091 |
| ATLAS-Registry (SQLite, Schema v1) | – | `/var/lib/atlas-sandbox/module03/registry` |
| Asset Store | – | `/srv/atlas-sandbox/module03/assets` |

## 3. Identität und Referenzen
- Logische Identität: **UUIDv7**. Referenz `atlas-library://<uuidv7>`; revisionsgebunden `atlas-library://<uuidv7>@sha256:<hash>`. Die Paperless-ID ist nur Backend-ID.
- Registry-Auflösung: `ok | revision_mismatch | trashed | deleted | unknown | pending`. IDs werden nie wiederverwendet (Tombstone bei Hard Delete).
- **Technische Fassung** desselben Dokuments → gleiche ATLAS-ID, neue Revision (Paperless-Version, Original bleibt abrufbar; gepinnte ältere Referenz liefert genau diese Fassung).
  **Fachlich/rechtlich neues Dokument** → neue ATLAS-ID.
- Assets werden über dieselbe Registry aufgelöst; der Asset Store liefert die exakte registrierte Datei (Hash-geprüft, keine Neugenerierung, Pfad-/Symlink-Schutz).

## 4. Lifecycle und Taxonomie
`Unverarbeitet → OCR (Paperless) → ATLAS-ID → Paperless-GPT (optional) → Verarbeitet | Prüfen` (Tags `Status/*`).
`Status/Prüfen` = Mensch muss prüfen (GPT-Fehler, keine Änderung, unplausibler Titel/Korrespondent, unbekannte Hinweise, nicht verarbeitbare Datei).
Taxonomie (idempotent angelegt, kein Auto-Matching): 9 Dokumenttypen, 9 inhaltliche + 4 System-Tags, 12 Custom Fields (u. a. **ATLAS-ID**, **Datumsgenauigkeit**), Storage Path `ATLAS-Standard`.
Unbekannte Korrespondenten/Typen/Tags in Hinweisen werden **nicht** angelegt. Priorität der Angaben: Nutzer > deterministisch extrahiert > LLM.

## 5. Dateinamen und Datumsgenauigkeit
`YYYY[-MM[-DD]] - Korrespondent - Dokumenttyp - Titel.ext` (Platzhalter `ohne Korrespondent` / `ohne Typ`). Paperless kennt nur volle Daten; die Genauigkeit
(Tag/Monat/Jahr) steht im Feld `Datumsgenauigkeit`, `created` = erster Tag. Kein erfundener Tag im Dateinamen. Siehe `docs/DATUMSGENAUIGKEIT.md`.

## 6. Duplikate, Versionen, Löschen
Bit-identisch → gemeldet, nichts abgelegt/gelöscht (atomar, auch bei gleichzeitigem Import). Zweiter Scan → eigener Eintrag, Mensch entscheidet. Löschen nur durch Menschen
(Papierkorb 90 Tage); Registry spiegelt `trashed`/Tombstone. Nicht verarbeitbare Dateien bleiben `pending` und werden als `stale` gemeldet – nie automatisch gelöscht.

## 7. Schnittstellen (Details `docs/INTERFACES.md`)
- **library-read**: nur lesend (HTTP: nur GET; MCP: nur lesende Tools). Metadaten vor Volltext vor Datei. Eigenes Paperless-Konto mit View-Rechten (Schreiben → 403).
- **library-ingest**: Token, Größen-/Typlimits, Hinweise aus Allowlist, `queued | duplicate`, `revision`, Reconcile (ATLAS-ID setzen), Lifecycle-Sync. Kein Löschen/Mergen/Überschreiben.
- Claude/GPT erhalten **keine** breite Paperless-API – nur diese Adapter.

## 8. Sicherheit (Details `docs/SECURITY.md`, `docs/SECURITY_SCAN.md`)
Loopback-Ports, Container-Isolation (live geprüft), Secrets 0600/0700 über `*_FILE`/LoadCredential, systemd-Härtung (Exposure 1.5), Cloudflare-Vorlagen mit automatischer Konfigurationsprüfung,
Secret-Scan über die gesamte Historie, bandit/pip-audit sauber. Restrisiko: Upstream-CVEs in den gepinnten Images (bewusstes Digest-Update vor Produktivnutzung).

## 9. Backup und Recovery (Details `docs/RECOVERY.md`, `docs/ONEDRIVE.md`)
Vollbackup (Export, `pg_dump`, Rohdaten, Volumes, Registry, Assets, GPT-Daten, **alle Sandbox-Secrets**, Manifest, SHA256SUMS) → `rclone crypt` (Namen + Inhalte) → OneDrive.
Der **Recovery-Key** liegt extern. Getestet (lokales Crypt-Remote): Verschlüsselung, falsches Passwort, Korruption, Abbruch/Wiederaufnahme, Totalverlust-Restore ohne lokale Kopie.

## 10. Installation, Betrieb, Upgrade
`./install.sh preflight | install | validate | upgrade | recover` (`docs/INSTALL.md`, `docs/OPERATIONS.md`). Upgrade nur mit frischem, verifiziertem Backup; Recovery nur mit Bestätigungsschalter.
Release: reproduzierbares ZIP + SHA-256 + `RELEASE_MANIFEST.txt` (Datei-Hashes, vom Installer verifiziert).

## 11. Tests
`tests/run-all.sh` führt alle Tests aus (PASS/FAIL/BLOCKED); CI spiegelt sie. Echter LLM und echtes OneDrive sind vorbereitet, aber **BLOCKED**.

## 12. Offene Entscheidungen/Punkte für den Betreiber
D20 Korrespondenten automatisch anlegen? · Digest-Update der Upstream-Images (CVE-Funde) · GPT-Watchdog bei hängendem LLM · OneDrive-Konto + Recovery-Key-Ablage · Cloudflare-Access-Einrichtung ·
systemd-Dienste auf ATLAS · Hardware-/Performance-Abnahme (Gate G10) · Anbindung an Modul 02 nach Gate L.
