#!/usr/bin/env bash
set -euo pipefail
[ "${EUID}" -eq 0 ] || { echo "Bitte mit sudo/root ausführen." >&2; exit 1; }
cd /opt/atlas-sandbox/module03/compose
# Pull-Fehler (z. B. Registry-Rate-Limit) sind nicht fatal, wenn die gepinnten Digests lokal vorhanden sind;
# fehlt ein Image, scheitert `up` anschließend mit klarer Meldung.
docker compose pull --ignore-pull-failures broker db webserver || echo "WARN: pull unvollständig, nutze lokale Images" >&2
docker compose up -d broker db webserver
for _ in $(seq 1 90); do
  if curl -fsS http://127.0.0.1:18000/api/ >/dev/null 2>&1; then echo "CORE=PASS"; docker compose ps; exit 0; fi
  sleep 2
done
echo "CORE=FAIL"; docker compose ps; docker compose logs --tail=200 webserver db broker; exit 1
