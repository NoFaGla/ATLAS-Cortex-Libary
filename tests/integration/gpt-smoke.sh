#!/usr/bin/env bash
# Paperless-GPT-Integrationstest OHNE LLM-Zugang: Startet das gepinnte Image gegen den echten Paperless-Teststack und prüft
# Start, Paperless-Verbindung, Tag-Anlage, Loopback-Bindung. Der eigentliche Enrichment-Funktionstest (Titel/Datum/Korrespondent
# per LLM) ist ohne LLM-Zugang BLOCKED und wird hier ausdrücklich NICHT behauptet. Exit 77 = BLOCKED (kein Docker).
set -euo pipefail
# shellcheck source=tests/integration/lib-stack.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib-stack.sh"
cleanup() { rc=$?; stack_down; exit "$rc"; }
trap cleanup EXIT
stack_up
cd "$WORK/compose"
# Dummy-Provider: ollama auf einem unerreichbaren Loopback-Port. Keine echten Schlüssel.
cat > "$WORK/sec/paperless-gpt.env" <<ENVEOF
PAPERLESS_API_TOKEN=$PAPERLESS_TOKEN
LLM_PROVIDER=ollama
LLM_MODEL=dummy-model
OLLAMA_HOST=http://127.0.0.1:1
ENVEOF
chmod 600 "$WORK/sec/paperless-gpt.env"
# Taxonomie (inkl. System/Paperless-GPT-*-Tags) zuerst, wie im Buildplan Gate F vor Gate E/G
ATLAS_PAPERLESS_URL="$PAPERLESS_URL" ATLAS_PAPERLESS_ADMIN_TOKEN="$PAPERLESS_TOKEN" \
  python3 -m atlas_library.cli --registry "$WORK/registry.sqlite3" taxonomy
docker compose --profile ai up -d paperless-gpt
ok=""
for _ in $(seq 1 40); do
  if curl -fsS -o /dev/null "http://127.0.0.1:28080/"; then ok=1; break; fi
  sleep 3
done
if [ -z "$ok" ]; then docker compose --profile ai logs --tail=60 paperless-gpt; echo "FAIL: Paperless-GPT-UI nicht erreichbar"; exit 1; fi
echo "PASS: Paperless-GPT-UI antwortet auf 127.0.0.1:28080"
state=$(docker compose --profile ai ps paperless-gpt --format '{{.State}}')
[ "$state" = running ] && echo "PASS: Container läuft (kein Crash-Loop)" || { echo "FAIL: Zustand $state"; exit 1; }
assert_loopback_only paperless-gpt
echo "PASS: UI nur an 127.0.0.1 gebunden"
sleep 5
logs=$(docker compose --profile ai logs paperless-gpt 2>&1)
echo "$logs" | tail -15
tags=$(curl -fsS "$PAPERLESS_URL/api/tags/?page_size=100" -H "Authorization: Token $PAPERLESS_TOKEN" | python3 -c 'import json,sys;print(" ".join(sorted(t["name"] for t in json.load(sys.stdin)["results"])))')
echo "INFO: Paperless-Tags nach GPT-Start: $tags"
for t in "System/Paperless-GPT-Queue" "System/Paperless-GPT-Done" "System/Paperless-GPT-Failed"; do
  case " $tags " in *"$t"*) echo "PASS: Tag $t von Paperless-GPT angelegt/vorhanden" ;; *) echo "FAIL: Tag $t fehlt"; exit 1 ;; esac
done
echo "BLOCKED: LLM-gestützte Anreicherung (kein LLM-Zugang/Testkonto)"
echo "RESULT=PASS (nur Start/Verbindung/Konfiguration)"
