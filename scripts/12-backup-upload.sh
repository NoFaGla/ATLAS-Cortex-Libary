#!/usr/bin/env bash
# Lädt ein lokales Backup (Verzeichnis mit current/ und SHA256SUMS) verschlüsselt hoch und verifiziert per Rück-Download.
# Aufruf: 12-backup-upload.sh <backup-basisverzeichnis>
# Umgebung: RCLONE_CONFIG (Pflicht), M03_CRYPT_REMOTE (atlascrypt), M03_CLOUD_DIR (M03-Sandbox)
set -euo pipefail
BASE=${1:-}; [ -d "$BASE/current" ] && [ -f "$BASE/SHA256SUMS" ] || { echo "Aufruf: $0 <backup-basis mit current/ und SHA256SUMS>" >&2; exit 2; }
command -v rclone >/dev/null || { echo "rclone fehlt" >&2; exit 1; }
CONF=${RCLONE_CONFIG:-}; [ -s "$CONF" ] || { echo "STOP: RCLONE_CONFIG fehlt oder leer" >&2; exit 1; }
export RCLONE_CONFIG="$CONF"
REMOTE=${M03_CRYPT_REMOTE:-atlascrypt}; TARGET="$REMOTE:${M03_CLOUD_DIR:-M03-Sandbox}"; STAMP=$(basename "$BASE")
# Das Backup enthält Secrets: nur in ein Crypt-Remote mit Dateinamen- UND Inhaltsverschlüsselung hochladen.
rclone config dump | python3 -c '
import json, sys
d = json.load(sys.stdin).get(sys.argv[1], {})
ok = d.get("type") == "crypt" and d.get("filename_encryption", "standard") == "standard" and d.get("directory_name_encryption", "true") == "true"
sys.exit(0 if ok else 1)' "$REMOTE" || { echo "STOP: Remote $REMOTE fehlt oder ist kein vollständig verschlüsselndes crypt-Remote (Upload verweigert)" >&2; exit 1; }
(cd "$BASE" && sha256sum --quiet -c SHA256SUMS) || { echo "STOP: lokales Backup ist inkonsistent (Prüfsummen)" >&2; exit 1; }
# Daten zuerst; SHA256SUMS zuletzt. Eine unterbrochene Übertragung hinterlässt dadurch eine nicht passende Prüfsummendatei
# und wird beim Cloud-Restore erkannt. Wiederholung ist idempotent. Ersetzte/gelöschte Dateien landen in versions/<stamp>.
rclone sync "$BASE/" "$TARGET/latest" --exclude /SHA256SUMS --backup-dir "$TARGET/versions/$STAMP" \
  --create-empty-src-dirs --transfers 2 --checkers 4 --retries 3 --low-level-retries 5
rclone copyto "$BASE/SHA256SUMS" "$TARGET/latest/SHA256SUMS"
rclone copyto "$BASE/SHA256SUMS" "$TARGET/manifests/$STAMP-SHA256SUMS"
# Verifikation per Download (Crypt-Remotes haben nicht auf allen Backends vergleichbare Hashes).
if ! rclone check "$BASE/current" "$TARGET/latest/current" --one-way --download; then
  # z. B. Bit-Rot/Teilübertragung im Cloud-Speicher bei gleicher Größe+Zeit: alles erneut hochladen und nochmals prüfen
  echo "WARN: Verifikation fehlgeschlagen, erzwinge erneute Übertragung (--ignore-times)" >&2
  rclone sync "$BASE/current" "$TARGET/latest/current" --ignore-times --transfers 2 --retries 3
  rclone check "$BASE/current" "$TARGET/latest/current" --one-way --download || { echo "FAIL: Cloud-Backup nicht verifizierbar" >&2; exit 1; }
fi
rclone cat "$TARGET/latest/SHA256SUMS" | cmp -s - "$BASE/SHA256SUMS" || { echo "FAIL: SHA256SUMS in der Cloud weicht ab" >&2; exit 1; }
echo "UPLOAD=PASS stamp=$STAMP"
