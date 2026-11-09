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
| `v0.2b` | F-row lock: Fn+Ctrl turns 1…= into F1…F12 (remembered, Fn key glows orange); with the lock on, Fn+F-keys = media |
| `v0.3b` | Solid white lighting by default |
| `v0.4b` | Bluetooth: Fn+Q/W/E/R/T device 1–5 (hold 3 s to pair), Fn+P wired/BT (hold 3 s to pair), Fn+Bksp hold to forget all |
| `v0.4.1b` | Fix: keys skipped when typing fast on Bluetooth (reports are now queued, not dropped) |
| `v0.4.2b` | Fix attempt 2 for skipped keys on Bluetooth: whole packet preloaded into the SPI FIFO, top-priority SPI interrupt |
| `v0.4.3b` | Stronger switch debounce (10 ms, per key) against double letters |
| `v0.4.4b` | Quieter status lights (only after Fn+Q–T/Fn+P, none on automatic reconnect), Caps Lock shown red |
| `v0.4.5b` | Caps Lock: stock cool white, or a dark key when the lighting is white |
| `v0.4.6b` | No Caps Lock blink when switching to Bluetooth (fresh lock state, 200 ms stability filter) |
| `v0.5b` | Side lights (follow keyboard / fixed / off, set in VIA) with status: pairing, mode, battery bar on Fn+Space; automatic wired/Bluetooth from cable detection |
| `v0.5.1b` | Side lights show mixed colours (white etc.) by cycling red/green/blue quickly |
| `v0.5.2b` | Side lights: 3x faster colour cycling (less visible colour split), blue toned down for the bluish diffuser |
| `v0.5.3b` | Side-light white balance in VIA (Neutral / Warm / Warmer / Warmest), default Warm |
| `v0.5.4b` | Side lights: Red/Green/Blue balance and Brightness sliders in VIA (0–31); follow keyboard brightness |
| `main` | Latest (= v0.5.4b) |

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

* Bluetooth (v0.4b+): no deep sleep yet. Lighting turns off after 5 minutes idle, but the chip stays awake, so turn the
  slide switch off when you are not using the keyboard on battery.
* VIA settings, keymaps and lighting are stored in flash. A new build can reset the keymap to its defaults.
