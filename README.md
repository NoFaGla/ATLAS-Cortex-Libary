# M03-CORTEX-LIBRARY-SANDBOX

Offline vorbereitetes Referenzpaket für **ATLAS – Modul 03: Cortex-Library**.

Ziel: Sobald der Server wieder läuft, kann die Sandbox reproduzierbar aufgebaut, getestet, vollständig gesichert, zerstört und aus dem Backup wiederhergestellt werden.

## Wichtige Grenzen

- Sandbox-Pfade sind strikt von produktiven ATLAS-Pfaden getrennt.
- `/srv/cortex` wird in dieser Phase **nicht** verändert.
- Keine produktiven Dokumente werden automatisch importiert.
- Paperless- und Paperless-GPT-Versionen sind gepinnt.
- `latest` ist im validierten Pfad verboten.
- Paperless-GPT wird erst nach erfolgreichem Paperless-Core-Test aktiviert.
- `library-registry`, `library-read`, `library-ingest` werden erst nach dem Core-Test implementiert/aktiviert.
- Das Sandbox-Backup enthält **alle Sandbox-Secrets**. Upload nach OneDrive erfolgt nur über einen `rclone crypt`-Remote.

## Gepinnter Startstand

- Paperless-ngx: `3.3.0`
- PostgreSQL: `18`
- Valkey: `9-alpine`
- Paperless-GPT: `v0.29.0` (Registry-Tag mit v-Präfix; `0.29.0` existiert nicht) als Zielstand; Image-Verfügbarkeit wird vor Start geprüft.

## Schnellstart, wenn ATLAS wieder läuft

```bash
unzip M03-CORTEX-LIBRARY-SANDBOX.zip
cd M03-CORTEX-LIBRARY-SANDBOX
bash scripts/00-preflight.sh
sudo bash scripts/01-bootstrap.sh
sudo /opt/atlas-sandbox/module03/scripts/02-up-core.sh
```

Danach **nicht blind weiterlaufen**, sondern `01_BUILD_PLAN.md` und `tests/TESTPLAN.md` abarbeiten.

## Sicherheitsprinzip

Webports der Sandbox binden ausschließlich an Loopback:

- Paperless: `127.0.0.1:18000`
- Paperless-GPT: `127.0.0.1:18080`

Öffentlicher Testzugriff wird später nur über Cloudflare Tunnel + Access eingerichtet.

## Verzeichnislayout auf ATLAS

```text
/opt/atlas-sandbox/module03/          Paket, Compose, Skripte
/srv/atlas-sandbox/module03/          media, consume, export, assets, Backups
/var/lib/atlas-sandbox/module03/      Paperless-GPT persistente Daten, Registry später
/etc/atlas/secrets/module03-sandbox/  Sandbox-Secrets
```

## Reihenfolge

1. Preflight
2. Bootstrap
3. Paperless-Core starten
4. Paperless-Core testen
5. API-Token erzeugen
6. Paperless-GPT konfigurieren/starten
7. Taxonomie + Testdokumente
8. Lifecycle/OCR/Metadaten/Dateinamen testen
9. Registry / library-read / library-ingest implementieren
10. Assets/Grounding testen
11. OneDrive/rclone-crypt konfigurieren
12. Vollbackup
13. Sandbox vollständig zerstören
14. Restore
15. Abnahme

Siehe `01_BUILD_PLAN.md`.
