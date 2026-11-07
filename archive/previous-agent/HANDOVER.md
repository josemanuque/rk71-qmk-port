# RK71 QMK Flash — Handover

## Current State
- Keyboard IS running QMK (NOT bricked). Confirms as VID=0x05AC PID=0x024F, 3 HID interfaces.
- Keys don't work: LED driver (rk71_led_flush) fights matrix by toggling P3.4/5/6 which are SHARED with key matrix rows D4/D5/D6.
- OEM EXE can't connect: QMK HID descriptor is different (no vendor collection).
- Patched firmware ready: `qmk_firmware/.build/rk_rk71_noled.bin/.hex` — NOP'd LED driver, keys will work.

## How to Fix (Priority Order)

### Option 1 — Bootmagic (easiest, try first)
Bootmagic runs BEFORE the LED driver initializes, so the matrix is clean.

1. Run watcher: `cd rk71_mod && python bootmagic_test.py`
2. PHYSICALLY hold the **Esc key on the RK71** (not any other keyboard)
3. While holding: unplug the RK71 USB
4. Plug USB back in, keep holding Esc for 2 seconds
5. Release — if ISP detected, run: `python flash_qmk.py --hex "qmk_firmware\.build\rk_rk71_noled.hex"`

### Option 2 — sonixflasher reboot attempt
Sometimes works (how QMK got flashed in the first place):
```
cd rk71_mod\sonixflasher
sonixflasher.exe -v 05ac/024f -r hfd -f ..\qmk_firmware\.build\rk_rk71_noled.bin
```
Run bootmagic_test.py simultaneously to watch for ISP.

### Option 3 — Hardware short (last resort, keyboard fully accessible)
SN32F240B enters ISP if P0.0 (pin 1) is shorted to GND at power-up.
On the PCB: find RESET pad or ISP test point. Short to GND, apply power, ISP appears (VID_0C45/7040).
Then flash: `python flash_qmk.py --hex "qmk_firmware\.build\rk_rk71_noled.hex"`

## Key Files
| File | Purpose |
|------|---------|
| `qmk_firmware/.build/rk_rk71_default.hex` | Original QMK (broken LED/matrix) |
| `qmk_firmware/.build/rk_rk71_noled.bin` | **Patched QMK — LED NOP'd, keys will work** |
| `qmk_firmware/.build/rk_rk71_noled.hex` | Same in Intel HEX format |
| `qmk_firmware/.build/rk_rk71_default.elf` | ELF with full debug symbols |
| `qmk_firmware/.build/rk_rk71_default.map` | Symbol map (function addresses) |
| `flash_qmk.py` | ISP flashing script |
| `bootmagic_test.py` | Watches for VID_0C45/7040 via libusb |
| `intercept_final.ps1` | Kills OEM EXE + flashes noled.hex |
| `RK71 RGB Firmware_V1.12_190603.exe` | OEM flasher (needs OEM firmware on keyboard) |

## Technical Facts
- MCU: SN32F240B (SONiX ARM Cortex-M0, 64KB flash)
- USB VID/PID (normal): 0x05AC / 0x024F
- USB VID/PID (ISP):    0x0C45 / 0x7040
- ISP trigger: write 0xE5 to RAM[0x2000013A] then reset
- Key matrix: 7 rows × 16 cols, ROW2COL, confirmed row pins P3.3-P3.6, confirmed col inputs P3.0-P3.2 / P3.7-P3.15 / P0.1 / P0.2 / P0.15 / P2.15
- LED conflict: rk71_led_flush toggles P3.4/5/6 which are ALSO key matrix rows 1-3
- noled.bin patch: offset 0x0618 and 0x1A78 → 0x70 0x47 (BX LR)
- Bootmagic key: Esc (matrix[0][0] = row D3/P3.3, col D0/P3.0) — CONFIRMED pins
- QK_BOOT shortcut: Fn+F12 (needs working matrix)
- After noled flash: keys work, LEDs off. Use `python bootmagic_test.py` for future reflash via bootmagic.

## Why OEM EXE No Longer Works
OEM EXE searches for a vendor HID collection (usage page 0xFFFF) that OEM firmware exposes but QMK does not. Switching back to OEM firmware would require ISP mode first.

## OEM Firmware Backup
No backup of original OEM firmware was taken. If needed, it can be re-downloaded:
`RK71 RGB Firmware_V1.12_190603.exe` is the OEM flasher and contains the firmware payload internally.

## Recovery Without Physical Access (If Bootmagic Fails)
Not possible. The ISP bootloader requires a physical trigger (key combo at power-up or hardware short). Bootmagic at Esc/[0][0] is the most viable remote option. The SONiX ISP USB magic bytes (hfd/evision) have not reliably triggered ISP on this keyboard.
