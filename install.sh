#!/usr/bin/env bash
# ATLAS M03 Cortex-Library — Installer (Sandbox-Pfade). Kein Deployment ohne ausdrücklichen Aufruf durch den Betreiber.
#
#   ./install.sh preflight                    Voraussetzungen + Release-Integrität prüfen (ändert nichts)
#   sudo ./install.sh install [--with-services] [--gpt]
#                                             Bootstrap, Core starten, Token, Taxonomie, optional Dienste/GPT
#   sudo ./install.sh service-accounts        Least-Privilege-Konten/Tokens für library-read/-ingest erzeugen (ohne systemd)
#   sudo ./install.sh validate                Gesundheit, Sicherheit (Isolation/Ports/Secrets), Registry, Taxonomie
#   sudo ./install.sh upgrade [--max-backup-age-h 24]
#                                             nur mit frischem, verifiziertem Backup; ändert nur, was nötig ist; validiert danach
#   sudo ./install.sh recover <backup-dir/current> --i-understand-this-replaces-the-sandbox
#                                             Restore aus (lokalem oder per 13-cloud-restore.sh geholtem) Backup + Validierung
#
# Sicherheit: nie destruktiv ohne Bestätigungsschalter, niemals auf Pfaden außerhalb /opt|/srv|/var/lib/atlas-sandbox und
# /etc/atlas/secrets/module03-sandbox. Secrets werden erzeugt (0600), nie ausgegeben.
set -euo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
OPT=/opt/atlas-sandbox/module03; SRV=/srv/atlas-sandbox/module03; VAR=/var/lib/atlas-sandbox/module03; SEC=/etc/atlas/secrets/module03-sandbox
say(){ printf '%s\n' "$*"; }
die(){ printf 'FEHLER: %s\n' "$*" >&2; exit 1; }
need_root(){ [ "${EUID}" -eq 0 ] || die "bitte mit sudo/root ausführen"; }
VERSION=$(python3 -c 'import tomllib;print(tomllib.load(open("'"$HERE"'/pyproject.toml","rb"))["project"]["version"])' 2>/dev/null || echo unknown)

verify_release_manifest(){
  # Im Release-ZIP liegt RELEASE_MANIFEST.txt (Zeilen "<sha256>  <pfad>"). Im Git-Checkout fehlt sie: dann Hinweis, kein Fehler.
  if [ -f "$HERE/RELEASE_MANIFEST.txt" ]; then
    local bad=0 sum path
    while read -r sum path; do
      [[ "$sum" =~ ^[0-9a-f]{64}$ ]] || continue
      [ -f "$HERE/$path" ] && [ "$(sha256sum "$HERE/$path" | cut -d' ' -f1)" = "$sum" ] || { say "FAIL: Manifest-Abweichung: $path"; bad=1; }
    done < "$HERE/RELEASE_MANIFEST.txt"
    [ "$bad" -eq 0 ] || die "Release-Integrität verletzt (Dateien verändert/fehlen)"
    say "PASS: Release-Manifest verifiziert ($(grep -c '^[0-9a-f]\{64\}  ' "$HERE/RELEASE_MANIFEST.txt") Dateien)"
  else
    say "INFO: kein RELEASE_MANIFEST.txt (Git-Checkout) — Integritätsprüfung übersprungen"
  fi
}

cmd_preflight(){
  say "== ATLAS M03 $VERSION preflight"
  verify_release_manifest
  command -v python3 >/dev/null && python3 -c 'import sys;sys.exit(0 if sys.version_info>=(3,11) else 1)' && say "PASS: python3 >= 3.11" || die "python3 >= 3.11 erforderlich"
  grep -q '@sha256:' "$HERE/compose/docker-compose.yml" && ! grep -qE 'image:.*:latest' "$HERE/compose/docker-compose.yml" && say "PASS: Images per Digest gepinnt, kein latest" || die "Compose nicht gepinnt"
  [ ! -e /srv/cortex ] || say "INFO: /srv/cortex existiert (wird nie angefasst)"
  bash "$HERE/scripts/00-preflight.sh"
  if [ -e "$OPT" ]; then say "INFO: Installation vorhanden ($OPT) — 'install' verweigert, 'upgrade' verwenden"; fi
}

cmd_install(){
  need_root
  local with_services=0 gpt=0
  while [ $# -gt 0 ]; do case "$1" in --with-services) with_services=1 ;; --gpt) gpt=1 ;; *) die "unbekannte Option $1" ;; esac; shift; done
  [ ! -e "$OPT" ] && [ ! -e "$SEC" ] || die "bereits installiert ($OPT / $SEC) — upgrade/recover verwenden; nichts wurde verändert"
  cmd_preflight
  bash "$HERE/scripts/01-bootstrap.sh" | tail -1
  bash "$OPT/scripts/02-up-core.sh" | grep -E "CORE="
  bash "$OPT/scripts/03-create-api-token.sh"
  install -d -m 0755 "$VAR/registry" "$VAR/registry/state"
  local tok; tok=$(grep '^PAPERLESS_API_TOKEN=' "$SEC/paperless-gpt.env" | cut -d= -f2-)
  ATLAS_PAPERLESS_URL=http://127.0.0.1:18000 ATLAS_PAPERLESS_ADMIN_TOKEN="$tok" PYTHONPATH="$OPT/src" \
    python3 -m atlas_library.cli --registry "$VAR/registry/registry.sqlite3" taxonomy | python3 -c 'import json,sys;d=json.load(sys.stdin);print("TAXONOMY=PASS created=%d existing=%d"%(d["created"],d["existing"]))'
  [ "$with_services" -eq 0 ] || install_services "$gpt"
  printf 'version=%s\ninstalled_utc=%s\ncommit=%s\n' "$VERSION" "$(date -u +%FT%TZ)" "$(grep '^commit=' "$HERE/RELEASE_MANIFEST.txt" 2>/dev/null | cut -d= -f2 || true)" > "$OPT/INSTALLED"
  say "INSTALL=PASS (version $VERSION). Nächster Schritt: ./install.sh validate; Paperless-GPT erst nach Core-Abnahme (scripts/05-up-ai.sh)."
}

service_accounts(){
  # Dienst-Tokens und Paperless-Dienstkonten (Least Privilege) erzeugen, falls nicht vorhanden
  python3 - "$SEC" "$(grep '^PAPERLESS_API_TOKEN=' "$SEC/paperless-gpt.env" | cut -d= -f2-)" <<'PY'
import json, os, secrets, sys, urllib.request
sec, admin = sys.argv[1], sys.argv[2]
base = "http://127.0.0.1:18000"
def api(method, path, body=None, token=admin, auth=True):
    req = urllib.request.Request(base + path, data=json.dumps(body).encode() if body is not None else None, method=method,
        headers={"Accept": "application/json; version=10", "Content-Type": "application/json", **({"Authorization": "Token " + token} if auth else {})})
    return json.loads(urllib.request.urlopen(req, timeout=30).read() or b"null")
def put(name, value):
    p = os.path.join(sec, name)
    if not os.path.exists(p):
        fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600); os.write(fd, (value + "\n").encode()); os.close(fd)
view = ["view_document", "view_tag", "view_correspondent", "view_documenttype", "view_customfield", "view_storagepath"]
for user, perms in (("library-read", view), ("library-ingest", view + ["change_document", "add_document"])):
    if os.path.exists(os.path.join(sec, f"{user}-paperless-token")):
        continue
    pw = secrets.token_urlsafe(32)
    api("POST", "/api/users/", {"username": user, "password": pw, "user_permissions": perms})
    tok = api("POST", "/api/token/", {"username": user, "password": pw}, auth=False)["token"]
    put(f"{user}-paperless-token", tok)
put("library-read-token", secrets.token_urlsafe(32)); put("library-ingest-token", secrets.token_urlsafe(32))
print("SERVICE_ACCOUNTS=PASS (Tokens in " + sec + ", nie ausgegeben)")
PY
}

install_services(){
  local gpt=$1 uid gid user group
  uid=$(stat -c %u "$SRV/consume"); gid=$(stat -c %g "$SRV/consume")
  user=$(getent passwd "$uid" | cut -d: -f1 || true); group=$(getent group "$gid" | cut -d: -f1 || true)
  [ -n "$user" ] && [ -n "$group" ] || die "kein Benutzer/keine Gruppe für UID/GID $uid/$gid (Consume-Besitzer) — Dienste nicht installiert"
  service_accounts
  for u in atlas-library-read atlas-library-ingest; do
    sed -e "s#@SERVICE_USER@#$user#g;s#@SERVICE_GROUP@#$group#g;s#@OPT@#$OPT#g;s#@VAR@#$VAR#g;s#@SRV@#$SRV#g;s#@SEC@#$SEC#g;s#@GPT_ENABLED@#$gpt#g" \
      "$HERE/deploy/systemd/$u.service.template" > "/etc/systemd/system/$u.service"
  done
  chown -R "$uid:$gid" "$VAR/registry"
  systemctl daemon-reload
  systemctl enable --now atlas-library-read atlas-library-ingest
  say "SERVICES=PASS (atlas-library-read :18090, atlas-library-ingest :18091, nur Loopback)"
}

cmd_validate(){
  need_root
  local rc=0
  say "== validate"
  curl -fsS http://127.0.0.1:18000/api/ >/dev/null && say "PASS: Paperless-API erreichbar" || { say "FAIL: Paperless-API"; rc=1; }
  bash "$HERE/scripts/14-security-check.sh" --project m03-sandbox --secrets "$SEC" || rc=1
  [ -f "$VAR/registry/registry.sqlite3" ] && PYTHONPATH="$HERE/src" python3 -m atlas_library.cli --registry "$VAR/registry/registry.sqlite3" registry-check || { say "FAIL: Registry"; rc=1; }
  local tok n; tok=$(grep '^PAPERLESS_API_TOKEN=' "$SEC/paperless-gpt.env" | cut -d= -f2-)
  n=$(curl -fsS "http://127.0.0.1:18000/api/document_types/?page_size=100" -H "Authorization: Token $tok" | python3 -c 'import json,sys;print(json.load(sys.stdin)["count"])' 2>/dev/null || echo 0)
  [ "$n" -ge 9 ] && say "PASS: Taxonomie vorhanden ($n Dokumenttypen)" || { say "FAIL: Taxonomie unvollständig"; rc=1; }
  if systemctl list-unit-files 2>/dev/null | grep -q '^atlas-library-read'; then
    for u in atlas-library-read atlas-library-ingest; do systemctl is-active --quiet "$u" && say "PASS: $u aktiv" || { say "FAIL: $u nicht aktiv"; rc=1; }; done
  else
    say "INFO: keine Dienste installiert (--with-services)"
  fi
  [ "$rc" -eq 0 ] && say "VALIDATE=PASS" || say "VALIDATE=FAIL"
  return $rc
}

cmd_upgrade(){
  need_root
  local max_h=24
  while [ $# -gt 0 ]; do case "$1" in --max-backup-age-h) max_h=$2; shift ;; *) die "unbekannte Option $1" ;; esac; shift; done
  [ -d "$OPT" ] || die "keine Installation gefunden — erst install"
  [ "$(cd "$HERE" && pwd -P)" != "$(cd "$OPT" && pwd -P)" ] || die "upgrade muss aus dem NEUEN Release-Verzeichnis gestartet werden, nicht aus der installierten Kopie"
  verify_release_manifest
  local latest; latest=$(readlink -f "$SRV/backup-staging/latest" 2>/dev/null || true)
  [ -n "$latest" ] && [ -f "$latest/SHA256SUMS" ] || die "kein Backup vorhanden: erst scripts/06-backup-sandbox.sh --upload ausführen (nichts wurde verändert)"
  (cd "$latest" && sha256sum --quiet -c SHA256SUMS) || die "Backup-Prüfsummen fehlerhaft (nichts wurde verändert)"
  local age_h=$(( ( $(date +%s) - $(stat -c %Y "$latest/SHA256SUMS") ) / 3600 ))
  [ "$age_h" -le "$max_h" ] || die "letztes Backup ist ${age_h}h alt (> ${max_h}h) — frisches Backup erstellen (nichts wurde verändert)"
  say "PASS: Backup ${age_h}h alt, Prüfsummen ok"
  # Paketdateien aktualisieren (Konfigurationen/Secrets/Daten bleiben): nur Code, Skripte, Compose-Datei, Vorlagen
  for d in src scripts deploy docs tests; do   # erst kopieren, dann austauschen: bei Fehler bleibt die alte Version unversehrt
    rm -rf "${OPT:?}/$d.new"; cp -a "$HERE/$d" "$OPT/$d.new"; rm -rf "${OPT:?}/$d"; mv "$OPT/$d.new" "$OPT/$d"
  done
  cp "$HERE/compose/docker-compose.yml" "$OPT/compose/docker-compose.yml"; cp "$HERE/install.sh" "$OPT/install.sh"; cp "$HERE/pyproject.toml" "$OPT/pyproject.toml"
  chmod +x "$OPT/scripts/"*.sh "$OPT/install.sh"
  (cd "$OPT/compose" && docker compose up -d broker db webserver)
  for _ in $(seq 1 90); do curl -fsS http://127.0.0.1:18000/api/ >/dev/null 2>&1 && break; sleep 2; done
  PYTHONPATH="$OPT/src" python3 -m atlas_library.cli --registry "$VAR/registry/registry.sqlite3" registry-check >/dev/null   # öffnet = migriert vorwärts
  if systemctl list-unit-files 2>/dev/null | grep -q '^atlas-library-read'; then systemctl restart atlas-library-read atlas-library-ingest; fi
  printf 'version=%s\nupgraded_utc=%s\n' "$VERSION" "$(date -u +%FT%TZ)" >> "$OPT/INSTALLED"
  if cmd_validate; then say "UPGRADE=PASS"; else say "UPGRADE=FAIL — Wiederherstellung: ./install.sh recover $latest/current --i-understand-this-replaces-the-sandbox"; return 1; fi
}

cmd_recover(){
  need_root
  local b=${1:-} flag=${2:-}
  [ -d "$b/opt/module03" ] || die "Aufruf: recover <backup/current> --i-understand-this-replaces-the-sandbox"
  [ "$flag" = "--i-understand-this-replaces-the-sandbox" ] || die "Bestätigungsschalter fehlt — nichts wurde verändert"
  [ -f "$(dirname "$b")/SHA256SUMS" ] && (cd "$(dirname "$b")" && sha256sum --quiet -c SHA256SUMS) || die "Backup-Prüfsummen fehlen/fehlerhaft — nichts wurde verändert"
  bash "$b/opt/module03/scripts/08-restore-sandbox.sh" "$b" --i-understand-this-replaces-the-sandbox
  cmd_validate
}

case "${1:-}" in
  preflight) shift; cmd_preflight "$@" ;;
  install) shift; cmd_install "$@" ;;
  validate) shift; cmd_validate "$@" ;;
  service-accounts) need_root; service_accounts ;;
  upgrade) shift; cmd_upgrade "$@" ;;
  recover) shift; cmd_recover "$@" ;;
  *) sed -n '2,16p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 2 ;;
esac
