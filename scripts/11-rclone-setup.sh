#!/usr/bin/env bash
# Erzeugt eine rclone-Konfiguration mit verschlüsseltem Remote `atlascrypt` (Dateinamen + Verzeichnisnamen + Inhalt).
# Keine Secrets auf der Kommandozeile (ps!): Passwörter werden zufällig erzeugt und über stdin obfuskiert.
#
#   11-rclone-setup.sh --type onedrive --token-file FILE --drive-id ID [--drive-type personal|business] \
#                      --base-path ATLAS-Backup --out CONF --recovery-out FILE
#   11-rclone-setup.sh --type local --base-path /abs/dir/ATLAS-Backup --out CONF --recovery-out FILE   (Tests)
#
# Der Recovery-Key (Crypt-Passwort + Salt im Klartext) wird NUR nach --recovery-out geschrieben (0600). Er muss außerhalb von
# ATLAS/OneDrive gesichert werden (Passwortmanager/Papier); danach die Datei vom Server entfernen. Er wird nie ausgegeben.
set -euo pipefail
REC_IN=""; TYPE=""; TOKEN_FILE=""; DRIVE_ID=""; DRIVE_TYPE="personal"; BASE=""; OUT=""; REC=""
while [ $# -gt 0 ]; do
  case "$1" in
    --type) TYPE=$2; shift 2 ;; --token-file) TOKEN_FILE=$2; shift 2 ;; --drive-id) DRIVE_ID=$2; shift 2 ;;
    --drive-type) DRIVE_TYPE=$2; shift 2 ;; --base-path) BASE=$2; shift 2 ;; --out) OUT=$2; shift 2 ;;
    --recovery-out) REC=$2; shift 2 ;; --recovery-in) REC_IN=$2; shift 2 ;; *) echo "unbekannte Option: $1" >&2; exit 2 ;;
  esac
done
command -v rclone >/dev/null || { echo "rclone fehlt" >&2; exit 1; }
[ -n "$TYPE" ] && [ -n "$BASE" ] && [ -n "$OUT" ] && { [ -n "$REC" ] || [ -n "$REC_IN" ]; } || { echo "Pflichtoptionen: --type --base-path --out und --recovery-out (neu) oder --recovery-in (Wiederherstellung)" >&2; exit 2; }
[ ! -e "$OUT" ] || { echo "STOP: $OUT existiert bereits (wird nicht überschrieben)" >&2; exit 1; }
[ -z "$REC" ] || [ ! -e "$REC" ] || { echo "STOP: $REC existiert bereits" >&2; exit 1; }
case "$TYPE" in
  onedrive)
    [ -s "$TOKEN_FILE" ] && [ -n "$DRIVE_ID" ] || { echo "onedrive: --token-file (rclone authorize) und --drive-id erforderlich" >&2; exit 2; }
    python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "$TOKEN_FILE" || { echo "Token-Datei ist kein gültiges JSON" >&2; exit 2; }
    case "$DRIVE_TYPE" in personal|business|documentLibrary) ;; *) echo "ungültiger --drive-type" >&2; exit 2 ;; esac
    ;;
  local) ;;
  *) echo "--type muss onedrive oder local sein" >&2; exit 2 ;;
esac
umask 077
if [ -n "$REC_IN" ]; then
  # Wiederherstellung der Konfiguration aus dem extern gesicherten Recovery-Key (z. B. nach Totalverlust des Servers)
  PW=$(grep '^password=' "$REC_IN" | head -1 | cut -d= -f2-); SALT=$(grep '^password2_salt=' "$REC_IN" | head -1 | cut -d= -f2-)
  [ -n "$PW" ] && [ -n "$SALT" ] || { echo "Recovery-Key-Datei ungültig" >&2; exit 2; }
else
  PW=$(python3 -c 'import secrets;print(secrets.token_urlsafe(48))')
  SALT=$(python3 -c 'import secrets;print(secrets.token_urlsafe(48))')
fi
PW_OBS=$(printf '%s' "$PW" | rclone obscure -)
SALT_OBS=$(printf '%s' "$SALT" | rclone obscure -)
{
  echo "[onedrive]"
  if [ "$TYPE" = onedrive ]; then
    echo "type = onedrive"
    printf 'token = %s\n' "$(python3 -c 'import json,sys;print(json.dumps(json.load(open(sys.argv[1])),separators=(",",":")))' "$TOKEN_FILE")"
    echo "drive_id = $DRIVE_ID"
    echo "drive_type = $DRIVE_TYPE"
    REMOTE="onedrive:$BASE"
  else
    echo "type = local"
    REMOTE="onedrive:$BASE"
  fi
  echo
  echo "[atlascrypt]"
  echo "type = crypt"
  echo "remote = $REMOTE"
  echo "filename_encryption = standard"
  echo "directory_name_encryption = true"
  echo "password = $PW_OBS"
  echo "password2 = $SALT_OBS"
} > "$OUT"
chmod 600 "$OUT"
if [ -n "$REC" ]; then
  { echo "# ATLAS M03 rclone-crypt Recovery-Key — AUSSERHALB von ATLAS/OneDrive sichern, danach vom Server löschen"; echo "password=$PW"; echo "password2_salt=$SALT"; } > "$REC"
  chmod 600 "$REC"
fi
unset PW SALT PW_OBS SALT_OBS
echo "RCLONE_SETUP=PASS config=$OUT recovery_key_file=$REC (Schlüssel nicht angezeigt)"
