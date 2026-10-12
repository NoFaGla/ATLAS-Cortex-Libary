#!/usr/bin/env bash
# Destruktiver Backup→Destroy→Restore-Test (scripts 06/07/08/09) in einer NACHWEISLICH ISOLIERTEN Wegwerf-Umgebung.
#
# Nur ausführen, wenn M03_ISOLATED_TEST_ENV=1 gesetzt ist UND alle Guards bestehen:
#  - keine Docker-Container/-Volumes außer m03-sandbox-* (keine fremden Projekte)
#  - /opt/atlas-sandbox, /srv/atlas-sandbox, /var/lib/atlas-sandbox, /etc/atlas fehlen ODER tragen unseren Marker
#  - /srv/cortex existiert nicht; /etc/atlas/secrets enthält höchstens module03-sandbox
#  - nur synthetische Daten (werden selbst erzeugt)
# Exit 77 = BLOCKED (Voraussetzung fehlt), 1 = FAIL.
set -euo pipefail
REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
MARK=.m03-restore-test-marker
OPT=/opt/atlas-sandbox/module03; SRV=/srv/atlas-sandbox/module03; VAR=/var/lib/atlas-sandbox/module03; SEC=/etc/atlas/secrets/module03-sandbox
WORK=$(mktemp -d)
say(){ printf '%s\n' "$*"; }
blocked(){ say "RESULT=BLOCKED ($*)"; exit 77; }
fail(){ say "FAIL: $*"; exit 1; }

[ "${M03_ISOLATED_TEST_ENV:-}" = 1 ] || blocked "M03_ISOLATED_TEST_ENV=1 fehlt"
[ "${EUID}" -eq 0 ] || blocked "root erforderlich"
command -v rclone >/dev/null || blocked "rclone fehlt (für den verschlüsselten Cloud-Pfad)"
docker info >/dev/null 2>&1 || blocked "Docker-Daemon nicht erreichbar"
[ ! -e /srv/cortex ] || blocked "/srv/cortex existiert – das ist keine isolierte Testumgebung"
if docker ps -a --format '{{.Names}}' | grep -v '^m03-sandbox-' | grep -q .; then blocked "fremde Container vorhanden"; fi
if docker volume ls -q | grep -v '^m03-sandbox-' | grep -q .; then blocked "fremde Docker-Volumes vorhanden"; fi
for d in /opt/atlas-sandbox /srv/atlas-sandbox /var/lib/atlas-sandbox /etc/atlas; do
  if [ -e "$d" ] && [ ! -f "$d/$MARK" ]; then blocked "$d existiert ohne Test-Marker"; fi
done
if [ -d /etc/atlas/secrets ] && find /etc/atlas/secrets -mindepth 1 -maxdepth 1 ! -name module03-sandbox | grep -q .; then blocked "/etc/atlas/secrets enthält Fremdes"; fi
if [ -e "$OPT" ] || [ -e "$SRV" ] || [ -e "$VAR" ] || [ -e "$SEC" ]; then blocked "Sandbox-Pfade existieren bereits"; fi
for d in /opt/atlas-sandbox /srv/atlas-sandbox /var/lib/atlas-sandbox /etc/atlas; do mkdir -p "$d"; : > "$d/$MARK"; done
say "GUARDS=PASS (isolierte Umgebung, Marker gesetzt)"

final_cleanup(){
  rc=$?
  if [ -d "$OPT/compose" ]; then (cd "$OPT/compose" && docker compose --profile ai down -v --remove-orphans >/dev/null 2>&1) || true; fi
  rm -rf "$OPT" "$SRV" "$VAR" "$SEC" /root/m03-sandbox-last-backup "$WORK"
  rmdir /etc/atlas/secrets 2>/dev/null || true
  for d in /opt/atlas-sandbox /srv/atlas-sandbox /var/lib/atlas-sandbox /etc/atlas; do rm -f "$d/$MARK"; rmdir "$d" 2>/dev/null || true; done
  exit "$rc"
}
trap final_cleanup EXIT

step(){ say "== $*"; }
step "00 preflight"; bash "$REPO/scripts/00-preflight.sh" >"$WORK/pre.log" 2>&1 || { cat "$WORK/pre.log"; blocked "Preflight (z. B. Platz/Ports)"; }
step "01 bootstrap"; bash "$REPO/scripts/01-bootstrap.sh" | tail -1
step "02 core"; bash "$OPT/scripts/02-up-core.sh" | grep -E "CORE=" 
step "03 token"; bash "$OPT/scripts/03-create-api-token.sh"
ENVF="$SEC/paperless-gpt.env"
mkdir -p "$VAR/registry"
step "seed synthetic data"
python3 "$REPO/tests/integration/sandbox_state.py" seed --root "$REPO" --env-file "$ENVF"
python3 "$REPO/tests/integration/sandbox_state.py" snapshot --root "$REPO" --env-file "$ENVF" --out "$WORK/before.json"
step "rclone crypt (lokales Test-Remote außerhalb der Sandbox-Pfade)"
mkdir -p "$WORK/cloud"
bash "$OPT/scripts/11-rclone-setup.sh" --type local --base-path "$WORK/cloud/ATLAS-Backup" --out "$SEC/rclone.conf" --recovery-out "$WORK/recovery-key.txt"
step "06 backup --upload"; bash "$OPT/scripts/06-backup-sandbox.sh" --upload > "$WORK/backup.log" 2>&1 || { cat "$WORK/backup.log"; fail "Backup/Upload"; }
tail -3 "$WORK/backup.log"
grep -q "UPLOAD=PASS" "$WORK/backup.log" && say "PASS: verschlüsselter Upload + Verifikation"
if grep -rqa "paperless_secret_key" "$WORK/cloud"; then fail "Klartext-Dateiname in der Cloud"; fi
SECRET_VALUE=$(cat "$SEC/paperless_secret_key")
if grep -rqaF "$SECRET_VALUE" "$WORK/cloud"; then fail "Secret im Klartext in der Cloud"; fi
if grep -qF "$SECRET_VALUE" "$WORK/backup.log"; then fail "Secret im Backup-Log"; fi
say "PASS: Secrets weder in Cloud-Dateinamen/-Inhalten noch im Log"
LATEST=$(readlink -f "$SRV/backup-staging/latest")
(cd "$LATEST" && sha256sum --quiet -c SHA256SUMS) && say "PASS: Backup-Prüfsummen"
grep -q "paperless_secret_key" <(cd "$LATEST/current/etc" && ls -R) && say "PASS: Secrets im Backup enthalten"
step "pre-destroy guard (erneut)"
if docker ps -a --format '{{.Names}}' | grep -v '^m03-sandbox-' | grep -q .; then fail "fremde Container aufgetaucht"; fi
step "07 destroy"
bash "$OPT/scripts/07-destroy-sandbox.sh" --i-understand-this-deletes-the-sandbox | head -3
for p in "$OPT" "$SRV" "$VAR" "$SEC"; do [ ! -e "$p" ] || fail "$p nach Destroy noch vorhanden"; done
if docker volume ls -q | grep -q '^m03-sandbox-'; then fail "Volumes nach Destroy noch vorhanden"; fi
say "PASS: Sandbox vollständig zerstört (Pfade, Volumes, Secrets)"
step "Cloud-Restore: Konfiguration aus Recovery-Key, lokale Recovery-Kopie wird bewusst entfernt"
rm -rf /root/m03-sandbox-last-backup
bash "$REPO/scripts/11-rclone-setup.sh" --type local --base-path "$WORK/cloud/ATLAS-Backup" --out "$WORK/rclone-recover.conf" --recovery-in "$WORK/recovery-key.txt" >/dev/null
RCLONE_CONFIG="$WORK/rclone-recover.conf" bash "$REPO/scripts/13-cloud-restore.sh" "$WORK/cloud-restore"
step "08 restore (inkl. 09) aus dem Cloud-Backup"
bash "$WORK/cloud-restore/current/opt/module03/scripts/08-restore-sandbox.sh" "$WORK/cloud-restore/current" --i-understand-this-replaces-the-sandbox > "$WORK/restore.log" 2>&1 || { tail -30 "$WORK/restore.log"; fail "Restore"; }
tail -12 "$WORK/restore.log"
step "snapshot nach Restore + Vergleich"
python3 "$REPO/tests/integration/sandbox_state.py" snapshot --root "$REPO" --env-file "$ENVF" --out "$WORK/after.json"
if cmp -s "$WORK/before.json" "$WORK/after.json"; then say "PASS: Dokumente/Hashes/Metadaten/Registry/Assets identisch"; else diff "$WORK/before.json" "$WORK/after.json" | head -30; fail "Zustand nach Restore weicht ab"; fi
python3 - "$REPO" "$VAR/registry/registry.sqlite3" "$ENVF" <<'PY'
import sys; sys.path.insert(0, sys.argv[1] + "/src")
from atlas_library.read import LibraryRead
from atlas_library.registry import Registry
from atlas_library.paperless import ReadClient
tok = next(l.split("=",1)[1].strip() for l in open(sys.argv[3]) if l.startswith("PAPERLESS_API_TOKEN="))
reg = Registry(sys.argv[2]); lr = LibraryRead(reg, ReadClient("http://127.0.0.1:18000", tok), None)
n = 0
with reg._conn() as c:
    rows = c.execute("SELECT atlas_id FROM entries WHERE kind='document'").fetchall()
for e in rows:
    ref = reg.pin(e["atlas_id"]); f = lr.get_document_file(ref)
    assert f["status"] == "ok", (ref, f.get("status")); n += 1
print(f"PASS: {n} gepinnte Referenzen lösen nach Restore auf und liefern hash-geprüfte Originale")
PY
say "RESULT=PASS"
