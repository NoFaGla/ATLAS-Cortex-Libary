#!/usr/bin/env bash
# E2E: isolierter Paperless-Teststack + pytest tests/e2e. Exit 77 = BLOCKED (kein Docker).
set -euo pipefail
# shellcheck source=tests/integration/lib-stack.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib-stack.sh"
cleanup() { rc=$?; stack_down; exit "$rc"; }
trap cleanup EXIT
stack_up
export ATLAS_E2E_URL="$PAPERLESS_URL" ATLAS_E2E_TOKEN="$PAPERLESS_TOKEN" ATLAS_E2E_CONSUME="$STACK_WORK/srv/consume"
export ATLAS_E2E_REPORT="${ATLAS_E2E_REPORT:-/tmp/e2e-observations.json}"
cd "$REPO"
python3 -m pytest -q -p no:cacheprovider tests/e2e/test_e2e.py -x -v
echo "RESULT=PASS"
