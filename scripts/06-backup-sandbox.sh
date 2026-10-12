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
  echo "paperless_image=ghcr.io/paperless-ngx/paperless-ngx:3.3.0"; echo "postgres_image=postgres:18"; echo "valkey_image=valkey:9-alpine"; grep '^PAPERLESS_GPT_IMAGE=' "$OPT/compose/.env" || true
} > "$CURRENT/manifest/versions.txt"
docker compose --profile ai config > "$CURRENT/manifest/compose.resolved.yml"
find "$CURRENT" -type f -print0 | sort -z | xargs -0 sha256sum > "$BASE/SHA256SUMS"
ln -sfn "$BASE" "$SRV/backup-staging/latest"
echo "LOCAL_BACKUP=$BASE"
if [ "$UPLOAD" -eq 1 ]; then
  CONF="$SEC/rclone.conf"; [ -s "$CONF" ] || { echo "STOP: $CONF fehlt" >&2; exit 1; }
  export RCLONE_CONFIG="$CONF"; TARGET="atlascrypt:M03-Sandbox"
  # Backup enthält Secrets: Upload nur, wenn atlascrypt tatsächlich ein crypt-Remote ist.
  rclone config dump | python3 -c 'import json,sys; d=json.load(sys.stdin).get("atlascrypt",{}); sys.exit(0 if d.get("type")=="crypt" else 1)' \
    || { echo "STOP: Remote atlascrypt fehlt oder ist kein crypt-Remote; unverschlüsselter Upload verweigert" >&2; exit 1; }
  rclone sync "$CURRENT/" "$TARGET/current" --backup-dir "$TARGET/versions/$STAMP" --create-empty-src-dirs --checkers 4 --transfers 2 --checksum
  rclone copyto "$BASE/SHA256SUMS" "$TARGET/manifests/$STAMP-SHA256SUMS"
  rclone check "$CURRENT/" "$TARGET/current" --one-way --checksum
  echo "UPLOAD=PASS"
fi
echo "BACKUP=PASS"
