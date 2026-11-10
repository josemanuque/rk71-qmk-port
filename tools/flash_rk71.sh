#!/usr/bin/env bash
# Flash a firmware image onto the RK71 (Windows Git Bash / MSYS2, Linux, macOS).
#
#   bash tools/flash_rk71.sh <firmware.bin> [minutes]
#
# Waits for the SN32 ROM bootloader (USB 0C45:7040), then writes the image at offset 0 with
# SonixFlasher. Start this first, then put the keyboard in the bootloader:
#   Fn+Pause (this QMK firmware) / python3 tools/stock_enter_isp.py (stock firmware) /
#   BOOT-pad short (anything; see stock/README.md).
#
# SonixFlasher is looked up as sonixflasher/sonixflasher[.exe] in this repo, then on PATH.
# Linux: install tools/udev/50-rk71.rules first, or run with sudo.
set -u
[ $# -ge 1 ] || { sed -n '2,13p' "$0"; exit 1; }
[ -f "$1" ] || { echo "No such file: $1"; exit 1; }
FW="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
MIN="${2:-15}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"

FLASHER=""
for c in "$HERE/sonixflasher/sonixflasher.exe" "$HERE/sonixflasher/sonixflasher"; do
  [ -x "$c" ] && { FLASHER="$c"; break; }
done
[ -n "$FLASHER" ] || FLASHER="$(command -v sonixflasher || command -v sonixflasher.exe || true)"
[ -n "$FLASHER" ] || {
  echo "SonixFlasher not found. Get it from https://github.com/SonixQMK/SonixFlasherC/releases"
  echo "and put it in sonixflasher/ (or on your PATH)."
  exit 1
}

bootloader_present() {
  "$FLASHER" -c 2>/dev/null | grep -qi '7040' && return 0
  case "$(uname -s)" in
    MINGW* | MSYS* | CYGWIN*) # Windows: also ask PnP directly
      powershell -NoProfile -c "if (Get-PnpDevice -PresentOnly | ? InstanceId -like 'USB\VID_0C45&PID_7040*') { 'yes' }" 2>/dev/null | grep -q yes ;;
    Linux)
      for d in /sys/bus/usb/devices/*; do
        [ "$(cat "$d/idVendor" 2>/dev/null)" = 0c45 ] && [ "$(cat "$d/idProduct" 2>/dev/null)" = 7040 ] && return 0
      done
      return 1 ;;
    *) return 1 ;;
  esac
}

end=$((SECONDS + MIN * 60))
echo "Firmware: $FW"
echo "Waiting up to $MIN min for the SN32 ROM bootloader (0C45:7040)..."
while [ $SECONDS -lt $end ]; do
  if bootloader_present; then
    echo "Bootloader found."
    "$FLASHER" -v 0c45/7040 -f "$FW"
    exit $?
  fi
  sleep 1
done
echo "Timed out: bootloader never appeared."
exit 2
