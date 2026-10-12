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
- Paperless-GPT: `v0.30.0` (Registry-Tag mit v-Präfix; vorher `v0.29.0`, Update siehe `docs/DEVIATIONS.md` D22); Image-Verfügbarkeit wird vor Start geprüft.

## Schnellstart auf ATLAS (Release-ZIP)

```bash
sha256sum -c M03-CORTEX-LIBRARY-<version>.zip.sha256 && unzip M03-CORTEX-LIBRARY-<version>.zip -d m03 && cd m03
./install.sh preflight          # ändert nichts; prüft auch das Release-Manifest (SHA-256 jeder Datei)
sudo ./install.sh install       # Bootstrap, Core, Token, Taxonomie   (--with-services: library-read/-ingest als systemd-Dienste)
sudo ./install.sh validate
```
Weiter: `docs/INSTALL.md`, `docs/OPERATIONS.md`, `docs/RECOVERY.md`, `docs/SECURITY.md`. **Das ist ein Release-Kandidat (siehe `docs/RELEASE_GATES.md`), nicht produktionsreif.**

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

## Reihenfolge (manuell, entspricht dem Installer)

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

## Repository-Überblick
```text
install.sh                Installer: preflight | install | validate | upgrade | recover | service-accounts
compose/ scripts/         Stack (Digest-gepinnt) und Betriebsskripte 00–14
src/atlas_library/        Registry (UUIDv7), Asset Store, library-read (HTTP+MCP), library-ingest (HTTP), Taxonomie, synthetische Testdaten
deploy/                   systemd-Units, Cloudflare Tunnel/Access-Vorlagen
tests/                    unit/ e2e/ integration/ mockllm/ ; Gesamtlauf: tests/run-all.sh
docs/                     AUDIT, DEVIATIONS, TESTREPORT, RELEASE_GATES, INSTALL, OPERATIONS, RECOVERY, SECURITY, ...
ATLAS_Modul_03_Cortex-Library.md   Modulbeschreibung (Release-Kandidat)
```
