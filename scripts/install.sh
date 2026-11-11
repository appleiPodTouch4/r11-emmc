#!/bin/sh
# Copy R11EmmcTestDxe into an existing UniXNU R11 checkout and wire it into
# the UEFI build.  This is intentionally a XNU-free, UEFI-only test.
set -eu

ROOT=${1:-${UNIXNU_ROOT:-/Users/mry0000/Desktop/unixnu_r11}}
REPO=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

DEST="$ROOT/UniXNU/package/UniXNUPkg/Driver/R11EmmcTestDxe"
DSC="$ROOT/uefi-r11-base/Platforms/OPPO/r11Pkg/r11.dsc"
DXE="$ROOT/uefi-r11-base/Platforms/OPPO/r11Pkg/Include/DXE.inc"

[ -d "$ROOT/UniXNU/package/UniXNUPkg" ] || {
  echo "not a UniXNU checkout: $ROOT" >&2
  exit 1
}
[ -f "$DSC" ] || {
  echo "missing $DSC" >&2
  exit 1
}

mkdir -p "$DEST"
cp "$REPO/Driver/R11EmmcTestDxe.c" "$DEST/"
cp "$REPO/Driver/R11EmmcTestDxe.inf" "$DEST/"

python3 - "$DSC" "$DXE" <<'PY'
import sys
from pathlib import Path

dsc = Path(sys.argv[1])
dxe = Path(sys.argv[2])
dxe_line = "  INF UniXNUPkg/Driver/R11EmmcTestDxe/R11EmmcTestDxe.inf\n"
dsc_line = "  UniXNUPkg/Driver/R11EmmcTestDxe/R11EmmcTestDxe.inf\n"

s = dsc.read_text()
if "R11EmmcTestDxe/R11EmmcTestDxe.inf" not in s:
    s = s.replace("[Components]\n", "[Components]\n" + dsc_line, 1)
    dsc.write_text(s)

s = dxe.read_text()
if "R11EmmcTestDxe/R11EmmcTestDxe.inf" not in s:
    marker = "  INF EmbeddedPkg/MetronomeDxe/MetronomeDxe.inf\n"
    if marker in s:
        s = s.replace(marker, dxe_line + marker, 1)
    else:
        s = dxe_line + s
    dxe.write_text(s)
print("integrated R11EmmcTestDxe")
PY
