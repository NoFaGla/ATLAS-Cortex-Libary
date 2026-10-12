#!/usr/bin/env bash
set -euo pipefail
OPT=/opt/atlas-sandbox/module03; cd "$OPT/compose"
docker compose exec -T webserver document_sanity_checker
SEC=/etc/atlas/secrets/module03-sandbox; USER=$(cat "$SEC/paperless_admin_user"); PASS=$(cat "$SEC/paperless_admin_password")
PAYLOAD=$(python3 - "$USER" "$PASS" <<'PYCHECK'
import json,sys
print(json.dumps({'username':sys.argv[1],'password':sys.argv[2]}))
PYCHECK
)
TOKEN=$(curl -fsS -X POST http://127.0.0.1:18000/api/token/ -H 'Content-Type: application/json' --data "$PAYLOAD" | python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])')
curl -fsSI http://127.0.0.1:18000/api/documents/ -H "Authorization: Token $TOKEN" -H 'Accept: application/json; version=10' | sed -n '1,20p'
echo "POST_RESTORE_CHECK=PASS"
