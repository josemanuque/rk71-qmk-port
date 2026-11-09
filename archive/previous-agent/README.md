# Archive: earlier attempt (do not use)

Kept for history only. This is the work of an earlier session that left the keyboard with dead keys and LEDs.
Nothing here is needed to build, flash or recover the keyboard. The few correct findings now live in `stock/` and
`docs/`.

* `HANDOVER.md`, `ANALYSIS.md`: notes from that attempt.
* `broken-qmk-port/rk71_as_flashed`: the QMK port that was actually flashed. Its matrix and LED pins were guessed, so
  nothing worked. `rk71_qmk_port_copy` is a slightly different copy of the same port.
* `scripts/`: ISP-trigger, HID-intercept, and flashing experiments.

## What was right and what was wrong

| Claim | Verdict |
|---|---|
| MCU is SN32F240B-family, 64 KB flash, ROM ISP `0C45:7040` | Right (the exact part is SN32F248BF) |
| ISP command `AA 42 89 5A FF 71 62 CC` as a 64-byte feature report (`scripts/rk71_hid.py`) | Right. Confirmed in the updater config and the firmware; see `stock/FIRMWARE_NOTES.md`. The scripts couldn't send it because they opened the keyboard read/write. `tools/stock_enter_isp.py` does it properly. |
| ISP entered by writing `0xE5` to RAM `0x2000013A` and resetting | Wrong. The firmware jumps straight to ROM `0x1FFF0301`. |
| Boot pin is P0.0 (pin 1) | Wrong. BOOT is P2.2, pin 3, the left P1/P2 pad. |
| LEDs driven by an IS31FL3731-type chip | Wrong. The LEDs are driven directly from GPIO. |
| Bluetooth module on a UART | Wrong. It's an ITON module on SPI0 (`docs/BLUETOOTH.md`). |
| GPIO register offsets and several peripheral base addresses | Wrong (SN32F240B datasheet v2.4 gives different ones) |
| Matrix and LED pins in the QMK port | Guessed and wrong. The working pins came from the stock key-scan routines. |
| "No OEM firmware backup exists" | Wrong. The vendor updater contains the full image (`stock/`). |

The working port is `keyboard/rk71_rgb`. Its pins were decoded from the stock firmware.
