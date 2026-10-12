# Test- und Abnahmeplan

> Ausführungsstand der Cloud-Läufe: `docs/TESTREPORT.md`. Die Checkboxen unten bleiben für die Abnahme auf dem ATLAS-Server offen.

Bewertung: PASS / PASS MIT DOKUMENTIERTER ABWEICHUNG / FAIL / BLOCKER.

## 1. Core
- [ ] PostgreSQL gesund.
- [ ] Valkey läuft.
- [ ] Paperless 3.3.0 läuft.
- [ ] nur `127.0.0.1:18000`.
- [ ] Adminlogin.
- [ ] Neustart ohne Datenverlust.
- [ ] `document_sanity_checker` sauber.

## 2. Ingest/OCR
- [ ] Webupload.
- [ ] Consume-Ordner.
- [ ] mehrseitiges PDF.
- [ ] deutscher OCR-Text brauchbar.
- [ ] schlechter Scan Baseline.
- [ ] Original unverändert.

## 3. Paperless-GPT
- [ ] UI nur Loopback.
- [ ] API-Verbindung.
- [ ] Titel sinnvoll.
- [ ] Datum sinnvoll.
- [ ] Korrespondent korrekt.
- [ ] bestehende Typen/Tags bevorzugt.
- [ ] keine freie Typ-Wildwuchs-Erzeugung.
- [ ] Custom Fields korrekt.
- [ ] Fehlerstatus statt Endlosschleife.

## 4. Dateinamen
- [ ] Schema `YYYY-MM[-DD] - Korrespondent - Dokumenttyp [- Titelrest]` praktikabel.
- [ ] Sortierbarkeit.
- [ ] keine Überschreibungen.
- [ ] robuste Sonderzeichen.
- [ ] Verhalten bei fehlendem Typ/Korrespondent.
- [ ] Datumspräzision ohne erfundenen Tag geklärt.

## 5. Duplikate/Versionen
- [ ] bit-identisches Duplikat erkannt, nicht gelöscht.
- [ ] zweiter Scan nicht automatisch destruktiv gemerged.
- [ ] technische Fassung als Version.
- [ ] fachlich geänderte Fassung eigenes Dokument.
- [ ] ältere Version abrufbar.

## 6. Retrieval später
- [ ] Metadaten vor Volltext.
- [ ] kompakte Treffer.
- [ ] OCR/PDF nur bei Bedarf.
- [ ] Mehrdeutigkeit sichtbar.

## 7. Registry später
- [ ] UUIDv7.
- [ ] logische Referenz.
- [ ] SHA-gepinnte Referenz.
- [ ] `revision_mismatch`, `trashed`, `deleted`, `unknown`.

## 8. Assets
- [ ] SVG, PNG, Vorlage.
- [ ] Resolver liefert exakte Datei.
- [ ] keine Neugenerierung.

## 9. Security
- [ ] keine Ports auf `0.0.0.0`.
- [ ] Secrets 0700/0600.
- [ ] keine Secrets in Compose/Markdown/Logs.
- [ ] Cloudflare Access später vor beiden UIs.

## 10. Backup
- [ ] logical export.
- [ ] pg_dump.
- [ ] rohe Hostdaten.
- [ ] Docker-Volume-Snapshots.
- [ ] GPT prompts/config/history.
- [ ] Assets/Registry.
- [ ] **alle Sandbox-Secrets**.
- [ ] SHA256SUMS.
- [ ] `rclone crypt` Upload + `rclone check`.

## 11. Destructive Restore
- [ ] Sandbox/Volumes/Secrets gelöscht.
- [ ] Restore aus Backup.
- [ ] Dokumente/Hashes/Metadaten identisch.
- [ ] Paperless-GPT/Assets/Registry vorhanden.
- [ ] `document_sanity_checker` sauber.

## Muss-Kriterien
Keine stille Originaländerung; keine KI-Löschung; keine ungeschützte UI; stabile IDs; verschlüsseltes Vollbackup; kompletter Restore PASS.
