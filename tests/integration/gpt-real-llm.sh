#!/usr/bin/env bash
# VORBEREITETER Test mit ECHTEM LLM (OpenAI oder Anthropic). Läuft NUR mit ausdrücklicher Freigabe und Schlüssel aus der Umgebung:
#   M03_REAL_LLM=1 LLM_PROVIDER=anthropic LLM_MODEL=<modell> ANTHROPIC_API_KEY=... bash tests/integration/gpt-real-llm.sh
#   M03_REAL_LLM=1 LLM_PROVIDER=openai    LLM_MODEL=<modell> OPENAI_API_KEY=...    bash tests/integration/gpt-real-llm.sh
# Es werden ausschließlich SYNTHETISCHE Dokumente (siehe atlas_library/synthetic.py) an den externen Anbieter gesendet.
# Schlüssel stehen nie im Repo/CI; sie werden nur in eine 0600-Datei im Temp-Verzeichnis des Teststacks geschrieben und danach gelöscht.
# Exit 77 = BLOCKED (keine Freigabe / kein Schlüssel / kein Docker).
set -euo pipefail
[ "${M03_REAL_LLM:-}" = 1 ] || { echo "RESULT=BLOCKED (M03_REAL_LLM=1 fehlt — keine Freigabe für externe LLM-Aufrufe)"; exit 77; }
PROVIDER=${LLM_PROVIDER:-}; MODEL=${LLM_MODEL:-}
case "$PROVIDER" in
  anthropic) KEYVAR=ANTHROPIC_API_KEY ;; openai) KEYVAR=OPENAI_API_KEY ;;
  *) echo "RESULT=BLOCKED (LLM_PROVIDER muss anthropic oder openai sein)"; exit 77 ;;
esac
[ -n "$MODEL" ] && [ -n "${!KEYVAR:-}" ] || { echo "RESULT=BLOCKED (LLM_MODEL oder $KEYVAR nicht gesetzt)"; exit 77; }
# shellcheck source=tests/integration/lib-stack.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib-stack.sh"
cleanup() { rc=$?; stack_down; exit "$rc"; }
trap cleanup EXIT
stack_up
cd "$WORK/compose"
ATLAS_PAPERLESS_URL="$PAPERLESS_URL" ATLAS_PAPERLESS_ADMIN_TOKEN="$PAPERLESS_TOKEN" PYTHONPATH="$REPO/src" \
  python3 -m atlas_library.cli --registry "$WORK/registry.sqlite3" taxonomy >/dev/null
umask 077
{ echo "PAPERLESS_API_TOKEN=$PAPERLESS_TOKEN"; echo "LLM_PROVIDER=$PROVIDER"; echo "LLM_MODEL=$MODEL"; echo "$KEYVAR=${!KEYVAR}"; } > "$WORK/sec/paperless-gpt.env"
docker compose --profile ai up -d paperless-gpt
sleep 5
export ATLAS_E2E_URL="$PAPERLESS_URL" ATLAS_E2E_TOKEN="$PAPERLESS_TOKEN" ATLAS_E2E_CONSUME="$STACK_WORK/srv/consume" ATLAS_E2E_COMPOSE="$WORK/compose"
export ATLAS_E2E_REPORT="${ATLAS_E2E_REPORT:-/tmp/gpt-real-observations.json}"
cd "$REPO"
python3 -m pytest -q -p no:cacheprovider tests/e2e/test_gpt_real.py -x -v
# Sicherheitsprüfung: der Schlüssel darf in keinem Container-Log stehen
if docker compose -f "$WORK/compose/docker-compose.yml" --profile ai logs 2>&1 | grep -qF "${!KEYVAR}"; then echo "FAIL: API-Schlüssel im Container-Log"; exit 1; fi
echo "PASS: API-Schlüssel nicht in Container-Logs"
echo "RESULT=PASS"
