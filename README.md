# RK71 mod: open QMK firmware for the Royal Kludge RK71 RGB

Royal Kludge RK71 RGB: PCB `603-836/RGB-BT-HFD REV:01`, MCU SONiX SN32F248BF. This repository has two parts:

* **the original vendor firmware**, kept untouched, so the keyboard can always go back to stock
* **a QMK port** (`keyboard/rk71_rgb`). Its pins come from disassembling the stock firmware, not from guesswork. It
  works with VIA, and it supports per-key RGB.

## Branches and versions

| Branch | What it is |
|---|---|
| `stock` | Original Royal Kludge firmware V1.12, unmodified, plus research notes |
| `v0.1b` | First working QMK: all 71 keys, RGB matrix, VIA, Win/Mac modes, Fn layer |
| `main` | Latest |

Each version branch has its ready-to-flash image in `releases/`.

## Layout

```
stock/         vendor firmware image + official updater / PC software (do not modify)
keyboard/      QMK keyboard source: rk71_rgb (copied into qmk_firmware/ at build time)
via/           VIA definition: load it in usevia.app > Settings > Design tab
releases/      built firmware for each version
docs/          reverse-engineering notes (Bluetooth protocol)
tools/         build.sh, flash_rk71.sh, gen_rk71.py (generates keyboard.json + VIA json)
archive/       an earlier failed attempt, kept for history only
```

## Flashing

1. Put the keyboard in the SN32 ROM bootloader (USB `0C45:7040`). Use one of:
   * from QMK: **Fn + Pause**, or hold **Esc** while plugging in (with the BT switch off)
   * from stock firmware: `sonixflasher -v 05ac/024f -r hfd -f <bin>` reboots the keyboard into the bootloader and flashes in one go
   * last resort: short the left P1/P2 pad next to U4 (BOOT pin) to the USB shell while plugging in, and **keep it
     shorted for the whole flash**
2. `bash tools/flash_rk71.sh releases/<file>.bin`. It waits for the bootloader, then flashes and checks the checksum.

[SonixFlasher](https://github.com/SonixQMK/SonixFlasher/releases) is expected at `sonixflasher/sonixflasher.exe`.

## Building

```
git clone https://github.com/SonixQMK/qmk_firmware.git qmk_firmware
git -C qmk_firmware checkout c9f3803f && git -C qmk_firmware submodule update --init --recursive
bash tools/build.sh                # output: build/rk71_rgb_via.bin
```

Required tools (Windows): Arm GNU Toolchain 12.2 (`winget install Arm.ArmGnuToolchain`), the qmk CLI
(`uv tool install qmk`), and MSYS2 `make` 4.4 at `tools/make.exe`. The ezwinports make breaks QMK's quoting. Use
`qmk compile`, not `make kb:km`, because the `make` command line is too long for Windows.

## Known limitations

* QMK runs over USB only. The Bluetooth module is not driven yet (the protocol is decoded in `docs/BLUETOOTH.md`).
* VIA settings, keymaps and lighting are stored in flash. A new build can reset the keymap to its defaults.
