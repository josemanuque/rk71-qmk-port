# RK71 mod: open QMK firmware for the Royal Kludge RK71 RGB

Royal Kludge RK71 RGB: PCB `603-836/RGB-BT-HFD REV:01`, MCU SONiX SN32F248BF. This repository has two parts:

* **a QMK port** (`keyboard/rk71_rgb`). Its pins come from disassembling the stock firmware, not from guesswork. It
  works with VIA on Windows, macOS and Linux, and supports per-key RGB, Bluetooth and the side lights.
* **the original vendor firmware**, preserved together with notes on how it works, so the keyboard can always go
  back to stock

**Using the QMK firmware (keys, Bluetooth, lighting, side lights, VIA): [docs/QMK_FIRMWARE.md](docs/QMK_FIRMWARE.md).**

## Download

Ready-to-flash images are on the [**Releases**](../../releases) page:

* `rk71_rgb_<version>.bin`: the firmware (VIA keymap). This is the one you want.
* `rk71_rgb_<version>_default-keymap.bin`: the same, with the plain QMK keymap
* `rk71_rgb_via.json`: the VIA definition (see the [user guide](docs/QMK_FIRMWARE.md#configuring-with-via))

The [**stock-v1.12**](../../releases/tag/stock-v1.12) release mirrors Royal Kludge's original software for this
board variant, which has become hard to find: the V1.12 updater, the PC configuration app, and the raw firmware
image (also in [stock/](stock)).

Every push also builds the firmware on GitHub Actions. Open a run under **Actions** and download it from
**Artifacts** to try unreleased changes.

### Versions

| Version | Changes |
|---|---|
| `v0.5.5b` | No keyboard blinking while dragging VIA side-light sliders (saves once settled) |
| `v0.5.4b` | Side lights: Red/Green/Blue balance and Brightness sliders in VIA (0–31); follow keyboard brightness |
| `v0.5.3b` | Side-light white balance in VIA (Neutral / Warm / Warmer / Warmest), default Warm |
| `v0.5.2b` | Side lights: 3× faster colour cycling (less visible colour split), blue toned down for the bluish diffuser |
| `v0.5.1b` | Side lights show mixed colours (white etc.) by cycling red/green/blue quickly |
| `v0.5b` | Side lights (follow keyboard / fixed / off, set in VIA) with status: pairing, mode, battery bar on Fn+Space; automatic wired/Bluetooth from cable detection |
| `v0.4.6b` | No Caps Lock blink when switching to Bluetooth (fresh lock state, 200 ms stability filter) |
| `v0.4.5b` | Caps Lock: stock cool white, or a dark key when the lighting is white |
| `v0.4.4b` | Quieter status lights (only after Fn+Q–T/Fn+P, none on automatic reconnect), Caps Lock shown red |
| `v0.4.3b` | Stronger switch debounce (10 ms, per key) against double letters |
| `v0.4.2b` | Fixed keys skipped when typing fast on Bluetooth (whole packet preloaded into the SPI FIFO, top-priority SPI interrupt) |
| `v0.4.1b` | First attempt at the skipped keys on Bluetooth (reports queued instead of dropped) |
| `v0.4b` | Bluetooth: Fn+Q/W/E/R/T device 1–5 (hold 3 s to pair), Fn+P wired/BT (hold 3 s to pair), Fn+Bksp hold to forget all |
| `v0.3b` | Solid white lighting by default |
| `v0.2b` | F-row lock: Fn+Ctrl turns 1…= into F1…F12 (remembered, Fn key glows orange); with the lock on, Fn+F-keys = media |
| `v0.1b` | First working QMK: all 71 keys, RGB matrix, VIA, Win/Mac modes, Fn layer |
| `stock-v1.12` | Original Royal Kludge firmware V1.12, unmodified, plus research notes |

Each version is a git tag. Check one out with `git checkout v0.4b`.

## Flashing

Works from Windows (Git Bash), macOS and Linux.

1. Get [SonixFlasher](https://github.com/SonixQMK/SonixFlasherC/releases) for your OS. Put it in `sonixflasher/`
   in this repo, or anywhere on your PATH. On Linux, first allow access without root:
   `sudo cp tools/udev/50-rk71.rules /etc/udev/rules.d/ && sudo udevadm control --reload && sudo udevadm trigger`
2. Start the flasher: `bash tools/flash_rk71.sh rk71_rgb_<version>.bin`. It waits for the bootloader.
3. Put the keyboard in the SN32 ROM bootloader (USB `0C45:7040`), with the cable plugged in:
   * from this QMK firmware: **Fn + Pause**
   * from stock firmware: `python3 tools/stock_enter_isp.py`, which is what the vendor updater does. Linux/macOS
     need `pip install hidapi`.
   * if nothing works: short the BOOT pad while plugging in. Step by step:
     [stock/README.md](stock/README.md#if-it-is-bricked-no-keys-no-lights-fnpause-does-nothing)
4. The script flashes, verifies the checksum, and the keyboard restarts.

## Building

```
git clone https://github.com/SonixQMK/qmk_firmware.git qmk_firmware
git -C qmk_firmware checkout c9f3803f && git -C qmk_firmware submodule update --init --recursive
bash tools/build.sh                # output: build/rk71_rgb_via.bin
```

Needed on PATH: `arm-none-eabi-gcc` (Arm GNU Toolchain 12.2; releases are built with it), `make`, and the qmk CLI
(`pip install qmk` or `uv tool install qmk`).

* **Linux / macOS:** install the toolchain from [Arm](https://developer.arm.com/downloads/-/arm-gnu-toolchain-downloads)
  or your package manager. `.github/workflows/build.yml` shows a full Ubuntu setup.
* **Windows:** `winget install Arm.ArmGnuToolchain`, and MSYS2 `make` 4.4 copied to `tools/make.exe` (the
  ezwinports make breaks QMK's quoting). `build.sh` adds these to PATH by itself. Use `qmk compile` (as
  `build.sh` does), not `make kb:km`: the `make` command line is too long for Windows.

`keyboard.json` and `via/rk71_rgb_via.json` are generated by `tools/gen_rk71.py`. Edit the generator, not the
outputs.

## Development workflow

* `main` is always the latest working firmware.
* Work happens on short-lived branches (`feature/side-light-calibration`, `fix/caps-blink`, …). They're merged into
  `main` once tested on the keyboard, then deleted.
* A release is a tag on `main`. Pushing it makes GitHub Actions build the images and publish the release:

  ```
  git tag v0.5.6b && git push origin v0.5.6b
  ```

  Tags ending in `b` are marked as pre-releases.
* If an old release ever needs a fix, branch `release/0.5.x` from its tag only then.

## Layout

```
keyboard/      QMK keyboard source: rk71_rgb (copied into qmk_firmware/ at build time)
via/           VIA definition: load it in usevia.app > Settings > Design tab
docs/          QMK_FIRMWARE.md (user guide), BLUETOOTH.md (Bluetooth module protocol)
stock/         original firmware image, recovery guide, stock internals and key map
tools/         build.sh, flash_rk71.sh, stock_enter_isp.py, gen_rk71.py, udev rule for Linux
archive/       an earlier failed attempt, kept for history only
```

## Known limitations

* Bluetooth: no deep sleep yet. Lighting turns off after 5 minutes idle, but the chip stays awake, so turn the
  slide switch off when you are not using the keyboard on battery.
* VIA settings, keymaps and lighting are stored in flash. Flashing a new build resets them to defaults.

## License

The QMK port and tools are GPL-2.0-or-later ([LICENSE](LICENSE)), like QMK itself. Royal Kludge's firmware and
programs (in `stock/` and on the `stock-v1.12` release) are their property. They're mirrored only to preserve
them for owners of this keyboard and aren't covered by this license.
