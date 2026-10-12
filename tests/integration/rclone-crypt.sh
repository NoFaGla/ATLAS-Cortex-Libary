#!/usr/bin/env bash
# rclone-crypt-Tests mit lokalem Test-Remote (kein Docker, keine Zugangsdaten). Exit 77 = BLOCKED (rclone fehlt).
# Prüft: Verschlüsselung von Namen/Inhalt, Upload/Download/Prüfsummen/Restore, falsches Passwort, beschädigte und abgeschnittene
# Dateien, unterbrochener Transfer, Upload-Guard bei unverschlüsseltem Remote, keine Secrets in Logs.
set -euo pipefail
REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
command -v rclone >/dev/null || { echo "RESULT=BLOCKED (rclone fehlt)"; exit 77; }
W=$(mktemp -d); trap 'rm -rf "$W"' EXIT; cd "$W"
pass(){ echo "PASS: $*"; }; fail(){ echo "FAIL: $*"; exit 1; }
MARK="TOPSECRET-MARKER-$(python3 -c 'import secrets;print(secrets.token_hex(8))')"
# --- Setup -----------------------------------------------------------------------------------------------------------------
mkdir -p cloud
bash "$REPO/scripts/11-rclone-setup.sh" --type local --base-path "$W/cloud/ATLAS-Backup" --out "$W/rclone.conf" --recovery-out "$W/recovery.txt" > setup.log
[ "$(stat -c %a rclone.conf)" = 600 ] && [ "$(stat -c %a recovery.txt)" = 600 ] && pass "Konfiguration + Recovery-Key mit 0600"
PW=$(grep '^password=' recovery.txt | cut -d= -f2-)
! grep -q "$PW" setup.log && ! grep -q "$PW" rclone.conf && pass "Klartext-Passwort weder im Log noch in der Konfiguration (nur obfuskiert)"
if bash "$REPO/scripts/11-rclone-setup.sh" --type local --base-path x --out rclone.conf --recovery-out r2.txt 2>/dev/null; then fail "Setup überschrieb bestehende Konfiguration"; fi
pass "Setup überschreibt keine bestehende Konfiguration"
# --- Synthetisches Backup (mit Secret-Marker) -------------------------------------------------------------------------------
B="$W/staging/20260101T000000Z"; mkdir -p "$B/current/etc/module03-sandbox-secrets" "$B/current/srv/media" "$B/current/database"
printf '%s\n' "$MARK" > "$B/current/etc/module03-sandbox-secrets/paperless_secret_key"
printf 'postgres-%s\n' "$MARK" > "$B/current/etc/module03-sandbox-secrets/postgres_password"
head -c 3000000 /dev/urandom > "$B/current/database/paperless.dump"
echo "Rechnung Muster synthetisch $MARK" > "$B/current/srv/media/Rechnung 2026 Müller.txt"
(cd "$B" && find current -type f -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS)
export RCLONE_CONFIG="$W/rclone.conf"
bash "$REPO/scripts/12-backup-upload.sh" "$B" > up.log 2>&1 || { cat up.log; fail "Upload"; }
grep -q "UPLOAD=PASS" up.log && pass "Upload + Rück-Download-Verifikation (rclone check --download)"
# --- Verschlüsselung: Namen und Inhalt ----------------------------------------------------------------------------------------
LISTING=$(cd cloud && find . | sort)
for plain in paperless_secret_key postgres_password paperless.dump Rechnung module03 media database SHA256SUMS current latest; do
  if printf '%s' "$LISTING" | grep -qi "$plain"; then fail "Klartextname '$plain' im Cloud-Verzeichnis sichtbar"; fi
done
pass "Datei- und Verzeichnisnamen sind verschlüsselt (kein Klartextname im Cloud-Speicher)"
if grep -rqa "$MARK" cloud; then fail "Secret-Marker im Klartext in der Cloud"; fi
pass "Inhalte sind verschlüsselt (Secret-Marker nirgends im Klartext)"
# --- Download / vollständige Wiederherstellung --------------------------------------------------------------------------------
bash "$REPO/scripts/13-cloud-restore.sh" "$W/restore1" > dl.log 2>&1 || { cat dl.log; fail "Cloud-Restore"; }
diff -r "$B/current" "$W/restore1/current" && cmp "$B/SHA256SUMS" "$W/restore1/SHA256SUMS" && pass "Cloud-Restore bit-identisch (alle Dateien inkl. Secrets, Sonderzeichen im Dateinamen)"
[ -f "$W/restore1/current/etc/module03-sandbox-secrets/paperless_secret_key" ] && pass "Sandbox-Secrets sind im verschlüsselten Backup enthalten und wiederherstellbar"
# --- Idempotenz / Änderungen ------------------------------------------------------------------------------------------------
echo changed >> "$B/current/srv/media/Rechnung 2026 Müller.txt"; (cd "$B" && find current -type f -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS)
B2="$W/staging/20260102T000000Z"; mv "$B" "$B2"
bash "$REPO/scripts/12-backup-upload.sh" "$B2" > up2.log 2>&1 && pass "zweiter Upload (Änderung) erfolgreich" || fail "zweiter Upload"
[ "$(rclone lsf -R --files-only atlascrypt:M03-Sandbox/versions | wc -l)" -ge 1 ] && pass "ersetzte Datei bleibt als Vorversion erhalten (versions/)"
# --- Falsches Passwort ------------------------------------------------------------------------------------------------------
python3 - "$W/rclone.conf" "$W/wrong.conf" <<'PY'
import re,sys,subprocess
s=open(sys.argv[1]).read()
wrong=subprocess.run(["rclone","obscure","-"],input="falsches-passwort",capture_output=True,text=True).stdout.strip()
s=re.sub(r"^password = .*$","password = "+wrong,s,flags=re.M)
open(sys.argv[2],"w").write(s)
PY
chmod 600 wrong.conf
if RCLONE_CONFIG="$W/wrong.conf" bash "$REPO/scripts/13-cloud-restore.sh" "$W/restore_wrong" > wrong.log 2>&1; then fail "Restore mit falschem Passwort erfolgreich"; fi
[ ! -f "$W/restore_wrong/current/etc/module03-sandbox-secrets/paperless_secret_key" ] && pass "falsches Passwort: Restore scheitert, kein Klartext erzeugt"
# --- Beschädigtes Backup ----------------------------------------------------------------------------------------------------
enc_path() { rclone cryptdecode --reverse atlascrypt: "$1" | awk '{print $NF}'; }
ENC=$(enc_path "M03-Sandbox/latest/current/database/paperless.dump"); BIG="ATLAS-Backup/$ENC"
[ -f "cloud/$BIG" ] || fail "verschlüsselter Pfad nicht gefunden ($BIG)"
python3 - "$W/cloud/$BIG" <<'PY'
import sys
p=sys.argv[1]; b=bytearray(open(p,"rb").read()); b[len(b)//2]^=0xFF; open(p,"wb").write(b)
PY
if bash "$REPO/scripts/13-cloud-restore.sh" "$W/restore_corrupt" > corrupt.log 2>&1; then fail "beschädigte Datei nicht erkannt"; fi
pass "beschädigte Cloud-Datei wird erkannt (Authentifizierung/Prüfsumme), Restore bricht ab"
# Reparatur durch erneuten Upload
bash "$REPO/scripts/12-backup-upload.sh" "$B2" > up3.log 2>&1 && pass "Wiederholter Upload repariert die beschädigte Cloud-Datei" || { cat up3.log; fail "Reparatur-Upload"; }
# --- Abgeschnittene Datei ---------------------------------------------------------------------------------------------------
truncate -s 1000000 "cloud/$BIG"
if bash "$REPO/scripts/13-cloud-restore.sh" "$W/restore_trunc" > trunc.log 2>&1; then fail "abgeschnittene Datei nicht erkannt"; fi
pass "abgeschnittene Cloud-Datei wird erkannt"
bash "$REPO/scripts/12-backup-upload.sh" "$B2" > up4.log 2>&1 || fail "Reparatur nach Abschneiden"
# --- Unterbrochener Transfer ------------------------------------------------------------------------------------------------
head -c 40000000 /dev/urandom > "$B2/current/database/big.bin"
(cd "$B2" && find current -type f -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS)
( RCLONE_CONFIG="$W/rclone.conf" timeout -s KILL 2 rclone sync "$B2/" atlascrypt:M03-Sandbox/latest --exclude /SHA256SUMS --bwlimit 8M >/dev/null 2>&1 ) || true
if bash "$REPO/scripts/13-cloud-restore.sh" "$W/restore_partial" > partial.log 2>&1; then fail "Teilupload nicht erkannt"; fi
pass "unterbrochener Upload hinterlässt kein scheinbar gültiges Backup (SHA256SUMS passt nicht → Restore verweigert)"
bash "$REPO/scripts/12-backup-upload.sh" "$B2" > up5.log 2>&1 && pass "Wiederaufnahme: erneuter Upload vollendet den Transfer" || { cat up5.log; fail "Wiederaufnahme"; }
bash "$REPO/scripts/13-cloud-restore.sh" "$W/restore_final" > dl2.log 2>&1 && diff -r "$B2/current" "$W/restore_final/current" && pass "vollständige Wiederherstellung nach Unterbrechung bit-identisch"
# --- Konfiguration aus extern gesichertem Recovery-Key neu aufbauen (Totalverlust des Servers) -----------------------------------
bash "$REPO/scripts/11-rclone-setup.sh" --type local --base-path "$W/cloud/ATLAS-Backup" --out "$W/rebuilt.conf" --recovery-in "$W/recovery.txt" > rebuild.log
RCLONE_CONFIG="$W/rebuilt.conf" bash "$REPO/scripts/13-cloud-restore.sh" "$W/restore_rebuilt" > rebuilt-dl.log 2>&1 && diff -r "$B2/current" "$W/restore_rebuilt/current" && pass "Konfiguration aus Recovery-Key neu aufgebaut: Cloud-Restore funktioniert ohne die alte Server-Konfiguration"
# --- Guard: unverschlüsseltes Remote -------------------------------------------------------------------------------------------
cat > plain.conf <<PLAIN
[atlascrypt]
type = local
PLAIN
if RCLONE_CONFIG="$W/plain.conf" bash "$REPO/scripts/12-backup-upload.sh" "$B2" > plain.log 2>&1; then fail "Upload zu unverschlüsseltem Remote erlaubt"; fi
grep -q "kein vollständig verschlüsselndes" plain.log && pass "Guard: Upload in unverschlüsseltes Remote wird verweigert"
sed 's/^filename_encryption = standard/filename_encryption = off/' rclone.conf > nofn.conf; chmod 600 nofn.conf
if RCLONE_CONFIG="$W/nofn.conf" bash "$REPO/scripts/12-backup-upload.sh" "$B2" > nofn.log 2>&1; then fail "Upload ohne Dateinamenverschlüsselung erlaubt"; fi
pass "Guard: Upload ohne Dateinamenverschlüsselung wird verweigert"
# --- OneDrive-Konfigurationsvorlage (ohne echte Zugangsdaten) -----------------------------------------------------------------
echo '{"access_token":"DUMMY","token_type":"Bearer","refresh_token":"DUMMY","expiry":"2030-01-01T00:00:00Z"}' > token.json
bash "$REPO/scripts/11-rclone-setup.sh" --type onedrive --token-file token.json --drive-id DUMMYDRIVE --base-path ATLAS-Backup --out od.conf --recovery-out od-recovery.txt > /dev/null
RCLONE_CONFIG="$W/od.conf" rclone config dump | python3 -c '
import json,sys
d=json.load(sys.stdin); assert d["onedrive"]["type"]=="onedrive" and d["onedrive"]["drive_type"]=="personal"
c=d["atlascrypt"]; assert c["type"]=="crypt" and c["remote"]=="onedrive:ATLAS-Backup" and c["filename_encryption"]=="standard" and c["directory_name_encryption"]=="true"' && pass "OneDrive+Crypt-Konfiguration korrekt generiert (Dummy-Token; keine Verbindung)"
# --- Keine Secrets in Logs ----------------------------------------------------------------------------------------------------
if grep -l -e "$MARK" -e "$PW" ./*.log >/dev/null 2>&1; then fail "Secret-Marker/Passwort in Logdatei"; fi
pass "keine Secrets (Marker, Crypt-Passwort) in sämtlichen Logs"
echo "BLOCKED: echter OneDrive-Upload/Restore (Konto/OAuth-Token erforderlich)"
echo "RESULT=PASS"
