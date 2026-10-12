#!/usr/bin/env bash
# Führt alle verfügbaren Tests nacheinander aus und gibt eine PASS/FAIL/BLOCKED-Übersicht aus (Exit 1 bei FAIL).
# Aufruf als root (Container-Tests brauchen root); destruktiver Restore-Test nur mit M03_ISOLATED_TEST_ENV=1 (siehe Skript).
set -uo pipefail
REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd); cd "$REPO" || exit 1
LOGDIR=${LOGDIR:-/tmp/m03-test-logs}; mkdir -p "$LOGDIR"
declare -a NAMES RESULTS
run() { # name command...
  local name=$1; shift
  echo "=== $name"; "$@" > "$LOGDIR/$name.log" 2>&1; local rc=$?
  case $rc in 0) r=PASS ;; 77) r=BLOCKED ;; *) r=FAIL ;; esac
  NAMES+=("$name"); RESULTS+=("$r"); echo "    -> $r (Log: $LOGDIR/$name.log)"
}
run shellcheck bash -c 'shellcheck -x -S style install.sh scripts/*.sh tests/*.sh tests/integration/*.sh'
run unit python3 -m pytest -q tests/unit
run bandit bandit -q -r src -ll
run rclone-crypt bash tests/integration/rclone-crypt.sh
run core-smoke bash tests/integration/core-smoke.sh
run e2e bash tests/integration/run-e2e.sh
run gpt-smoke bash tests/integration/gpt-smoke.sh
run gpt-mock bash tests/integration/run-gpt-mock.sh
if [ "${M03_ISOLATED_TEST_ENV:-}" = 1 ]; then run restore-e2e bash tests/integration/restore-e2e.sh; else NAMES+=(restore-e2e); RESULTS+=(NOT-RUN); fi
run gpt-real-llm bash tests/integration/gpt-real-llm.sh
echo; echo "== Zusammenfassung"; fail=0
for i in "${!NAMES[@]}"; do printf '%-14s %s\n' "${NAMES[$i]}" "${RESULTS[$i]}"; [ "${RESULTS[$i]}" = FAIL ] && fail=1; done
exit $fail
