#!/usr/bin/env bash
# Hilfsfunktionen für isolierte Paperless-Teststacks (Projekt m03-ci, Port 28000, Temp-Verzeichnis).
# Einbinden mit `source`. Berührt weder /srv/atlas-sandbox noch /etc/atlas noch fremde Docker-Projekte.
# shellcheck shell=bash disable=SC2034
REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
PORT=${M03_CI_PORT:-28000}
export COMPOSE_PROJECT_NAME=m03-ci

stack_up() {
  if ! docker info >/dev/null 2>&1; then echo "RESULT=BLOCKED (Docker-Daemon nicht erreichbar)"; exit 77; fi
  if docker volume ls -q | grep -q '^m03-ci-'; then echo "STOP: m03-ci-* Volumes existieren bereits" >&2; exit 1; fi
  WORK=$(mktemp -d); chmod 700 "$WORK"
  mkdir -p "$WORK"/{compose,sec,srv/media,srv/consume,srv/export}
  chown -R 1000:1000 "$WORK/srv"
  sed -e "s#/etc/atlas/secrets/module03-sandbox#$WORK/sec#g" -e "s#/srv/atlas-sandbox/module03#$WORK/srv#g" \
      -e "s#/var/lib/atlas-sandbox/module03#$WORK/var#g" \
      -e "s#m03-sandbox#m03-ci#g" -e "s#127.0.0.1:18000:8000#127.0.0.1:$PORT:8000#" -e "s#127.0.0.1:18080:8080#127.0.0.1:28080:8080#" \
      "$REPO/compose/docker-compose.yml" > "$WORK/compose/docker-compose.yml"
  cp "$REPO/compose/paperless.env.example" "$WORK/compose/paperless.env"
  # Testumgebung: Consume-Verzeichnis per Polling beobachten (inotify auf Bind-Mounts ist nicht überall verfügbar).
  printf 'PAPERLESS_CONSUMER_POLLING=2\n' >> "$WORK/compose/paperless.env"
  cp "$REPO/compose/.env.example" "$WORK/compose/.env"
  for f in postgres_password paperless_secret_key paperless_admin_password; do python3 -c 'import secrets;print(secrets.token_urlsafe(32))' > "$WORK/sec/$f"; done
  cp "$REPO/compose/paperless-gpt.env.example" "$WORK/sec/paperless-gpt.env"
  mkdir -p "$WORK"/var/paperless-gpt/{prompts,config,db}
  cd "$WORK/compose" || exit 1
  docker compose up -d broker db webserver
  for _ in $(seq 1 120); do curl -fsS "http://127.0.0.1:$PORT/api/" >/dev/null 2>&1 && break; sleep 3; done
  curl -fsS "http://127.0.0.1:$PORT/api/" >/dev/null || { docker compose logs --tail=80 webserver; echo "FAIL: API nicht erreichbar"; return 1; }
  ADMIN=$(grep '^PAPERLESS_ADMIN_USER=' paperless.env | cut -d= -f2)
  TOKEN=$(python3 - "$ADMIN" "$(cat "$WORK/sec/paperless_admin_password")" <<'PY' | curl -fsS -X POST "http://127.0.0.1:$PORT/api/token/" -H 'Content-Type: application/json' --data @- | python3 -c 'import json,sys;print(json.load(sys.stdin)["token"])'
import json,sys
print(json.dumps({"username":sys.argv[1],"password":sys.argv[2]}))
PY
)
  export PAPERLESS_URL="http://127.0.0.1:$PORT" PAPERLESS_TOKEN="$TOKEN" STACK_WORK="$WORK"
}

stack_down() {
  mockllm_down
  if [ -n "${WORK:-}" ] && [ -d "$WORK/compose" ]; then
    (cd "$WORK/compose" && docker compose --profile ai down -v --remove-orphans >/dev/null 2>&1) || true
    rm -rf "$WORK"
  fi
}

# Prüft über die Docker-Port-Zuordnung (nicht über ss/netstat, die in Minimal-Images fehlen können), dass ALLE veröffentlichten
# Host-Ports des Dienstes an 127.0.0.1 gebunden sind und mindestens einer existiert.
assert_loopback_only() {
  local svc=$1 ports n bad
  ports=$(docker compose --profile ai ps "$svc" --format '{{json .Publishers}}')
  n=$(printf '%s' "$ports" | python3 -c 'import json,sys;print(len([p for p in json.load(sys.stdin) if p.get("PublishedPort")]))')
  bad=$(printf '%s' "$ports" | python3 -c 'import json,sys;print(len([p for p in json.load(sys.stdin) if p.get("PublishedPort") and p.get("URL") not in ("127.0.0.1",)]))')
  if [ "$n" -lt 1 ] || [ "$bad" -ne 0 ]; then echo "FAIL: $svc nicht ausschließlich an 127.0.0.1 veröffentlicht ($ports)"; return 1; fi
  echo "PASS: $svc veröffentlicht $n Port(s) ausschließlich an 127.0.0.1"
}

# Mock-LLM (OpenAI-kompatibel) als Container im Test-Netz, ausgeführt mit dem bereits gepinnten Paperless-Image (enthält python3).
mockllm_up() {
  local img
  img=$(docker compose config --images | grep paperless-ngx)
  docker rm -fv m03-ci-mockllm >/dev/null 2>&1 || true
  docker run -d --name m03-ci-mockllm --network m03-ci-net --network-alias mockllm -v "$REPO/tests/mockllm:/mock:ro" \
    --entrypoint python3 "$img" /mock/server.py 8000 >/dev/null
  for _ in $(seq 1 30); do
    docker exec m03-ci-mockllm python3 -c 'import urllib.request;urllib.request.urlopen("http://127.0.0.1:8000/_stats",timeout=2)' >/dev/null 2>&1 && return 0
    sleep 1
  done
  echo "FAIL: Mock-LLM startet nicht"; return 1
}
mockllm_mode() { docker exec m03-ci-mockllm python3 -c 'import sys,json,urllib.request;urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8000/_mode",data=json.dumps({"mode":sys.argv[1]}).encode(),method="POST"),timeout=5)' "$1"; }
mockllm_stats() { docker exec m03-ci-mockllm python3 -c 'import urllib.request;print(urllib.request.urlopen("http://127.0.0.1:8000/_stats",timeout=5).read().decode())'; }
mockllm_down() { docker rm -fv m03-ci-mockllm >/dev/null 2>&1 || true; }
