# Stock firmware V1.12: how it works

Notes from disassembling `rk71_fw_v1.12.bin` (Thumb, load address 0) and taking the vendor updater apart. Addresses
are flash offsets in the `.bin`. "Confirmed" means it was read from code or data, or tested on the keyboard.
"Likely" means a guess from context that has not been tested.

## USB identity

* Device descriptor @`0x7580`: `05AC:024F` (an Apple keyboard ID), bcdDevice `0x0112` (= V1.12), no serial number.
* Configuration @`0x772E`, two HID interfaces:
  * **Interface 0**, boot keyboard, report descriptor @`0x7592` (89 bytes): 6KRO keyboard, LEDs, a vendor input
    byte (usage page `0xFF`), and **a 64-byte vendor feature report with no report ID**. Both the RK configuration
    software and the ISP command use this feature report.
  * **Interface 1**: consumer keys (report ID 3), system power/sleep/wake (ID 2), NKRO keyboard (ID 1).
* Over Bluetooth the ITON module also identifies as `05AC:024F` (seen as `{00001124-…}_vid&000205ac_pid&024f` on
  Windows). That link doesn't carry the feature report to the MCU, so updates only work over the cable.

## How the updater gets the keyboard into flashing mode

The official updater is Sonix's generic "SONiX USB MCU ISP Tool", rebranded as "HFD ISP Tool". Its settings
and the firmware sit in an embedded zip (PE resource RCDATA 4011, extracted to `updater_contents/`). Other resources:
4007 = `12345678` (default ISP password field), 4008/4009 = `0C45`/`7903` (default VID/PID fields in the UI),
4013 = build time `2019/06/24 18:36`.

`UISettings.ini` says:

```
CheckDeviceCmd = AA 42 89 5A FF 71 62 CC      <- the "enter ISP" command
CheckBootLoaderID = 1
[SpecialPID0] 0C45:8006   [SpecialPID1] 05AC:0256   [SpecialPID2] 05AC:024F   (all SN32F24xB, SN32F240B_32.hex)
```

What happens when you click Start:

1. The updater enumerates HID devices (SetupAPI) looking for one of the three IDs above, and opens interface 0
   (`…&mi_00`). Windows doesn't let any program open a keyboard for reading or writing, so it opens the device
   with **no access rights**. That still allows feature reports.
2. `HidD_SetFeature` with report ID `00` + 64 bytes: `AA 42 89 5A FF 71 62 CC 00 00 …`.
3. **In the stock firmware** (confirmed in code):
   * The EP0 OUT handler @`0x18C8` copies the 64 bytes to RAM `0x200002C4`. If the first two words are
     `0x5A8942AA`, `0xCC6271FF` (the magic above, @`0x1944`), it sets state 2.
   * When the transfer's status stage finishes (@`0x1818`), it re-checks the magic, clears 64 words of USB buffer,
     and calls @`0x014C`. That writes `SYS0+0x24` and branches to **`0x1FFF0301`, the SN32 ROM bootloader**.
   * There's no reset and no magic RAM flag (an earlier note claiming "write 0xE5 to 0x2000013A" was wrong).
4. The keyboard drops off USB and comes back as `0C45:7040` (ROM ISP). The updater then speaks the Sonix ISP
   protocol over feature reports (Get Firmware Version `0x01/0x21`, Compare ISP Password `0x02/0x22`, Enable Erase
   `0x04`, Enable Program `0x05`, Get Checksum `0x06`, Return User Mode `0x07`, Code Option `0x08/0x09`, …),
   writes `SN32F240B_32.hex`, and returns to user mode.

SonixFlasher implements the same steps: `-r hfd` sends that magic, and its normal flashing is step 4.
`tools/stock_enter_isp.py` does steps 1–3: with Python's standard library on Windows, or `hidapi` on Linux/macOS.

Why the earlier session's attempts "never triggered reliably": its scripts opened the keyboard with read/write
access (refused by Windows), or sent invented packets (`AA 55 …`, `0x33/0x81`).

QMK (our port) has its own way in: `QK_BOOT` (Fn+Pause) and Bootmagic (Esc held at plug-in). Both jump to the same
ROM address. QMK doesn't respond to the HFD magic.

## Stock key map

The key table @`0x7842` has 16 columns × 8 slots. Each byte is a standard HID usage; `A0`–`A7` are the modifiers
(`E0`–`E7`) and `AF` is Fn. Slot 0 is an F-key row left over from the vendor's template; the RK71 has no such
row. Slots 1–5 are the five real rows, the same as QMK's `ROW0`–`ROW4` in `keyboard/rk71_rgb`.

| | C0 | C1 | C2 | C3 | C4 | C5 | C6 | C7 | C8 | C9 | C10 | C11 | C12 | C13 | C14 | C15 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | | F1 | F2 | F3 | F4 | F5 | F6 | F7 | F8 | F9 | F10 | F11 | F12 | | | |
| **1** | Esc | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 0 | - | = | Bksp | Ins | Home |
| **2** | Tab | Q | W | E | R | T | Y | U | I | O | P | [ | ] | \\ | Del | End |
| **3** | Caps | A | S | D | F | G | H | J | K | L | ; | ' | | Enter | Pause | PgUp |
| **4** | LShift | (ISO \\) | Z | X | C | V | B | N | M | , | . | / | | RShift | ↑ | PgDn |
| **5** | LCtrl | Win | LAlt | | | | Space | | | | RAlt | **Fn** | RCtrl | ← | ↓ | → |

The `(ISO \)` position has no switch on the ANSI board.

### Fn layer

The Fn table @`0x7942` is 36 pairs (key → action), with the pair count stored at `0x798A`. A second copy @`0x798C`
is used when the Mac flag is set. Action codes below `0x78` are ordinary keys. `A8`–`AA` are system keys,
`B0`–`CF` index the consumer-key table @`0x79E4` (next, prev, stop, play, mute, vol+/-, browser keys, calculator,
…), and the rest are handled by the firmware's own routines.

| Fn + | Action code | What it does | Status |
|---|---|---|---|
| Esc | `35` | \` ~ | confirmed (plain key code) |
| 1 … = | `3A`–`45` | F1 … F12 | confirmed |
| Pause | `46` | Print Screen | confirmed |
| Q W E R T | `F3 F4 F5 AD F6` | Bluetooth device 1–5; hold 3 s = pair that slot | confirmed (see `docs/BLUETOOTH.md`) |
| P | `F1` | Tap: wired ↔ Bluetooth. Hold 3 s: pair the current slot. | confirmed |
| A / S | `AC` / `AB` | Windows / Mac mode (clears/sets the flag that selects the second Fn table) | confirmed in code |
| Space | `D2` | Hold ~3 s: runs a reset routine, then re-reads the saved wired/BT mode (flash `0x8009`) and re-applies it. Probably the factory reset. | likely |
| Tab | `DB` | Toggles a flag. A WASD ↔ arrows swap table exists @`0x79D4`, and this flag is the likely switch. | likely |
| Win | `D1` | Win-key lock | likely |
| ↑ / ↓ | `D4` / `D5` | Lighting brightness up / down | likely |
| ← / → | `D7` / `D6` | Lighting effect speed | likely |
| Ins / Home / End | `9D` / `D3` / `DA` | Lighting effect / colour selection | likely |
| Z / X / C, LCtrl | `93` / `94` / `95`, `9C` | Unknown (each has its own handler; not traced) | – |

Wired vs Bluetooth mode is saved at flash `0x8009`. The slide switch only connects the battery.

The QMK port deliberately keeps the confirmed bindings (F-keys, Bluetooth keys, Fn+P, Pause = PrtSc) the same, so
switching between the two feels familiar.
