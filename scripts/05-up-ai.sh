#!/usr/bin/env bash
set -euo pipefail
[ "${EUID}" -eq 0 ] || { echo "Bitte mit sudo/root ausführen." >&2; exit 1; }
SEC=/etc/atlas/secrets/module03-sandbox/paperless-gpt.env
if grep -Eq 'REPLACE_(AFTER_CORE_START|MODEL|SECRET)' "$SEC"; then echo "STOP: $SEC enthält Platzhalter." >&2; exit 1; fi
cd /opt/atlas-sandbox/module03/compose
if ! docker compose --profile ai pull paperless-gpt; then
  echo "STOP: gepinntes 0.29.0-Image nicht pullbar. Nicht auf latest wechseln; Version bewusst prüfen." >&2
  exit 1
fi
docker compose --profile ai up -d paperless-gpt
sleep 3
docker compose --profile ai ps paperless-gpt
if curl -fsSI http://127.0.0.1:18080/ >/dev/null; then echo "AI_UI=PASS"; else docker compose --profile ai logs --tail=150 paperless-gpt; exit 1; fi
