# Wiederherstellung (Recovery)

Grundsatz: **Restore nie auf Produktion**, nie ohne Bestätigungsschalter, immer aus einem geprüften Backup.

## Was gesichert wird
Paperless-Export (`document_exporter`), `pg_dump`, rohe Pfade (media/consume/export/assets/Registry/GPT-Daten), Docker-Volumes, Paket/Compose,
**alle Sandbox-Secrets**, Versionsmanifest, `SHA256SUMS` (relative Pfade). Cloud-Kopie: `rclone crypt` (Namen + Inhalte verschlüsselt).

## Recovery-Key (kritisch)
`scripts/11-rclone-setup.sh --recovery-out DATEI` schreibt Crypt-Passwort + Salt in eine 0600-Datei. **Diese Datei außerhalb von ATLAS und OneDrive sichern**
(Passwortmanager/Papier-Ausdruck an zweitem Ort) und vom Server löschen. Ohne diesen Schlüssel ist die Cloud-Kopie unlesbar – auch für uns.

## Szenario A — Teilverlust, lokales Backup vorhanden
```bash
sudo ./install.sh recover /srv/atlas-sandbox/module03/backup-staging/<stamp>/current --i-understand-this-replaces-the-sandbox
```
## Szenario B — Totalverlust des Servers (nur Cloud-Backup + Recovery-Key)
```bash
# 1. Docker/Pakete installieren, Release-ZIP entpacken (siehe INSTALL.md), rclone installieren
# 2. rclone-Konfiguration aus dem Recovery-Key neu aufbauen (OneDrive-Token neu autorisieren: docs/ONEDRIVE.md)
sudo ./scripts/11-rclone-setup.sh --type onedrive --token-file token.json --drive-id <ID> --base-path ATLAS-Backup \
     --out /root/rclone-recover.conf --recovery-in /pfad/zum/recovery-key.txt
# 3. Backup holen (prüft Entschlüsselung + SHA256SUMS + Dateianzahl)
sudo RCLONE_CONFIG=/root/rclone-recover.conf ./scripts/13-cloud-restore.sh /root/m03-cloud-restore
# 4. Wiederherstellen + validieren
sudo ./install.sh recover /root/m03-cloud-restore/current --i-understand-this-replaces-the-sandbox
```
## Fehlerbilder
| Meldung | Bedeutung / Maßnahme |
|---|---|
| `Download/Entschlüsselung fehlgeschlagen` | falsches Crypt-Passwort/Salt oder beschädigte Cloud-Datei → Recovery-Key prüfen; `versions/<stamp>` enthält Vorversionen |
| `Prüfsummen stimmen nicht` / `Dateianzahl passt nicht` | beschädigter oder unterbrochener Upload → älteren Stand aus `versions/` oder `manifests/` nehmen; neuen Upload vom Server wiederholen |
| `kein Backup vorhanden` / `Backup ... h alt` (upgrade) | erst `06-backup-sandbox.sh --upload` ausführen |
| Paperless startet nach Restore nicht | `docker compose logs webserver db`; Backup unverändert lassen; zweites Restore auf frischem Host versuchen |
Nach jedem Restore: `./install.sh validate` und `docker compose exec webserver document_sanity_checker`.
