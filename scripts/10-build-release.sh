#!/usr/bin/env bash
# Reproduzierbares Release-ZIP aus getrackten Dateien (sortiert, fester Zeitstempel, feste Rechte).
# Aufruf: scripts/10-build-release.sh [ausgabeverzeichnis]   (kein Deployment, keine Secrets)
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
OUT=${1:-"$ROOT/dist"}
cd "$ROOT"
VERSION=$(python3 -c 'import tomllib;print(tomllib.load(open("pyproject.toml","rb"))["project"]["version"])')
COMMIT=$(git rev-parse HEAD)
EPOCH=$(git log -1 --format=%ct)
mkdir -p "$OUT"
ZIP="$OUT/M03-CORTEX-LIBRARY-$VERSION.zip"
python3 - "$ZIP" "$EPOCH" "$VERSION" "$COMMIT" <<'PY'
import hashlib, subprocess, sys, time, zipfile
zip_path, epoch, version, commit = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
files = sorted(subprocess.run(["git", "ls-files", "-z"], capture_output=True, check=True).stdout.decode().split("\0"))
files = [f for f in files if f and not f.startswith("dist/")]
dt = time.gmtime(max(epoch, 315532800))[:6]
manifest = [f"version={version}", f"commit={commit}"]
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for f in files:
        data = open(f, "rb").read()
        manifest.append(f"{hashlib.sha256(data).hexdigest()}  {f}")
        mode = 0o755 if f.endswith(".sh") else 0o644
        zi = zipfile.ZipInfo(f, dt); zi.external_attr = (0o100000 | mode) << 16; zi.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(zi, data)
    zi = zipfile.ZipInfo("RELEASE_MANIFEST.txt", dt); zi.external_attr = (0o100000 | 0o644) << 16
    z.writestr(zi, "\n".join(manifest) + "\n")
PY
( cd "$OUT" && sha256sum "$(basename "$ZIP")" > "$(basename "$ZIP").sha256" )
cat "$ZIP.sha256"
