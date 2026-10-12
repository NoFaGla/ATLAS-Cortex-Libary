#!/usr/bin/env bash
set -euo pipefail
[ "${EUID}" -eq 0 ] || { echo "Bitte mit sudo/root ausführen." >&2; exit 1; }
for c in tar sha256sum docker python3; do command -v "$c" >/dev/null || { echo "fehlt: $c" >&2; exit 1; }; done
UPLOAD=0; [ "${1:-}" = "--upload" ] && UPLOAD=1
[ "$UPLOAD" -eq 0 ] || command -v rclone >/dev/null || { echo "rclone fehlt" >&2; exit 1; }
OPT=/opt/atlas-sandbox/module03; SRV=/srv/atlas-sandbox/module03; VAR=/var/lib/atlas-sandbox/module03; SEC=/etc/atlas/secrets/module03-sandbox
STAMP=$(date -u +%Y%m%dT%H%M%SZ); BASE="$SRV/backup-staging/$STAMP"; CURRENT="$BASE/current"
umask 077
mkdir -p "$CURRENT"/{opt,srv,var,etc,database,paperless-export,docker-volumes,manifest}
cd "$OPT/compose"
cleanup(){ docker compose --profile ai start >/dev/null 2>&1 || true; }; trap cleanup EXIT
rm -rf "$SRV/export"/*
docker compose exec -T webserver document_exporter ../export -c
cp -a "$SRV/export/." "$CURRENT/paperless-export/"
docker compose exec -T db pg_dump -U paperless -d paperless -Fc > "$CURRENT/database/paperless.dump"
cp -a "$OPT" "$CURRENT/opt/module03"; cp -a "$SEC" "$CURRENT/etc/module03-sandbox-secrets"
mkdir -p "$CURRENT/srv/module03" "$CURRENT/var/module03"
if command -v rsync >/dev/null 2>&1; then
  rsync -aHAX --exclude backup-staging/ "$SRV/" "$CURRENT/srv/module03/"; rsync -aHAX "$VAR/" "$CURRENT/var/module03/"
else
  tar -C "$SRV" --exclude=backup-staging -cf - . | tar -C "$CURRENT/srv/module03" -xf -; cp -a "$VAR/." "$CURRENT/var/module03/"
fi
docker compose --profile ai stop
for vol in m03-sandbox-paperless-data m03-sandbox-pgdata m03-sandbox-redisdata; do
  docker volume inspect "$vol" >/dev/null 2>&1 || continue
  docker run --rm -v "$vol:/from:ro" -v "$CURRENT/docker-volumes:/to" alpine:3.22 sh -c "cd /from && tar -czf /to/${vol}.tar.gz ."
done
{
  echo "backup_utc=$STAMP"; echo "hostname=$(hostname)"; echo "kernel=$(uname -a)"; echo "docker=$(docker --version)"; echo "compose=$(docker compose version)"
  docker compose --profile ai config --images
} > "$CURRENT/manifest/versions.txt"
docker compose --profile ai config > "$CURRENT/manifest/compose.resolved.yml"
# relative Pfade: Prüfsummen bleiben nach Cloud-Download/Restore an anderem Ort gültig
(cd "$BASE" && find current -type f -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS)
ln -sfn "$BASE" "$SRV/backup-staging/latest"
echo "LOCAL_BACKUP=$BASE"
if [ "$UPLOAD" -eq 1 ]; then
  CONF="$SEC/rclone.conf"; [ -s "$CONF" ] || { echo "STOP: $CONF fehlt (scripts/11-rclone-setup.sh)" >&2; exit 1; }
  RCLONE_CONFIG="$CONF" bash "$OPT/scripts/12-backup-upload.sh" "$BASE"
fi
echo "BACKUP=PASS"
