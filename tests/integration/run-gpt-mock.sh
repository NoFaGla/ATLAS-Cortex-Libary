#!/usr/bin/env bash
# Paperless-GPT (echtes, gepinntes Image) + Mock-LLM + echtes Paperless. Exit 77 = BLOCKED (kein Docker).
set -euo pipefail
# shellcheck source=tests/integration/lib-stack.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib-stack.sh"
cleanup() { rc=$?; stack_down; exit "$rc"; }
trap cleanup EXIT
stack_up
cd "$WORK/compose"
# Taxonomie (inkl. System-Tags) vor dem Start von Paperless-GPT
ATLAS_PAPERLESS_URL="$PAPERLESS_URL" ATLAS_PAPERLESS_ADMIN_TOKEN="$PAPERLESS_TOKEN" PYTHONPATH="$REPO/src" \
  python3 -m atlas_library.cli --registry "$WORK/registry.sqlite3" taxonomy >/dev/null
mockllm_up
cat > "$WORK/sec/paperless-gpt.env" <<ENVEOF
PAPERLESS_API_TOKEN=$PAPERLESS_TOKEN
LLM_PROVIDER=openai
LLM_MODEL=mock-model
OPENAI_API_KEY=mock-key-not-real
OPENAI_BASE_URL=http://mockllm:8000/v1
ENVEOF
chmod 600 "$WORK/sec/paperless-gpt.env"
docker compose --profile ai up -d paperless-gpt
sleep 5
export ATLAS_E2E_URL="$PAPERLESS_URL" ATLAS_E2E_TOKEN="$PAPERLESS_TOKEN" ATLAS_E2E_CONSUME="$STACK_WORK/srv/consume" ATLAS_E2E_COMPOSE="$WORK/compose"
export ATLAS_E2E_REPORT="${ATLAS_E2E_REPORT:-/tmp/gpt-mock-observations.json}"
cd "$REPO"
python3 -m pytest -q -p no:cacheprovider tests/e2e/test_gpt_mock.py -x -v
echo "RESULT=PASS"
