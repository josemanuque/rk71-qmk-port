# Stock Royal Kludge firmware (original, unmodified)

These are the vendor files, kept exactly as downloaded, so the keyboard can always go back to factory firmware.
How the firmware and the updater work inside, and the stock key map, are in [FIRMWARE_NOTES.md](FIRMWARE_NOTES.md).

| File | What it is |
|---|---|
| `rk71_fw_v1.12.bin` | Raw 64 KB flash image of stock firmware V1.12 (USB ID `05AC:024F`, bcdDevice 1.12). Flash at offset 0. |
| `RK71 RGB Firmware_V1.12_190603.exe` ¹ | Royal Kludge's official updater (Sonix "HFD ISP Tool", built 2019-06-24). Windows only. Contains the same firmware. |
| `RK71 RGB Keyboard PC Software V1.00n.exe` ¹ | Royal Kludge's Windows configuration software (lighting, macros). Only works with stock firmware. |
| `updater_contents/SN32F240B_32.hex` | The firmware exactly as embedded in the updater (extracted from its resource 4011, a zip). |
| `updater_contents/UISettings.ini` | The updater's config from the same zip: which USB IDs it accepts and the ISP command it sends. UTF-16. |

¹ Not in git (too large). Download them from the [stock-v1.12 release](../../../releases/tag/stock-v1.12). They're
hard to find elsewhere for this variant. Check your copy against these SHA-256 hashes:

```
a28e2624ef79d484ace399cccd8b2854062c78b734e50813df3c020fd1e985ac  rk71_fw_v1.12.bin
1c27b4bd7c037914fec4d8282bd48aa847fe22a9f06b7cbcfe10e186ee24a9f6  RK71 RGB Firmware_V1.12_190603.exe
d636568ff59b5afb9dc10da25bb982a9a0802691687c0ee10fe6e22fc8d02ae9  RK71 RGB Keyboard PC Software V1.00n.exe
```

**The `.bin` is verified original:** every byte the updater's `.hex` defines is identical to `rk71_fw_v1.12.bin`.
The only difference is that the hex leaves `0xEE9C`–`0xFFFB` undefined, and the `.bin` has zeros there. The last
word (`0xFFFC` = `55 55 AA AA`, the chip's code-option word) is in both.

## Going back to stock

1. Get the keyboard into the SN32 ROM bootloader (USB `0C45:7040`, it shows up as a HID device with no keys working).
   Pick whichever applies:

   | The keyboard is running… | Do this |
   |---|---|
   | our QMK (`0C45:8071`) | **Fn + Pause**, or hold **Esc** while plugging in the cable |
   | stock firmware (`05AC:024F`) | `python3 tools/stock_enter_isp.py` (Linux/macOS: `pip install hidapi`), or the vendor updater's Start button (Windows), or `sonixflasher -v 05ac/024f -r hfd` |
   | nothing / unknown / dead | the BOOT pad short below. It always works. |

2. Flash: `bash tools/flash_rk71.sh stock/rk71_fw_v1.12.bin`. It waits for `0C45:7040`, writes the whole 64 KB,
   and checks the checksum. The keyboard restarts as `05AC:024F`.

The vendor updater itself can also do the whole job, but **only from stock firmware**: it looks for `05AC:024F`,
`05AC:0256` or `0C45:8006` and does not recognise QMK's `0C45:8071`.

Flashing the full image also erases the QMK settings area, so VIA keymaps and lighting go back to defaults the next
time QMK is flashed.

## If it is bricked (no keys, no lights, Fn+Pause does nothing)

The SN32F248BF's bootloader is in ROM and can't be overwritten, so a bad flash can always be undone. You only
need to hold the chip's BOOT pin low while it powers up.

1. **Cut battery power**: slide the switch off, or to be sure, unplug the battery connector from the PCB.
   Otherwise the chip never powers down and does not see the BOOT pin at start-up.
2. Find the two small round pads labelled **P1 / P2** just left of the MCU (U4, the 64-pin chip), next to LED D56.
   * left pad = MCU pin 3 (BOOT, P2.2)
   * right pad = GND
3. Short the left pad to ground: tweezers or a wire across P1–P2, or from the left pad to the metal USB shell.
4. **While holding the short**, plug in the USB cable. A new USB device `0C45:7040` should appear. Check with
   `sonixflasher -c`, or `lsusb` (Linux), `system_profiler SPUSBDataType` (macOS), or Device Manager (Windows).
5. **Keep holding the short for the whole flash** (about a minute). The ROM bootloader quits as soon as BOOT is
   released, and the flash then fails partway. Run `bash tools/flash_rk71.sh stock/rk71_fw_v1.12.bin` (or a QMK
   image from the Releases page).
6. Release, unplug, reconnect the battery, plug in again.

This was used on 2026-11-06 to recover from the earlier broken port (see `archive/`).

Never drive pin P2.2 (BOOT) from custom firmware. The QMK port doesn't use it.
