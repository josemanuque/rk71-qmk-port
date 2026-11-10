#!/usr/bin/env bash
# Build the RK71 QMK firmware (Windows Git Bash / MSYS2, Linux, macOS).
#   bash tools/build.sh [keymap] [output.bin]      (keymap defaults to "via")
#
# The keyboard source lives in keyboard/rk71_rgb (this repo). It is copied into the
# SonixQMK checkout in ./qmk_firmware (not part of this repo; see README) and compiled there.
# Override the checkout location with QMK_DIR=/path/to/qmk_firmware.
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
KM="${1:-via}"
OUT="${2:-$HERE/build/rk71_rgb_${KM}.bin}"
QMK_DIR="${QMK_DIR:-$HERE/qmk_firmware}"
QMK_COMMIT=c9f3803f # SonixQMK commit this port is built and tested against

# Needed on PATH: arm-none-eabi-gcc (Arm GNU Toolchain 12.2 is what releases are built with),
# make, and the qmk CLI (pip / uv tool install qmk).
case "$(uname -s)" in
  MINGW* | MSYS* | CYGWIN*)
    # Windows defaults: winget Arm.ArmGnuToolchain, uv-installed qmk, MSYS2 make 4.4 in tools/
    # (the ezwinports make mangles QMK's quoting).
    export PATH="$HERE/tools:/c/Program Files (x86)/Arm GNU Toolchain arm-none-eabi/12.2 mpacbti-rel1/bin:$HOME/.local/bin:$PATH"
    ;;
esac
command -v arm-none-eabi-gcc > /dev/null || { echo "arm-none-eabi-gcc not found on PATH"; exit 1; }
command -v qmk > /dev/null || { echo "qmk CLI not found (pip install qmk)"; exit 1; }

[ -d "$QMK_DIR/.git" ] || { echo "Missing $QMK_DIR. See README: clone SonixQMK there."; exit 1; }
have=$(git -C "$QMK_DIR" rev-parse --short=8 HEAD)
[ "$have" = "$QMK_COMMIT" ] || echo "warning: qmk_firmware is at $have, this port was tested on $QMK_COMMIT"

dst="$QMK_DIR/keyboards/royal_kludge/rk71_rgb"
rm -rf "$dst"
cp -r "$HERE/keyboard/rk71_rgb" "$dst"

(cd "$QMK_DIR" && qmk compile -kb royal_kludge/rk71_rgb -km "$KM")
mkdir -p "$(dirname "$OUT")"
cp "$QMK_DIR/royal_kludge_rk71_rgb_${KM}.bin" "$OUT"
echo "Built: $OUT"
