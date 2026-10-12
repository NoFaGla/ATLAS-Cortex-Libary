# Echter LLM-Test für Paperless-GPT (vorbereitet, nicht ausgeführt)

Status: **BLOCKED** (kein LLM-Zugang in der Cloud-Umgebung; Schlüssel gehören nie in GitHub).
Alles andere an der GPT-Kommunikation ist gegen einen OpenAI-kompatiblen Mock getestet (`docs/TESTREPORT.md`, Abschnitt Paperless-GPT).

## Ausführung (lokal, mit ausdrücklicher Freigabe durch den Betreiber)
```bash
export M03_REAL_LLM=1 LLM_PROVIDER=anthropic LLM_MODEL=<modellname> ANTHROPIC_API_KEY=<schlüssel>   # oder openai + OPENAI_API_KEY
bash tests/integration/gpt-real-llm.sh
```
- Es werden nur die **synthetischen** Dokumente T01, T06, T07 an den Anbieter gesendet (kein privater Inhalt).
- Der Schlüssel wird nur in eine 0600-Datei im Temp-Verzeichnis des Wegwerf-Stacks geschrieben, danach gelöscht; das Skript prüft, dass er in keinem Container-Log steht.
- Geprüft: sinnvoller Titel (5–128 Zeichen), gültiges Datum, **kein** automatischer Dokumenttyp, keine neuen Tags/Typen, Original unverändert, Endstatus Verarbeitet/Prüfen.
- Ohne die Variablen endet das Skript mit `RESULT=BLOCKED` (Exit 77).

## Auswertung
Beobachtungen: `/tmp/gpt-real-observations.json`. Qualität (Korrespondent, Datum, Tags) ist LLM-abhängig und wird nur auf Plausibilität geprüft;
Abweichungen sind keine Testfehler, aber ein Eintrag in `docs/AUDIT.md` wert.
