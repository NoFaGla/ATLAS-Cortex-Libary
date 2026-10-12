# OneDrive-Backup

Sandbox-Muster:

```text
ATLAS -> lokales Staging -> rclone crypt -> OneDrive
```

Das Backup enthält **auch Secrets** und darf deshalb nicht unverschlüsselt hochgeladen werden.

## Config

```text
/etc/atlas/secrets/module03-sandbox/rclone.conf
```

```bash
sudo rclone --config /etc/atlas/secrets/module03-sandbox/rclone.conf config
```

Remotes:

1. `onedrive` = OneDrive.
2. `atlascrypt` = Crypt über `onedrive:ATLAS-Backup`.

Der Crypt-Recovery-Key muss extern außerhalb ATLAS/OneDrive gesichert sein.

## Upload

```bash
sudo /opt/atlas-sandbox/module03/scripts/06-backup-sandbox.sh --upload
```

Logisches Layout:

```text
M03-Sandbox/
├── current/
├── versions/<UTC-Timestamp>/
└── manifests/
```

## Cloud-Restore

Nach Neu-Konfiguration von OneDrive + Crypt:

```bash
mkdir -p /root/m03-cloud-restore/current
sudo RCLONE_CONFIG=/etc/atlas/secrets/module03-sandbox/rclone.conf \
  rclone copy atlascrypt:M03-Sandbox/current /root/m03-cloud-restore/current
sudo bash scripts/08-restore-sandbox.sh /root/m03-cloud-restore/current --i-understand-this-replaces-the-sandbox
```

Nach bestandener Sandbox wird dasselbe Muster auf ganz ATLAS erweitert, inklusive `/etc/atlas/secrets/`.
