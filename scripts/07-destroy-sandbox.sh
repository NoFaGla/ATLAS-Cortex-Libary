#!/usr/bin/env bash
set -euo pipefail
[ "${EUID}" -eq 0 ] || { echo "Bitte mit sudo/root ausführen." >&2; exit 1; }
[ "${1:-}" = "--i-understand-this-deletes-the-sandbox" ] || { echo "ABBRUCH: Bestätigungsschalter fehlt." >&2; exit 1; }
OPT=/opt/atlas-sandbox/module03; SRV=/srv/atlas-sandbox/module03; VAR=/var/lib/atlas-sandbox/module03; SEC=/etc/atlas/secrets/module03-sandbox
LATEST=$(readlink -f "$SRV/backup-staging/latest" 2>/dev/null || true)
[ -n "$LATEST" ] && [ -f "$LATEST/SHA256SUMS" ] || { echo "STOP: kein lokales Backup erkennbar" >&2; exit 1; }
SAFE=/root/m03-sandbox-last-backup; rm -rf "$SAFE"; mkdir -p "$SAFE"; cp -a "$LATEST/." "$SAFE/"
cd "$OPT/compose"; docker compose --profile ai down -v --remove-orphans
rm -rf "$OPT" "$VAR" "$SEC" "$SRV"
printf 'DESTROY=PASS\nTemporäre lokale Recovery-Kopie: %s\n' "$SAFE"
