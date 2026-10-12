# Cloud-Workflow: GitHub + Claude Code

## Einmalig
1. Ein **privates** GitHub-Repository `ATLAS-Cortex-Library` erstellen.
2. Den **Inhalt** dieses ZIPs ins Repository hochladen (Dateien auf Repo-Root-Ebene). `.env`, Secrets und echte Dokumente nie hochladen.
3. Claude Code mit GitHub verbinden und das Repository als Arbeitskontext wählen. `CLAUDE.md` wird als Projektanweisung verwendet.
4. Den Prompt aus `PROMPT_FUER_CLAUDE.txt` senden.

## Ausführung
- Claude Code Cloud kann Code und Skripte entwickeln, prüfen und PRs vorbereiten.
- GitHub Actions kann statische Tests und ggf. isolierte Container-Tests ausführen.
- Ein Claude-Code-Cloud-Arbeitsplatz ist **kein** dauerhaft laufender Docker-Host. Integrationstests sind nur PASS, wenn die Umgebung sie wirklich ausführt.
- Keine echten Secrets in GitHub Actions ohne getrennte Testumgebung und explizite Freigabe.
- Server-Hardware, OneDrive-Restore, Cloudflare Access und Performance benötigen später echte End-to-End-Tests.

## Release-Regel
Cloud-grün bedeutet nicht produktionsreif. Freigabe erst nach Hardware-, Sicherheits- und destruktivem Restore-Test auf separater Sandbox.
