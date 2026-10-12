#!/usr/bin/env bash
# Prüft Docker-Isolation, Portbindungen, Image-Pins und Secret-Rechte eines laufenden Projekts.
#   14-security-check.sh [--project m03-sandbox] [--secrets /etc/atlas/secrets/module03-sandbox]
# Exit 0 = alle Prüfungen bestanden, 1 = mindestens eine fehlgeschlagen.
set -euo pipefail
PROJECT=m03-sandbox; SECDIR=""
while [ $# -gt 0 ]; do
  case "$1" in --project) PROJECT=$2; shift 2 ;; --secrets) SECDIR=$2; shift 2 ;; *) echo "unbekannte Option $1" >&2; exit 2 ;; esac
done
command -v docker >/dev/null && docker info >/dev/null 2>&1 || { echo "BLOCKED: Docker nicht erreichbar"; exit 77; }
IDS=$(docker ps -q --filter "label=com.docker.compose.project=$PROJECT")
[ -n "$IDS" ] || { echo "FAIL: keine laufenden Container im Projekt $PROJECT"; exit 1; }
rc=0
TMP=$(mktemp); trap 'rm -f "$TMP"' EXIT
# shellcheck disable=SC2086
docker inspect $IDS > "$TMP"
python3 - "$TMP" <<'PY' || rc=1
import json, sys
fail = 0
def check(ok, msg):
    global fail
    print(("PASS: " if ok else "FAIL: ") + msg)
    fail += 0 if ok else 1
for c in json.load(open(sys.argv[1])):
    n = c["Name"].lstrip("/"); hc = c["HostConfig"]
    check(not hc.get("Privileged"), f"{n}: nicht privilegiert")
    check(hc.get("NetworkMode") != "host" and not hc.get("PidMode") and hc.get("IpcMode") != "host", f"{n}: kein Host-Netz/-PID/-IPC")
    check(not hc.get("CapAdd"), f"{n}: keine zusätzlichen Capabilities")
    check(any(o.startswith("no-new-privileges") for o in (hc.get("SecurityOpt") or [])), f"{n}: no-new-privileges")
    check(not any("docker.sock" in m.get("Source", "") for m in c.get("Mounts", [])), f"{n}: kein docker.sock gemountet")
    check(not any(m.get("Source", "") in ("/", "/etc", "/root", "/home", "/var/run") for m in c.get("Mounts", [])), f"{n}: keine Wurzel-/Systempfade gemountet")
    for port, binds in (c["NetworkSettings"].get("Ports") or {}).items():
        for b in binds or []:
            check(b["HostIp"] == "127.0.0.1", f"{n}: Port {port} nur an 127.0.0.1 (ist {b['HostIp']}:{b['HostPort']})")
    img = c["Config"]["Image"]
    check("@sha256:" in img, f"{n}: Image per Digest gepinnt ({img.split('@')[0]})")
sys.exit(1 if fail else 0)
PY
if [ -n "$SECDIR" ]; then
  [ "$(stat -c %a "$SECDIR")" = 700 ] && echo "PASS: $SECDIR 0700" || { echo "FAIL: $SECDIR nicht 0700"; rc=1; }
  while IFS= read -r f; do
    [ "$(stat -c %a "$f")" = 600 ] && [ "$(stat -c %U "$f")" = root ] || { echo "FAIL: Secret-Datei $(basename "$f") nicht root:0600"; rc=1; }
  done < <(find "$SECDIR" -type f)
  echo "INFO: Secret-Dateien geprüft (Namen/Rechte, Inhalte werden nie gelesen)"
fi
exit $rc
