# Stock Royal Kludge firmware (original, unmodified)

These are the vendor files, kept exactly as downloaded, so the keyboard can always go back to factory firmware.

| File | What it is |
|---|---|
| `rk71_fw_v1.12.bin` | Raw 64 KB flash image of stock firmware V1.12 (USB ID `05AC:024F`). Flash at offset 0. |
| `RK71 RGB Firmware_V1.12_190603.exe` | Royal Kludge's official updater for V1.12 (HFD ISP tool). |
| `RK71 RGB Keyboard PC Software V1.00n.exe` | Royal Kludge's Windows configuration software. |

The stock firmware is the only one that drives the Bluetooth module. See `docs/BLUETOOTH.md`.

## Going back to stock

1. Put the keyboard in the SN32 ROM bootloader (USB `0C45:7040`):
   * from QMK: **Fn + Pause**, or hold **Esc** while plugging in (with the BT switch off);
   * from anything (last resort): short the left P1/P2 pad next to U4 (MCU pin 3, BOOT) to the USB
     shell while plugging in, and **keep it shorted for the whole flash**.
2. Flash: `bash tools/flash_rk71.sh stock/rk71_fw_v1.12.bin`
