#!/usr/bin/env bash
set -euo pipefail
[ "${EUID}" -eq 0 ] || { echo "Bitte mit sudo/root ausführen." >&2; exit 1; }
SEC=/etc/atlas/secrets/module03-sandbox
ADMIN_USER=$(cat "$SEC/paperless_admin_user")
ADMIN_PASS=$(cat "$SEC/paperless_admin_password")
PAYLOAD=$(python3 - "$ADMIN_USER" "$ADMIN_PASS" <<'PYTOKEN'
import json,sys
print(json.dumps({'username':sys.argv[1],'password':sys.argv[2]}))
PYTOKEN
)
OUT=$(curl -fsS -X POST http://127.0.0.1:18000/api/token/ -H 'Content-Type: application/json' --data "$PAYLOAD")
TOKEN=$(printf '%s' "$OUT" | python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])')
ENV="$SEC/paperless-gpt.env"
python3 - "$ENV" "$TOKEN" <<'PYWRITE'
from pathlib import Path
import sys
p=Path(sys.argv[1]); token=sys.argv[2]
lines=p.read_text().splitlines(); out=[]; done=False
for line in lines:
    if line.startswith('PAPERLESS_API_TOKEN='): out.append('PAPERLESS_API_TOKEN='+token); done=True
    else: out.append(line)
if not done: out.append('PAPERLESS_API_TOKEN='+token)
p.write_text('\n'.join(out)+'\n')
PYWRITE
chmod 600 "$ENV"
echo "TOKEN=PASS"
