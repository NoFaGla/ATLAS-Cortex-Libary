#!/usr/bin/env bash
# Installiert eine feste rclone-Version mit gepinnter SHA-256 (CI/Testumgebungen). Nutzung: sudo bash tests/integration/install-rclone.sh
set -euo pipefail
VER=v1.75.2; SHA=349ac8fba6ff65d6247043f1750cdcb518ec5d500ef91463a10d37c0ccdf3702
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
curl -fsSL -o "$T/rclone.zip" "https://downloads.rclone.org/$VER/rclone-$VER-linux-amd64.zip"
echo "$SHA  $T/rclone.zip" | sha256sum -c - >/dev/null || { echo "FAIL: rclone-Prüfsumme stimmt nicht" >&2; exit 1; }
unzip -q "$T/rclone.zip" -d "$T"
install -m 0755 "$T"/rclone-*-linux-amd64/rclone /usr/local/bin/rclone
rclone version | head -1
