#!/usr/bin/env bash
set -euo pipefail
fail=0
say(){ printf '%s\n' "$*"; }
need(){ if command -v "$1" >/dev/null 2>&1; then say "[OK] $1: $(command -v "$1")"; else say "[FAIL] fehlt: $1"; fail=1; fi; }
optional(){ if command -v "$1" >/dev/null 2>&1; then say "[OK] optional $1"; else say "[INFO] optional fehlt (vor Backup nötig): $1"; fi; }

say "== M03 Sandbox Preflight =="
need docker
if docker compose version >/dev/null 2>&1; then say "[OK] docker compose: $(docker compose version)"; else say "[FAIL] docker compose fehlt"; fail=1; fi
need curl
need python3
optional rclone
optional rsync

if command -v docker >/dev/null 2>&1 && ! docker info >/dev/null 2>&1; then say "[FAIL] Docker-Daemon nicht erreichbar/Rechte fehlen"; fail=1; fi

for p in /opt/atlas-sandbox/module03 /srv/atlas-sandbox/module03 /var/lib/atlas-sandbox/module03 /etc/atlas/secrets/module03-sandbox; do
  [ -e "$p" ] && say "[INFO] existiert bereits: $p"
done

for port in 18000 18080; do
  if ss -ltn 2>/dev/null | awk '{print $4}' | grep -Eq "(^|:)${port}$"; then say "[FAIL] Port $port belegt"; fail=1; else say "[OK] Port $port frei"; fi
done

avail_kb=$(df -Pk / | awk 'NR==2{print $4}')
if [ "${avail_kb:-0}" -lt $((20*1024*1024)) ]; then say "[FAIL] weniger als 20 GiB frei"; fail=1; else say "[OK] mindestens 20 GiB frei"; fi

if [ "$fail" -ne 0 ]; then say "PRECHECK=FAIL"; exit 1; fi
say "PRECHECK=PASS"
