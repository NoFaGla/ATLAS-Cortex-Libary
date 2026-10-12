#!/usr/bin/env bash
# Holt das letzte verschlüsselte Backup aus der Cloud in ein NEUES Verzeichnis und verifiziert die Prüfsummen.
# Aufruf: 13-cloud-restore.sh <ziel-verzeichnis (neu oder leer)>      Umgebung wie 12-backup-upload.sh
# Danach:  08-restore-sandbox.sh <ziel>/current --i-understand-this-replaces-the-sandbox
set -euo pipefail
DEST=${1:-}; [ -n "$DEST" ] || { echo "Aufruf: $0 <ziel-verzeichnis>" >&2; exit 2; }
command -v rclone >/dev/null || { echo "rclone fehlt" >&2; exit 1; }
CONF=${RCLONE_CONFIG:-}; [ -s "$CONF" ] || { echo "STOP: RCLONE_CONFIG fehlt oder leer" >&2; exit 1; }
export RCLONE_CONFIG="$CONF"
if [ -e "$DEST" ] && [ -n "$(ls -A "$DEST" 2>/dev/null)" ]; then echo "STOP: $DEST ist nicht leer" >&2; exit 1; fi
TARGET="${M03_CRYPT_REMOTE:-atlascrypt}:${M03_CLOUD_DIR:-M03-Sandbox}"
mkdir -p "$DEST"; chmod 700 "$DEST"
rclone copy "$TARGET/latest" "$DEST" --transfers 2 --retries 3 --low-level-retries 5 || { echo "FAIL: Download/Entschlüsselung fehlgeschlagen (falsches Passwort oder beschädigtes Backup?)" >&2; exit 1; }
[ -f "$DEST/SHA256SUMS" ] || { echo "FAIL: SHA256SUMS fehlt im Cloud-Backup (unterbrochener Upload?)" >&2; exit 1; }
(cd "$DEST" && sha256sum --quiet -c SHA256SUMS) || { echo "FAIL: Prüfsummen stimmen nicht (beschädigt/unvollständig)" >&2; exit 1; }
N_LISTED=$(wc -l < "$DEST/SHA256SUMS"); N_FILES=$(find "$DEST/current" -type f | wc -l)
[ "$N_LISTED" -eq "$N_FILES" ] || { echo "FAIL: Dateianzahl ($N_FILES) passt nicht zur Prüfsummenliste ($N_LISTED)" >&2; exit 1; }
echo "CLOUD_RESTORE=PASS dest=$DEST files=$N_FILES"
