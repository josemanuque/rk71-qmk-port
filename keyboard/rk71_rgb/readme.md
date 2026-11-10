# Royal Kludge RK71 RGB (HFD PCB 603-836/RGB-BT-HFD, SN32F248BF)

A 71-key 70% board. USB and Bluetooth (on-board ITON module, see docs/BLUETOOTH.md in the rk71_mod repo).

* Keyboard maintainer: josemanuque
* Hardware supported: RK71 RGB, PCB `603-836/RGB-BT-HFD REV:01`, MCU SN32F248BF (LQFP64)
* USB ID: `0C45:8071` (stock firmware is `05AC:024F`)

## How this port was made

The matrix and LED pins come from disassembling stock firmware V1.12, not from guesswork:

* Key rows (inputs): D11, D10, D9, D8, D7. Stock routine `0x4778` reads P3.11…P3.7.
* Key columns: A8–A15, B0–B7. Stock routine `0x4516` drives them; the counter wraps at 16.
* The key-ID table at `0x7842` holds standard HID usages, which gives the exact key position of every row/column.
* LED row pins: identical to `royal_kludge/rk68_rgb`.

## Build

    make royal_kludge/rk71_rgb:via

## Entering the bootloader

* **Fn + Pause** (QK_BOOT)
* **Bootmagic**: hold Esc while plugging in
* **Hardware**, which always works: with the battery unplugged, short the left of the two round pads
  labelled P1/P2 (left of the MCU, next to LED D56) to the USB shell. Then plug in USB and keep the
  short on for the WHOLE flash, because the ROM bootloader exits when BOOT goes high.

Flash with SonixFlasherC at offset 0:

    sonixflasher -v 0c45/7040 -f royal_kludge_rk71_rgb_via.bin

To go back to stock, flash `stock/rk71_fw_v1.12.bin` from the project repository the same way.
