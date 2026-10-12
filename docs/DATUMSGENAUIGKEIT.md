# Datumsgenauigkeit und Dateinamen (Befund + Lösung)

## Befund (real gegen Paperless 3.3.0, synthetische Dokumente)
- Paperless kennt nur volle Daten (`created`). Bei „Monat Jahr“-Angaben setzt es den **1. des Monats** – ein erfundener Tag.
- Das Auto-Datum ist unzuverlässig: T02 enthält „Verdienstabrechnung Februar 2026“ **und** „Abrechnungsdatum: 28.02.2026“;
  Paperless wählte `2026-02-01` (E2E-Beobachtung `auto_date_T02`).
- Das Standard-Dateinamenformat `{{ created }} - …` liefert immer `YYYY-MM-DD` und für fehlende Korrespondenten/Typen den Text `none`.

## Lösung
1. Custom Field **`Datumsgenauigkeit`** (Auswahl `Tag` | `Monat` | `Jahr`). `created` bleibt technisch ein volles Datum
   (Konvention: erster Tag), die Genauigkeit steht im Feld.
2. Storage Path **`ATLAS-Standard`** mit Jinja-Vorlage (`atlas_library.taxonomy.FILENAME_TEMPLATE`):
   `YYYY[-MM[-DD]] - Korrespondent - Dokumenttyp - Titel`, Platzhalter `ohne Korrespondent` / `ohne Typ`.
   Ohne Eintrag im Feld gilt `Tag`. `library-ingest` weist den Storage Path jedem importierten Dokument zu.
3. `library-ingest` nimmt `created` (YYYY-MM-DD) + `date_precision` als Hinweis (Priorität: Nutzer > deterministisch > LLM)
   und überschreibt damit das Paperless-Raten.
4. Titel werden vor dem Import bereinigt (`/` → `-`), weil Paperless den Titel im Dateinamen verwendet und `/` ein Unterverzeichnis erzeugen würde.

## Verifiziert (E2E, PASS)
`2026-01-31 - Muster Arbeitgeber GmbH - Abrechnung - Verdienstabrechnung 2026-01.pdf` (Tag),
`2026-03 - Beispiel Wohnbau GmbH - Abrechnung - …` (Monat, kein erfundener Tag), `2023-06 - … - Zeugnis - …`,
`… - ohne Typ - …` (fehlender Typ), Sonderzeichen/`&`/Umlaute, lexikographische = chronologische Sortierung,
Namenskollisionen werden von Paperless mit Zähler aufgelöst (keine Überschreibung).

## Offen
- Jahres-Genauigkeit (`Jahr`) ist implementiert, aber nicht mit eigenem Testdokument belegt.
- `PAPERLESS_FILENAME_FORMAT` (env) bleibt nur Fallback für Dokumente ohne Storage Path (liefert `none`-Platzhalter).
