#!/usr/bin/env bash
# Usage: bash tools/flash_rk71.sh <firmware.bin> [minutes]
# Waits for the SN32 ROM bootloader (USB VID 0C45) to appear, then flashes the given .bin at offset 0.
# Enter the bootloader with Fn+Pause (QMK build), Esc held at plug-in (QMK bootmagic), or the BOOT pad
# short (left P1/P2 pad to the USB shell, held for the WHOLE flash).
set -u
FW="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
MIN="${2:-15}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
end=$((SECONDS + MIN * 60))
echo "Firmware: $FW"
echo "Waiting up to $MIN min for the SN32 ROM bootloader (0C45:7040)..."
while [ $SECONDS -lt $end ]; do
  id=$(powershell -NoProfile -c "(Get-PnpDevice -PresentOnly | ? InstanceId -like 'USB\VID_0C45&PID_7040*' | select -First 1).InstanceId" 2>/dev/null | tr -d '\r')
  if [ -n "$id" ]; then
    pid=$(echo "$id" | sed -E 's/.*PID_([0-9A-Fa-f]{4}).*/\1/')
    echo "Bootloader found: $id"
    "$HERE/sonixflasher/sonixflasher.exe" -v "0c45/$pid" -f "$FW"
    exit $?
  fi
  sleep 1
done
echo "Timed out: bootloader never appeared."; exit 2
