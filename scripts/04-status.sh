#!/usr/bin/env bash
set -euo pipefail
cd /opt/atlas-sandbox/module03/compose
docker compose --profile ai ps
printf '\n== Paperless API ==\n'; curl -sSI http://127.0.0.1:18000/api/ | sed -n '1,12p' || true
printf '\n== Disk ==\n'; df -h /srv/atlas-sandbox/module03 /var/lib/atlas-sandbox/module03 2>/dev/null || true
printf '\n== Images ==\n'; docker compose --profile ai config --images
