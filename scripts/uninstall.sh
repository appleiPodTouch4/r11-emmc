#!/bin/sh
# Remove R11EmmcTestDxe from an existing R11 UEFI build tree.
set -eu

ROOT=${1:-${UNIXNU_ROOT:-/Users/mry0000/Desktop/unixnu_r11}}
DEST="$ROOT/UniXNU/package/UniXNUPkg/Driver/R11EmmcTestDxe"
DSC="$ROOT/uefi-r11-base/Platforms/OPPO/r11Pkg/r11.dsc"
APRIORI="$ROOT/uefi-r11-base/Platforms/OPPO/r11Pkg/Include/APRIORI.inc"

rm -rf "$DEST"
python3 - "$DSC" "$APRIORI" <<'PY'
import sys
from pathlib import Path
for name in sys.argv[1:]:
    p = Path(name)
    if not p.exists():
        continue
    lines = [line for line in p.read_text().splitlines(True)
             if 'R11EmmcTestDxe/R11EmmcTestDxe.inf' not in line]
    p.write_text(''.join(lines))
print('removed R11EmmcTestDxe')
PY
