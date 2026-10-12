#!/usr/bin/env bash
set -euo pipefail
if [ "${EUID}" -ne 0 ]; then echo "Bitte mit sudo/root ausführen." >&2; exit 1; fi
SRC=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
OPT=/opt/atlas-sandbox/module03
SRV=/srv/atlas-sandbox/module03
VAR=/var/lib/atlas-sandbox/module03
SEC=/etc/atlas/secrets/module03-sandbox
REAL_USER=${SUDO_USER:-root}
if [ "$REAL_USER" = root ]; then HOST_UID=1000; HOST_GID=1000; else HOST_UID=$(id -u "$REAL_USER"); HOST_GID=$(id -g "$REAL_USER"); fi

install -d -m 0755 "$OPT" "$SRV" "$VAR"
install -d -m 0755 "$SRV/media" "$SRV/consume" "$SRV/export" "$SRV/assets" "$SRV/testdata" "$SRV/backup-staging"
install -d -m 0755 "$VAR/paperless-gpt/prompts" "$VAR/paperless-gpt/config" "$VAR/paperless-gpt/db" "$VAR/registry"
install -d -m 0700 "$SEC"

if command -v rsync >/dev/null 2>&1; then rsync -a --delete --exclude '*.zip' "$SRC/" "$OPT/"; else cp -a "$SRC/." "$OPT/"; fi
[ -f "$OPT/compose/.env" ] || cp "$OPT/compose/.env.example" "$OPT/compose/.env"
sed -i "s/^HOST_UID=.*/HOST_UID=$HOST_UID/; s/^HOST_GID=.*/HOST_GID=$HOST_GID/" "$OPT/compose/.env"
[ -f "$OPT/compose/paperless.env" ] || cp "$OPT/compose/paperless.env.example" "$OPT/compose/paperless.env"

umask 077
make_secret(){
  local f="$SEC/$1" n="$2"
  if [ ! -s "$f" ]; then python3 -c "import secrets; print(secrets.token_urlsafe($n))" > "$f"; fi
  chmod 600 "$f"; chown root:root "$f"
}
make_secret postgres_password 32
make_secret paperless_secret_key 64
make_secret paperless_admin_password 24
if [ ! -s "$SEC/paperless_admin_user" ]; then printf '%s\n' 'atlas-admin' > "$SEC/paperless_admin_user"; fi
chmod 600 "$SEC/paperless_admin_user"
ADMIN_USER=$(cat "$SEC/paperless_admin_user")
sed -i "s/^PAPERLESS_ADMIN_USER=.*/PAPERLESS_ADMIN_USER=$ADMIN_USER/" "$OPT/compose/paperless.env"

if [ ! -f "$SEC/paperless-gpt.env" ]; then cp "$OPT/compose/paperless-gpt.env.example" "$SEC/paperless-gpt.env"; fi
chmod 600 "$SEC/paperless-gpt.env"
chown -R "$HOST_UID:$HOST_GID" "$SRV/media" "$SRV/consume" "$SRV/export" "$SRV/assets" "$SRV/testdata" "$VAR/paperless-gpt"
chmod -R u+rwX,go-rwx "$VAR/paperless-gpt"
chmod 700 "$SEC"
chmod +x "$OPT/scripts"/*.sh
printf 'BOOTSTRAP=PASS\nPaket=%s\nDaten=%s\nRuntime=%s\nSecrets=%s\nAdmin=%s\n' "$OPT" "$SRV" "$VAR" "$SEC" "$ADMIN_USER"
