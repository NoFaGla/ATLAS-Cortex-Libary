# Installation (Sandbox auf dem ATLAS-Server)

> Dieses Paket installiert **nur** die Sandbox (`/opt|/srv|/var/lib/atlas-sandbox/module03`, `/etc/atlas/secrets/module03-sandbox`).
> `/srv/cortex`, Modul 00–02 und produktive Pfade werden nie angefasst. Kein Schritt hier ist ein produktives Deployment.

## Voraussetzungen
- Linux mit Docker Engine + Compose v2, `python3 >= 3.11`, `curl`, ≥ 20 GiB frei; für Backup `rclone` (empfohlen ≥ 1.60), optional `rsync`.
- Ports 18000/18080 (und 18090/18091 für die Dienste) frei; alle Dienste binden **nur** an `127.0.0.1`.

## 1. Release prüfen und entpacken
```bash
sha256sum -c M03-CORTEX-LIBRARY-<version>.zip.sha256     # Prüfsumme des ZIP
unzip M03-CORTEX-LIBRARY-<version>.zip -d m03 && cd m03
./install.sh preflight                                    # prüft auch RELEASE_MANIFEST.txt (SHA-256 jeder Datei); ändert nichts
```
## 2. Installieren
```bash
sudo ./install.sh install                  # Bootstrap (Secrets 0600), Core, API-Token, Taxonomie
sudo ./install.sh validate                 # Isolation, Ports, Secrets, Registry, Taxonomie
sudo ./install.sh install --with-services  # (statt install) zusätzlich Dienstkonten + systemd-Units library-read/-ingest
```
`install` verweigert, wenn bereits eine Installation existiert (nichts wird überschrieben).

## 3. Paperless-GPT (optional, erst nach bestandener Core-Abnahme)
1. `sudo $EDITOR /etc/atlas/secrets/module03-sandbox/paperless-gpt.env` → Provider/Modell/Schlüssel eintragen (Platzhalter `REPLACE_*` ersetzen). Schlüssel nur dort, nie im Repo.
2. `sudo /opt/atlas-sandbox/module03/scripts/05-up-ai.sh` (verweigert bei Platzhaltern oder nicht ladbarem gepinnten Image).
3. Empfohlener erster Test mit echtem LLM: `docs/GPT_REAL_LLM_TEST.md`.

## 4. Backup einrichten (vor produktiver Nutzung Pflicht)
Siehe `docs/ONEDRIVE.md` (OneDrive + `rclone crypt`) und `docs/RECOVERY.md`.

## 5. Zugriff von außen
Nur über Cloudflare Tunnel + Access (Vorlagen in `deploy/cloudflare`, Anleitung `docs/CLOUDFLARE.md`). Nie Ports öffnen.

## Upgrade
```bash
sudo /opt/atlas-sandbox/module03/scripts/06-backup-sandbox.sh --upload      # frisches, verschlüsseltes Backup
unzip neues-release.zip -d m03-neu && cd m03-neu && ./install.sh preflight
sudo ./install.sh upgrade                  # verweigert ohne frisches (≤24 h), verifiziertes Backup; validiert danach
```
Bei Fehlschlag gibt `upgrade` den exakten `recover`-Befehl aus; es wird nichts automatisch gelöscht oder zurückgerollt.
Images werden nur durch bewusste Änderung der Digests in `compose/docker-compose.yml` + `VERSION_LOCK.md` aktualisiert (nach Sandbox-Test).
