# OneDrive-Anbindung (vorbereitet, ohne echte Zugangsdaten getestet)

Cloud-Ziel: `OneDrive:ATLAS-Backup` → rclone-Remote `onedrive`; darüber das Crypt-Remote `atlascrypt` (Dateinamen, Verzeichnisnamen, Inhalte verschlüsselt).
Getestet ist die komplette Kette mit einem lokalen Test-Remote (`tests/integration/rclone-crypt.sh`, `restore-e2e.sh`). **Nicht getestet: echte
OneDrive-Authentifizierung, Mengen-/Rate-Limits, OneDrive-spezifisches Verhalten.**

## Schritte (einmalig, Betreiber)
1. Auf einem Rechner **mit Browser**: `rclone authorize "onedrive"` → Anmeldung → Ausgabe (JSON `{"access_token":...}`) in `token.json` speichern (0600).
2. Laufwerk-ID ermitteln: `rclone config` (Hilfsrechner) oder Microsoft Graph (`/me/drive`). Typ `personal` oder `business`.
3. Auf ATLAS (root):
```bash
sudo /opt/atlas-sandbox/module03/scripts/11-rclone-setup.sh --type onedrive --token-file token.json --drive-id <ID> --drive-type personal \
     --base-path ATLAS-Backup --out /etc/atlas/secrets/module03-sandbox/rclone.conf --recovery-out /root/recovery-key.txt
shred -u token.json
```
4. `/root/recovery-key.txt` **extern sichern**, dann `shred -u`. (Siehe `RECOVERY.md`.)
5. Erster Lauf: `sudo .../06-backup-sandbox.sh --upload`; danach `sudo RCLONE_CONFIG=... .../13-cloud-restore.sh /root/test-restore` und mit `diff -r` gegen das lokale Staging vergleichen.

## Sicherheit
- `12-backup-upload.sh` lädt **nur** in ein Crypt-Remote mit `filename_encryption=standard` + `directory_name_encryption=true` hoch.
- Das OAuth-Token liegt (wie jede rclone-Konfiguration) in `rclone.conf` (0600, root). Token-Ablauf: `rclone about onedrive:` prüfen; bei Ablauf neu autorisieren.
- Cloud-Struktur: `latest/` (aktuell), `versions/<stamp>/` (ersetzte Dateien), `manifests/<stamp>-SHA256SUMS`.
- Die Konfigurationsdatei selbst ist im Backup enthalten (Sandbox-Secrets-Verzeichnis) – für die Wiederherstellung wird sie aus dem Recovery-Key neu gebaut.
