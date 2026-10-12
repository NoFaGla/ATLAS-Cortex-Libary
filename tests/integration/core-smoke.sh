#!/usr/bin/env bash
# Isolierter Core-Smoke-Test (Paperless-ngx + PostgreSQL + Valkey) mit ausschließlich synthetischen Daten.
# Nutzt eigene Projekt-/Volume-/Netzwerknamen (m03-ci-*), Port 127.0.0.1:28000 und ein Temp-Verzeichnis;
# berührt weder /srv/atlas-sandbox noch /etc/atlas noch produktive Pfade. Exit 77 = BLOCKED (kein Docker).
# shellcheck disable=SC2015  # A && pass || fail ist hier bewusst (fail beendet das Skript)
set -euo pipefail
REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
PORT=28000
if ! docker info >/dev/null 2>&1; then echo "RESULT=BLOCKED (Docker-Daemon nicht erreichbar)"; exit 77; fi
if docker volume ls -q | grep -q '^m03-ci-'; then echo "STOP: m03-ci-* Volumes existieren bereits" >&2; exit 1; fi
WORK=$(mktemp -d); chmod 700 "$WORK"
export COMPOSE_PROJECT_NAME=m03-ci
cleanup(){ rc=$?; (cd "$WORK/compose" 2>/dev/null && docker compose down -v --remove-orphans >/dev/null 2>&1) || true; rm -rf "$WORK"; exit $rc; }
trap cleanup EXIT
mkdir -p "$WORK"/{compose,sec,srv/media,srv/consume,srv/export}
chown -R 1000:1000 "$WORK/srv"
sed -e "s#/etc/atlas/secrets/module03-sandbox#$WORK/sec#g" -e "s#/srv/atlas-sandbox/module03#$WORK/srv#g" \
    -e "s#m03-sandbox#m03-ci#g" -e "s#127.0.0.1:18000:8000#127.0.0.1:$PORT:8000#" \
    "$REPO/compose/docker-compose.yml" > "$WORK/compose/docker-compose.yml"
cp "$REPO/compose/paperless.env.example" "$WORK/compose/paperless.env"
cp "$REPO/compose/.env.example" "$WORK/compose/.env"
for f in postgres_password paperless_secret_key paperless_admin_password; do python3 -c 'import secrets;print(secrets.token_urlsafe(32))' > "$WORK/sec/$f"; done
cd "$WORK/compose"
pass(){ echo "PASS: $*"; }; fail(){ echo "FAIL: $*"; docker compose logs --tail=80 webserver || true; exit 1; }
docker compose up -d broker db webserver
for _ in $(seq 1 120); do curl -fsS "http://127.0.0.1:$PORT/api/" >/dev/null 2>&1 && break; sleep 3; done
curl -fsS "http://127.0.0.1:$PORT/api/" >/dev/null || fail "Paperless API nicht erreichbar"
pass "API erreichbar"
[ "$(docker compose ps db --format '{{.Health}}')" = healthy ] && pass "PostgreSQL healthy" || fail "PostgreSQL nicht healthy"
[ "$(docker compose exec -T broker valkey-cli ping | tr -d '\r')" = PONG ] && pass "Valkey PONG" || fail "Valkey"
docker compose exec -T webserver python3 -c 'import django;print(1)' >/dev/null 2>&1 || true
VER=$(docker compose exec -T webserver sh -c 'cat /usr/src/paperless/src/paperless/version.py 2>/dev/null | grep -o "([0-9, ]*)" | head -1' || true)
echo "INFO: paperless version tuple: ${VER:-unbekannt}"
if ss -ltn | awk '{print $4}' | grep -E ":$PORT$" | grep -vq '^127.0.0.1:'; then fail "Port nicht nur auf Loopback"; fi
pass "Port nur an 127.0.0.1"
ADMIN=$(grep '^PAPERLESS_ADMIN_USER=' paperless.env | cut -d= -f2)
TOKEN=$(python3 - "$ADMIN" "$(cat "$WORK/sec/paperless_admin_password")" <<'PY' | curl -fsS -X POST "http://127.0.0.1:$PORT/api/token/" -H 'Content-Type: application/json' --data @- | python3 -c 'import json,sys;print(json.load(sys.stdin)["token"])'
import json,sys
print(json.dumps({"username":sys.argv[1],"password":sys.argv[2]}))
PY
)
[ -n "$TOKEN" ] && pass "Adminlogin/Token" || fail "Token"
python3 - "$WORK/doc.pdf" <<'PY'
import sys
text = "ATLASSYNTH Rechnung 2026-01 Synthetisches Testdokument Musterfirma GmbH"
stream = f"BT /F1 14 Tf 50 750 Td ({text}) Tj ET".encode()
objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream", b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
out = b"%PDF-1.4\n"; offs = []
for i, o in enumerate(objs, 1):
    offs.append(len(out)); out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
x = len(out); out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
for o in offs: out += b"%010d 00000 n \n" % o
out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, x)
open(sys.argv[1], "wb").write(out)
PY
SHA_BEFORE=$(sha256sum "$WORK/doc.pdf" | cut -d' ' -f1)
curl -fsS -X POST "http://127.0.0.1:$PORT/api/documents/post_document/" -H "Authorization: Token $TOKEN" -F "document=@$WORK/doc.pdf;filename=synthetisch.pdf" -F "title=Synthetisch" >/dev/null
DOC=""
for _ in $(seq 1 90); do
  DOC=$(curl -fsS "http://127.0.0.1:$PORT/api/documents/?query=ATLASSYNTH" -H "Authorization: Token $TOKEN" | python3 -c 'import json,sys;r=json.load(sys.stdin)["results"];print(r[0]["id"] if r else "")')
  [ -n "$DOC" ] && break; sleep 3
done
[ -n "$DOC" ] && pass "Upload + Konsumierung + OCR/Text-Index (Doc $DOC)" || fail "Dokument nicht konsumiert"
SHA_AFTER=$(curl -fsS "http://127.0.0.1:$PORT/api/documents/$DOC/download/?original=true" -H "Authorization: Token $TOKEN" | sha256sum | cut -d' ' -f1)
[ "$SHA_BEFORE" = "$SHA_AFTER" ] && pass "Original bit-identisch abrufbar" || fail "Original verändert"
docker compose restart >/dev/null
for _ in $(seq 1 120); do curl -fsS "http://127.0.0.1:$PORT/api/" >/dev/null 2>&1 && break; sleep 3; done
N=$(curl -fsS "http://127.0.0.1:$PORT/api/documents/" -H "Authorization: Token $TOKEN" | python3 -c 'import json,sys;print(json.load(sys.stdin)["count"])')
[ "$N" = 1 ] && pass "Neustart ohne Datenverlust" || fail "Dokumentanzahl nach Neustart: $N"
docker compose exec -T webserver document_sanity_checker && pass "document_sanity_checker" || fail "sanity checker"
echo "RESULT=PASS"
