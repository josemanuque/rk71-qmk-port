# RK71 QMK firmware: user guide

An open-source replacement for the Royal Kludge RK71 RGB's factory firmware, built on
[QMK](https://qmk.fm) (SonixQMK fork). You configure it live from the browser with [VIA](https://usevia.app),
on any OS, with no vendor software.

This guide describes the latest version (`main`, currently **v0.5.5b**). The change history is in the
[README](../README.md#branches-and-versions).

* [Stock vs this firmware](#stock-vs-this-firmware)
* [Installing](#installing)
* [Keys](#keys)
* [Wired and Bluetooth](#wired-and-bluetooth)
* [Lighting](#lighting)
* [Side lights and status](#side-lights-and-status)
* [Configuring with VIA](#configuring-with-via)
* [What is saved](#what-is-saved)
* [Limitations](#limitations)
* [Troubleshooting](#troubleshooting)
* [For developers](#for-developers)

## Stock vs this firmware

| | Stock V1.12 | This firmware |
|---|---|---|
| Source code | Closed binary (vendor Sonix/HFD SDK) | Open (QMK, GPL-2.0), in `keyboard/rk71_rgb` |
| Configuration | Royal Kludge's Windows app only | VIA in any Chromium browser (Windows, macOS, Linux), live, no install |
| Remapping | What the RK app allows | Every key on every layer, 5 layers, macros, any QMK keycode |
| Lighting | Built-in effects, custom per-key colours in the RK app | 19 QMK effects + solid colour, hue/saturation/speed in VIA |
| Bluetooth | 5 devices (Fn+Q…T) | Same keys, same 5 devices, plus automatic wired/Bluetooth from the cable |
| Side lights | Status only | Follow keyboard colour / fixed colour / off, colour balance and brightness, status overlay |
| Battery level | – | Fn+Space shows a 1/3/6-light bar on the side lights |
| Debounce | Vendor default | 10 ms per key (fixes chattering switches without slowing the others) |
| USB ID | `05AC:024F` (pretends to be an Apple keyboard) | `0C45:8071` (its own ID) |
| Sleep on battery | Deep sleep | Lighting off when idle, but the chip stays awake (see [Limitations](#limitations)) |

The RK configuration app doesn't work with this firmware, and VIA doesn't work with the stock firmware. To go
back to stock at any time, see [stock/README.md](../stock/README.md).

## Installing

1. Get [SonixFlasher](https://github.com/SonixQMK/SonixFlasher/releases) into `sonixflasher/sonixflasher.exe`.
2. Put the keyboard into the bootloader (USB `0C45:7040`). With the cable plugged in:
   * **from this firmware:** **Fn + Pause**
   * **from stock firmware:** `python tools/stock_enter_isp.py`
   * **if nothing works:** the BOOT-pad short in [stock/README.md](../stock/README.md#if-it-is-bricked-no-keys-no-lights-fnpause-does-nothing)
3. `bash tools/flash_rk71.sh releases/rk71_rgb_v0.5.5b.bin`

   Tip: start the script first. It waits for the bootloader, so you can then press Fn+Pause and it flashes
   straight away.
4. The keyboard restarts on its own. The first boot after a full flash starts from defaults: solid white
   lighting, wired, device slot 1.

Flashing works with the slide switch in either position, but the cable must be plugged in.

## Keys

The base layer is a normal ANSI 70% layout (see `keymaps/via/keymap.c`). Esc is *Grave Escape*: on its own it's
Esc, and with Shift it gives `~`.

### Fn layer

| Fn + | Does |
|---|---|
| Esc | \` |
| 1 … = | F1 … F12 |
| Ins / Home | Print Screen / previous track |
| Del / End | Play-pause / next track |
| PgUp / PgDn | Volume up / down |
| M | Mute |
| Enter | Lighting on / off |
| \\ | Next lighting effect |
| H | Lighting hue (colour) |
| ↑ / ↓ | Lighting brighter / dimmer |
| ← / → | Effect slower / faster |
| Win / Alt | Mac mode / Windows mode (remembered) |
| Ctrl (either) | **F-row lock** on/off (remembered). The Fn key glows orange while it's on. |
| Q W E R T | Bluetooth device 1–5. Hold 3 s: pair a new device in that slot. |
| P | Switch wired ↔ Bluetooth. Hold 3 s: pair the current slot again. |
| Backspace | Hold 3 s: forget all paired Bluetooth devices |
| Space | Show the battery level on the side lights |
| Pause | Bootloader (for flashing) |

While Fn is held, the P key shows the current mode (green = wired, blue = Bluetooth). In Bluetooth mode, the
current device key (Q–T) is lit blue too.

### F-row lock

With the lock on (Fn+Ctrl), the number row types F1…F12 without Fn. Fn then turns the F-keys into media keys:

| Fn + | F1 | F2 | F4 | F5 | F6 | F7 | F8 | F9 |
|---|---|---|---|---|---|---|---|---|
| does | screen dimmer | screen brighter | prev track | play-pause | next track | mute | vol − | vol + |

### Mac mode

Fn+Win switches to the Mac layer: the key next to Space becomes Cmd and the next one out becomes Option, on both
sides. Fn+Alt goes back to Windows. The Fn combinations use the physical keys, so they're the same in both modes.

## Wired and Bluetooth

* **Unplugged:** always Bluetooth (slide switch on).
* **Plugged in:** wired, unless you picked Bluetooth with Fn+P or Fn+Q…T. That choice is remembered.
  Unplugging and plugging in switches automatically: the firmware senses the cable.
* **Pair a new computer:**
  1. Hold Fn + Q (or W/E/R/T) for 3 s. The side lights blink blue quickly.
  2. On the computer, pick the keyboard in its Bluetooth settings (the name comes from the Bluetooth module, the
     same as with stock firmware). The side lights go solid blue for a moment once connected.
* **Switch computers:** tap Fn + the slot key.
* **Forget everything:** hold Fn+Backspace 3 s. The side lights flash red.

The slide switch only connects the battery. With it off, the keyboard works over the cable only.

## Lighting

19 QMK effects plus solid colour: breathing, band, cycles (all, left-right, up-down, pinwheel, spiral),
gradients, chevron, rain effects, reactive (lights up on key press), splash, typing heatmap. Change the effect
with Fn+\\ or in VIA, where you also get hue, saturation, brightness and speed.

* **Caps Lock:** the Caps key turns cool white (as on stock). On white or pale lighting, where that wouldn't
  stand out, it turns dark instead.
* **Computer asleep:** all lighting goes off.
* **On battery:** lighting turns off after 5 minutes without typing, and comes back with the next key press. It
  also turns off when the battery reports critically low.

## Side lights and status

The two edge strips have 6 lights each (light 1 = far end, 6 = nearest you). Both strips always show the same
thing.

**Normally** they follow the keyboard: the nearest of 7 colours (white, red, yellow, green, cyan, blue, magenta)
to the current lighting colour, at the keyboard's brightness. They go off when the lighting is off. In VIA you
can pick a fixed colour or turn them off instead.

**Status** takes over for a moment when something happens (unless turned off in VIA):

| What you see | Meaning |
|---|---|
| Fast blue blink | Pairing (waiting for a computer) |
| Slow blue blink | Connecting to the selected device |
| Solid blue, ~1 s | Connected |
| Solid green, 1.5 s | Switched to wired |
| Solid blue, 1.5 s | Switched to Bluetooth |
| Fast red flash, all | All pairings forgotten |
| Fn+Space: 6 green | Battery high |
| Fn+Space: 3 yellow (near end) | Battery medium |
| Fn+Space: 1 red (nearest) | Battery low |
| Fn+Space: nearest blinks red | No answer from the Bluetooth module (slide switch off?) |
| Nearest light slow red blink | Battery low, charge soon |

The connect/pair indication only shows after you press a Bluetooth key. Automatic reconnects (after waking up,
for example) are silent.

With side-light status turned off in VIA, the same information shows on the keys instead: the slot key
(Q–T) blinks blue, P flashes green/blue, Backspace red, and Space blinks red for low battery. The Fn+Space
battery bar exists only on the side lights, so with status off it shows nothing.

**The red LED near the space bar** is the charger's own "charging" light. It's wired directly to the charging
chip, so no firmware can control it.

## Configuring with VIA

1. Open [usevia.app](https://usevia.app) in Chrome or Edge.
2. The first time only: in **Settings**, turn on "Show Design tab". Then under **Design**, load
   `via/rk71_rgb_via.json` from this repository. VIA doesn't know this board otherwise.
3. **Authorize device**, then pick the RK71.

You get:

* **Configure → Keymap:** remap any key on all 5 layers (0 Windows, 1 Mac, 2 F-row lock, 3 Fn, 4 Fn+F-row
  media). The Bluetooth functions are under *Special → Custom*: BT 1–5, BT/USB, BT Clear, Battery.
* **Macros:** text and key sequences, assignable to any key.
* **Lighting:** effect, brightness, speed, colour.
* **Side lights:**
  * **Colour:** Follow keyboard / Fixed colour / Off (and which fixed colour)
  * **Brightness:** 0–31. This is multiplied by the keyboard's own brightness.
  * **Red / Green / Blue:** 0–31 each. The side lights sit behind a bluish diffuser, and these sliders balance it
    out. Defaults are 31 / 20 / 8 (warm), which looks close to neutral white through the diffuser.
  * **Show status:** status on the side lights (on) or on the keys (off)

VIA has to be connected over USB. Settings are saved about 2 seconds after you stop moving a slider.

Each light has slightly different red, green and blue chips, so a mixed colour like white can look a little
different from light to light. That's normal for these LEDs. Pure red, green or blue look the most even.

## What is saved

Kept across unplugging and power-off:

* Keymap, macros, lighting effect and colour, side-light settings
* Win/Mac mode, F-row lock, wired/Bluetooth choice, current device slot

Bluetooth pairings are stored in the Bluetooth module itself, so they survive reflashing. Everything else resets
to defaults when you flash a new image or switch to stock and back.

## Limitations

* **No deep sleep on battery yet.** The lighting turns off, but the chip and the radio stay awake. Slide the
  switch off when you're not using the keyboard on battery.
* **Storage is tight:** 5 layers is the maximum alongside VIA macros. The chip has 8 KB of RAM, and the
  firmware uses almost all of it.
* **Bootmagic (hold Esc while plugging in)** only works if the chip actually restarts, so slide the battery
  switch off first. Fn+Pause is easier.
* **Status lights:** Caps Lock may blink once when switching to Bluetooth.

## Troubleshooting

| Problem | Try |
|---|---|
| Keys don't work, lights off after flashing | Recovery via the BOOT pad: [stock/README.md](../stock/README.md#if-it-is-bricked-no-keys-no-lights-fnpause-does-nothing) |
| Fn+Pause and the keyboard seems dead | It's in the bootloader, waiting for a flash. Run the flash script, or unplug/replug to restart normally (with the slide switch off). |
| VIA doesn't find the keyboard | Use the cable, use Chrome/Edge, and load `via/rk71_rgb_via.json` in the Design tab |
| Bluetooth computer won't connect | Remove the keyboard from the computer's Bluetooth list, then hold Fn + slot key 3 s to pair again |
| Fn+Space blinks red | The Bluetooth module isn't answering: slide switch off, or the battery is completely flat |
| Want factory firmware back | [stock/README.md](../stock/README.md#going-back-to-stock) |

## For developers

* Source: `keyboard/rk71_rgb/`
  * `rk71_rgb.c`: modes, Bluetooth keys, status, VIA menu
  * `rk71_bt.c`: SPI driver for the Bluetooth module
  * `rk71_side.c`: side lights and cable detection
  * `keymaps/via`: the keymap
* `keyboard.json` and the VIA definition are generated by `tools/gen_rk71.py`. Edit that, not the outputs.
* Build: `bash tools/build.sh` (setup in the [README](../README.md#building)).
* Hardware findings: [BLUETOOTH.md](BLUETOOTH.md) (module protocol), [stock/FIRMWARE_NOTES.md](../stock/FIRMWARE_NOTES.md)
  (stock key map, ISP entry). The `diag` keymap toggles and shows unknown pins, which helps when mapping
  hardware.
