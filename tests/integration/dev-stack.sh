#!/usr/bin/env bash
# Entwicklungshilfe: startet den isolierten Teststack und lässt ihn laufen (stack_down zum Aufräumen).
set -euo pipefail
# shellcheck source=tests/integration/lib-stack.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib-stack.sh"
# shellcheck source=/dev/null
case "${1:-}" in
  up) stack_up; printf 'PAPERLESS_URL=%s\nPAPERLESS_TOKEN=%s\nSTACK_WORK=%s\n' "$PAPERLESS_URL" "$PAPERLESS_TOKEN" "$STACK_WORK" > /tmp/m03-dev-stack.env ;;
  down) . /tmp/m03-dev-stack.env; WORK=$STACK_WORK; stack_down; rm -f /tmp/m03-dev-stack.env ;;
  *) echo "usage: $0 up|down" >&2; exit 2 ;;
esac
