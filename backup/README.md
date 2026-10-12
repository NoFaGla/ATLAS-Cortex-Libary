# OneDrive-Backup

```text
ATLAS -> lokales Staging -> rclone crypt (Namen + Inhalte) -> OneDrive:ATLAS-Backup
```
Das Backup enthält **auch Secrets** und wird deshalb nur verschlüsselt hochgeladen. Details: `docs/ONEDRIVE.md`, `docs/RECOVERY.md`.

## Einrichtung
```bash
sudo scripts/11-rclone-setup.sh --type onedrive --token-file token.json --drive-id <ID> --base-path ATLAS-Backup \
     --out /etc/atlas/secrets/module03-sandbox/rclone.conf --recovery-out /root/recovery-key.txt   # Recovery-Key extern sichern!
```
## Betrieb
```bash
sudo scripts/06-backup-sandbox.sh --upload        # sichert lokal, lädt verschlüsselt hoch, verifiziert per Rück-Download (12-backup-upload.sh)
sudo RCLONE_CONFIG=... scripts/13-cloud-restore.sh /root/m03-cloud-restore      # holt + prüft das Cloud-Backup
sudo ./install.sh recover /root/m03-cloud-restore/current --i-understand-this-replaces-the-sandbox
```
Cloud-Layout: `M03-Sandbox/latest/` (aktuell: `current/` + `SHA256SUMS`), `versions/<UTC-Stamp>/` (ersetzte Dateien), `manifests/<Stamp>-SHA256SUMS`.
