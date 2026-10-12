#!/usr/bin/env bash
set -euo pipefail
[ "${EUID}" -eq 0 ] || { echo "Bitte mit sudo/root ausführen." >&2; exit 1; }
[ "${2:-}" = "--i-understand-this-replaces-the-sandbox" ] || { echo "ABBRUCH: Aufruf: 08-restore-sandbox.sh <backup-dir> --i-understand-this-replaces-the-sandbox (ersetzt Sandbox-Pfade)" >&2; exit 1; }
BACKUP=${1:-}; [ -d "$BACKUP/opt/module03" ] || { echo "Ungültiges Backup" >&2; exit 1; }; [ -d "$BACKUP/etc/module03-sandbox-secrets" ] || { echo "Secrets fehlen" >&2; exit 1; }
OPT=/opt/atlas-sandbox/module03; SRV=/srv/atlas-sandbox/module03; VAR=/var/lib/atlas-sandbox/module03; SEC=/etc/atlas/secrets/module03-sandbox
rm -rf "$OPT" "$SRV" "$VAR" "$SEC"; mkdir -p /opt/atlas-sandbox /srv/atlas-sandbox /var/lib/atlas-sandbox /etc/atlas/secrets
cp -a "$BACKUP/opt/module03" "$OPT"; cp -a "$BACKUP/srv/module03" "$SRV"; cp -a "$BACKUP/var/module03" "$VAR"; cp -a "$BACKUP/etc/module03-sandbox-secrets" "$SEC"
chmod 700 "$SEC"; chmod 600 "$SEC"/* 2>/dev/null || true; chmod +x "$OPT/scripts"/*.sh
cd "$OPT/compose"; docker compose --profile ai create broker db webserver >/dev/null
for vol in m03-sandbox-paperless-data m03-sandbox-pgdata m03-sandbox-redisdata; do
  arc="$BACKUP/docker-volumes/${vol}.tar.gz"; [ -f "$arc" ] || continue
  docker run --rm -v "$vol:/to" -v "$BACKUP/docker-volumes:/from:ro" alpine:3.22 sh -c "find /to -mindepth 1 -maxdepth 1 -exec rm -rf {} +; tar -xzf /from/${vol}.tar.gz -C /to"
done
docker compose --profile ai up -d
for _ in $(seq 1 90); do
  if curl -fsS http://127.0.0.1:18000/api/ >/dev/null 2>&1; then echo "RESTORE_CORE=PASS"; "$OPT/scripts/09-post-restore-check.sh"; exit 0; fi
  sleep 2
done
echo "RESTORE=FAIL"; docker compose --profile ai logs --tail=200; exit 1
