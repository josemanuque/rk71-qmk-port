# RK71 RGB Keyboard — Reverse Engineering Analysis

## Hardware Identity

| Component | Value |
|---|---|
| MCU | SONiX **SN32F240B** (ARM Cortex-M0, 64 KB flash, ~16 KB SRAM) |
| Flash map | 0x0000–0xEE9B: code/data · 0xEE9C–0xFFFC: zeroed EEPROM emulation area |
| USB VID/PID (normal) | **0x05AC / 0x024F** (Apple keyboard identity — common OEM trick for Mac compat) |
| USB VID/PID (ISP bootloader) | **0x0C45 / 0x8006** (SONiX ISP protocol) |
| Firmware version | V1.12 (bcdDevice = 0x0112) |
| Firmware file | `Settings/FWFiles/SN32F240B_32.hex` (Intel HEX, 171 891 bytes → 64 KB binary) |

---

## USB Descriptor Layout

### Device Descriptor (@ flash 0x7580)
```
bcdUSB = 0x0200 (USB 2.0)
bDeviceClass = 0x00 (Composite)
bMaxPacketSize0 = 64
idVendor  = 0x05AC  ← Apple
idProduct = 0x024F
bcdDevice = 0x0112  ← firmware V1.12
iManufacturer = 1 ("SONIX USB DEVICE")
iProduct      = 2 ("DEMO")
bNumConfigurations = 1
```

### Configuration Descriptor — Boot config (59 bytes @ 0x772E)
Two HID interfaces, `bmAttributes = 0xA0` (remote wakeup), 100 mA:

| Interface | Protocol | EP | Interval | HID Report Desc |
|---|---|---|---|---|
| 0 — Keyboard | 1 (Boot Keyboard) | EP1 IN, 16 B | 1 ms | 89 bytes |
| 1 — Media/Mouse | 2 (Boot Mouse) | EP2 IN, 16 B | 1 ms | 158 bytes |

### Configuration Descriptor — Extended (417 bytes @ 0x7641)
Adds Consumer Controls, vendor-specific channels (Interface 2 = GamePad / Interface 3 = Vendor 0xFF).

---

## HID Report Descriptor — Interface 0 (89 bytes @ 0x7592)

```
05 01  Usage Page (Generic Desktop)
09 06  Usage (Keyboard)
A1 01  Collection Application

  05 07  Usage Page (Keyboard)
  19 E0 29 E7  Usage Min/Max E0–E7 (modifier keys)
  15 00 25 01  Logical Min 0, Max 1
  75 01 95 08  Size 1, Count 8
  81 02        Input  [modifier bits — 1 byte]

  95 01 75 08  Count 1, Size 8
  81 01        Input  [reserved byte]

  95 05 75 01  Count 5, Size 1
  05 08        Usage Page (LEDs)
  19 01 29 05  Usage Min NumLock, Max Kana
  91 02        Output [LED state — 5 bits]

  95 01 75 03
  91 01        Output [LED padding — 3 bits]

  05 07        Usage Page (Keyboard)
  19 00 2A FF 00  Usage Min 0, Max 255
  95 05 75 08  Count 5, Size 8
  15 00 26 FF 00
  81 00        Input  [5 key-code bytes — Array]

  05 FF 09 03  Usage Page Vendor 0xFF, Usage 0x03
  75 08 95 01
  81 02        Input  [1 vendor status byte]

  05 0C 09 00  Usage Page Consumer, Usage 0
  15 80 25 7F  Logical Min –128, Max 127
  95 40 75 08  Count 64, Size 8
  B1 02        Feature  ← 64-BYTE CONFIG CHANNEL

C0 End Collection
```

**Input report = 8 bytes** (modifier + reserved + 5 keycodes + 1 vendor byte).  
**Feature report = 64 bytes** (no Report ID, raw write to control endpoint EP0).  
This feature report is the entire configuration channel for RGB, macros, profiles, etc.

---

## Configuration Database (SQLite)

`RecoverSetting/GK/GamingKeyboard.gkdb` is a plain SQLite database installed alongside the app.

| Table | Purpose |
|---|---|
| `ProfileSummary` | 3 profiles, active/used flags, current light mode ID |
| `KeyCustomization` | Per-key remap definitions (`"type?value"` format) |
| `KeyLightCustomization` | Per-key RGB color in UserDefine mode |
| `KeyLightBreathing/Reactive/…` | Lighting effect parameters |
| `KeyLightGeneral` | Active params for modes 9–19 |
| `GamingMode` | Alt+Tab / Alt+F4 / Win-key disable flags |
| `MacroSummary` / `MacroStep` | Stored macros |
| `FWMacroSummary` | On-device macro slots (10 slots) |

Default profile has **KeyLightMode = 19** (UserDefine off → shows as mode 19 in the UI).

---

## Lighting Modes (IDs 0–19)

| ID | Name | ID | Name |
|---|---|---|---|
| 0 | Static | 10 | Rolling |
| 1 | SingleOn | 11 | Rotating |
| 2 | SingleOff | 12 | Explode |
| 3 | Glittering | 13 | Launch |
| 4 | Falling | 14 | Ripples |
| 5 | Colourful | 15 | Flowing |
| 6 | Breath | 16 | Pulsating |
| 7 | Spectrum | 17 | Tilt |
| 8 | Outward | 18 | Shuttle |
| 9 | Scrolling | 19 | UserDefine |

The official PC software only exposes modes 0–8 in its UI. Modes 9–19 are hidden but fully functional — they can be activated by sending the appropriate feature report or by editing the SQLite DB.

---

## ISP / Bootloader Mode

**Trigger command** (from `UISettings.ini`, `CheckDeviceCmd`):
```
AA 42 89 5A FF 71 62 CC
```
Send this as a **64-byte HID SET_FEATURE report** (zero-padded) to the keyboard while it is in normal mode (VID=0x05AC, PID=0x024F). The keyboard immediately resets into the SONiX ISP bootloader (VID=0x0C45, PID=0x8006).

**Version gate**: The ISP flasher checks `CurVersion = 0x0109`. Devices reporting firmware ≥ 0x0109 get the "already updated" message in the GUI. The keyboard is at 0x112 (> 0x109) so the official tool refuses to reflash. The ISP trigger command itself still works — it just bypasses the GUI check.

---

## Key Matrix

6 rows × 16 columns = 96 positions (71 physical keys).  
Matrix-to-label mapping in `Message/GK/KeyboardIDMapping.xml` as `ROW_COL` (0-indexed).

**Fn-layer media keys** (Consumer Control, 2-byte HID usages):

| Fn+ | Consumer Usage | Action |
|---|---|---|
| F1 | 0x00B5 | Next Track |
| F2 | 0x00B6 | Prev Track |
| F3 | 0x00B7 | Stop |
| F4 | 0x00CD | Play/Pause |
| F9 | 0x00E2 | Mute |
| F10 | 0x00E9 | Volume − |
| F11 | 0x00EA | Volume + |
| PrtSc | 0x0152 | AC Home |

---

## EEPROM Emulation Area

Flash pages 0xEE9C–0xFFFC (~4.4 KB) are zeroed in the distributed firmware HEX. At runtime the firmware writes per-key RGB colors, macro definitions, and profile settings into this area using its flash-write routines. The HEX file represents the factory-default blank state.

---

## LED Architecture (ARM Disassembly — CONFIRMED)

This was the critical unknown that caused broken LEDs with QMK ports.

### LED driver: direct GPIO multiplex — NO external IC

The stock firmware drives all 71 RGB LEDs **directly via GPIO pins**. There is no
IS31FL3731, IS31FL3733, or any other external I2C/SPI LED controller chip on this board.
Any QMK port that enables `RGB_MATRIX_DRIVER = IS31FL3731` (or similar) will produce
no LED output because those drivers expect an I2C LED chip that does not exist here.

### SN32F240B peripheral map (confirmed from disassembly)

| Address | Peripheral |
|---|---|
| 0x40002000 | I2C0 controller |
| 0x40010000 | WDT (watchdog timer — fed via key 0x5AFA55AA) |
| 0x4001c000 | USB endpoint controller (IRQ6 = USB RX handler) |
| 0x40032000 | CT16B PWM timer (PWMCTRL at +0x40) |
| 0x40044000 | GPIO_P0 |
| 0x40046000 | GPIO_P1 |
| 0x40048000 | GPIO_P2 |
| 0x4004a000 | GPIO_P3 |
| 0x4005c000 | SYS (clock/power management) |
| 0x40062000 | I2C bus master (key scan or config channel) |

### GPIO direction map (from init function at flash 0x653c)

| Port | Base addr | MODE register | Input pins | Output pins |
|---|---|---|---|---|
| P0 | 0x40044000 | 0x7ff9 | P0.1, P0.2, P0.15 | P0.0, P0.3–P0.14 |
| P1 | 0x40046000 | 0xffff | — | ALL (P1.0–P1.15) |
| P2 | 0x40048000 | 0x7fff | P2.15 | P2.0–P2.14 |
| P3 | 0x4004a000 | 0x0078 | P3.0–P3.2, P3.7–P3.15 | P3.3–P3.6 |

GPIO register layout (SN32F240B, 0x2000 spacing between ports):
- `+0x00` DATA, `+0x04` MODE, `+0x08` LATCH, `+0x20` BSET, `+0x24` BCLR, `+0x28` TOGGLE

### LED state machine

- **3-phase cycle** (state 0 / 1 / 2 at RAM 0x20000271), corresponding to R / G / B channels
- **18 sub-cycles** per complete frame at RAM 0x2000026e (wraps at 0x12) → 6 key-matrix rows × 3 colors
- **PWM counter** at RAM 0x20000270, range 0–63 (0x3f) — incremented each SysTick tick
- Each state reads brightness bytes from RAM 0x2000025c (and 0x20000262 for state 1) and compares to the counter; above threshold → BSET (LED on), at/below → BCLR (LED off)

### LED column drivers (confirmed GPIO bits)

| State 0 channels | GPIO | Bit |
|---|---|---|
| Channel 0 (brightness[0]) | P1 | 9 |
| Channel 1 (brightness[1]) | P1 | 10 |
| Channel 2 (brightness[2]) | P1 | 11 |
| Channel 3 (brightness[3]) | P1 | 12 |
| Channel 4 (brightness[4]) | P2 | 1 |

State 1 drives P1.9/10/11, P3.6/4/3 and additional P2 bits; state 2 adds P2.2 and P3 bits.
P3.3–P3.6 are **row-select** lines (driven per sub-cycle to activate one LED row at a time).

### Full GPIO-to-key LED mapping (not yet complete)

The exact LED index → GPIO pin mapping (which brightness byte slot corresponds
to which physical key) requires cross-referencing the 18 × 5 = 90 slots with the
key positions from `KeyboardIDMapping.xml`. This mapping is needed to build a QMK
`RGB_MATRIX` layout. Physical PCB tracing or a logic analyser capture would
confirm it in one session; the firmware analysis can narrow it to ~90 candidates.

---

## Using QMK — Correct Approach for This Board

> ⚠️ This keyboard uses **direct GPIO LED drive** — not IS31FL3731/3733. Using an
> IS31FL QMK driver produces no LED output (the chip simply does not exist).

### Step 1 — Enter ISP bootloader mode

Send the ISP trigger as a 64-byte HID SET_FEATURE report:
```
AA 42 89 5A FF 71 62 CC  (zero-padded to 64 bytes)
```
The keyboard resets into the SONiX ISP bootloader (VID=0x0C45, PID=0x8006).
Use `python rk71_hid.py isp` from this project.

### Step 2 — Flash QMK

Use the SONiX ISP flasher (`sonix_flasher` or `hfd_bootloader`). Target VID=0x0C45,
PID=0x8006. The keyboard definition in QMK must specify:
- `MCU = SN32F240B`
- `BOOTLOADER = sn32-dfu` (or SONiX HFD)
- `RGB_MATRIX_DRIVER = custom` with direct GPIO writes (not IS31FL)

### Step 3 — Restore stock firmware

If you need to go back: keep `rk71_fw.bin` as a backup. Enter ISP mode via the
QMK RESET key, then re-flash `rk71_fw.bin`.

### Step 4 — Identify your exact hardware revision

If a community QMK file for RK71 doesn't work, check flash offset 0x7580 for the
Apple Device Descriptor with `bcdDevice = 0x01xx`. That confirms the SN32F240B
variant with the direct-drive LED matrix described in this document.

---

---

## Files Generated

| File | Contents |
|---|---|
| `rk71_fw.bin` | 64 KB flat binary extracted from the Intel HEX firmware |
| `rk71_hid.py` | Python HID helper: ISP trigger, feature report R/W, lighting control |
| `ANALYSIS.md` | This document |
