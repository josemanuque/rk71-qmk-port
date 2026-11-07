"""
RK71 RGB Keyboard - HID Communication & ISP Trigger Script
Reverse engineered from firmware V1.12 and PC software V1.00n

Hardware:  SONiX SN32F240B (ARM Cortex-M0, 64KB flash)
Normal mode:  USB VID=0x05AC  PID=0x024F  (Apple keyboard identity)
ISP/DFU mode: USB VID=0x0C45  PID=0x8006  (SONiX bootloader)

Config channel: 64-byte HID Feature Reports on Interface 0 (keyboard HID interface)
  - No Report ID prefix; raw 64-byte writes/reads on the control endpoint
  - Usage Page 0x0C (Consumer), Usage 0x00, bSize=8, bCount=64

ISP trigger: send 8-byte command AA 42 89 5A FF 71 62 CC (zero-padded to 64 bytes)
  as a SET_FEATURE report to transition keyboard into SONiX ISP bootloader.
  After reset the keyboard reappears as VID=0x0C45 PID=0x8006 for firmware flashing.

Key layout:  6-row × 16-col matrix, 71 keys (compact TKL w/ numpad)
Lighting modes (ID 0-19): Static, SingleOn, SingleOff, Glittering, Falling,
  Colourful, Breath, Spectrum, Outward, Scrolling, Rolling, Rotating,
  Explode, Launch, Ripples, Flowing, Pulsating, Tilt, Shuttle, UserDefine

Requirements: pip install hid  (wraps hidapi)
"""

import hid
import time
import struct

# ── Device constants ──────────────────────────────────────────────────────────
VID_NORMAL = 0x05AC   # Apple VID used in normal operation
PID_NORMAL = 0x024F
VID_ISP    = 0x0C45   # SONiX ISP bootloader
PID_ISP    = 0x8006

REPORT_SIZE = 64      # Feature report payload size

# ── ISP trigger command (from UISettings.ini: CheckDeviceCmd=AA42895AFF7162CC)
ISP_TRIGGER = bytes([0xAA, 0x42, 0x89, 0x5A, 0xFF, 0x71, 0x62, 0xCC])


def find_keyboard(vid=VID_NORMAL, pid=PID_NORMAL):
    """Return the first matching HID device path, or None."""
    for dev in hid.enumerate(vid, pid):
        # Interface 0 is the keyboard HID (boot keyboard, usage page 0x01)
        if dev.get('usage_page') == 1 and dev.get('usage') == 6:
            return dev['path']
    # Fallback: return any matching device
    for dev in hid.enumerate(vid, pid):
        return dev['path']
    return None


def open_keyboard(vid=VID_NORMAL, pid=PID_NORMAL):
    path = find_keyboard(vid, pid)
    if path is None:
        raise RuntimeError(f"Keyboard not found (VID={hex(vid)} PID={hex(pid)}). "
                           "Make sure the keyboard is plugged in.")
    dev = hid.device()
    dev.open_path(path)
    dev.set_nonblocking(1)
    mfr = dev.get_manufacturer_string()
    prod = dev.get_product_string()
    print(f"Opened: {mfr} - {prod}  [{path}]")
    return dev


def send_feature(dev, payload: bytes):
    """Send a 64-byte SET_FEATURE report (no Report ID)."""
    if len(payload) > REPORT_SIZE:
        raise ValueError(f"Payload too long ({len(payload)} > {REPORT_SIZE})")
    buf = payload + b'\x00' * (REPORT_SIZE - len(payload))
    # hidapi feature report needs a leading 0x00 Report ID byte
    dev.send_feature_report(b'\x00' + buf)


def recv_feature(dev) -> bytes:
    """Read a 64-byte GET_FEATURE report."""
    # Request: report ID 0x00, read 65 bytes (ID + 64 data)
    data = dev.get_feature_report(0x00, REPORT_SIZE + 1)
    return bytes(data[1:])  # strip report ID byte


# ── Enter ISP / DFU bootloader ────────────────────────────────────────────────

def enter_isp_mode():
    """
    Send the ISP trigger command to put the keyboard into SONiX ISP bootloader.
    After calling this the keyboard resets.  Wait ~2 s then look for
    VID=0x0C45 PID=0x8006 to flash new firmware with the SONiX ISP protocol.
    """
    print("Connecting to keyboard in normal mode...")
    dev = open_keyboard()
    print(f"Sending ISP trigger: {ISP_TRIGGER.hex().upper()}")
    send_feature(dev, ISP_TRIGGER)
    dev.close()
    print("ISP trigger sent.  Keyboard should reboot into bootloader in ~1 s.")
    print(f"Look for: VID={hex(VID_ISP)} PID={hex(PID_ISP)}")


# ── Feature report command helpers ───────────────────────────────────────────
# The exact command protocol below is partially reverse-engineered.
# Byte 0 of every feature report is the COMMAND byte.
# Commands observed in existing open-source ports for SN32F240B keyboards:

# NOTE: These command bytes are EDUCATED GUESSES, not confirmed from firmware.
# Firmware analysis confirmed the 64-byte feature report channel is real
# (HID descriptor at flash 0x7592), but the USB RX handler stores raw bytes
# into RAM buffer and delegates to the main command loop — the byte→action
# mapping was not traced to completion. Test empirically before relying on these.
CMD_GET_FW_VERSION  = 0x01
CMD_SET_LIGHT_MODE  = 0x0A   # byte[1]=mode(0-19), byte[2]=brightness(0-15)
CMD_SET_LIGHT_COLOR = 0x0B   # byte[1]=mode, byte[2..4]=R,G,B
CMD_SET_KEY_COLOR   = 0x0C   # per-key RGB for UserDefine mode
CMD_PROFILE_SWITCH  = 0x14   # byte[1]=profile index (0-2)
CMD_SAVE_TO_FLASH   = 0x50   # commit current settings to firmware EEPROM area

LIGHT_MODES = {
    0:  "Static",
    1:  "SingleOn",
    2:  "SingleOff",
    3:  "Glittering",
    4:  "Falling",
    5:  "Colourful",
    6:  "Breath",
    7:  "Spectrum",
    8:  "Outward",
    9:  "Scrolling",
    10: "Rolling",
    11: "Rotating",
    12: "Explode",
    13: "Launch",
    14: "Ripples",
    15: "Flowing",
    16: "Pulsating",
    17: "Tilt",
    18: "Shuttle",
    19: "UserDefine",
}


def get_firmware_version(dev) -> str:
    send_feature(dev, bytes([CMD_GET_FW_VERSION]))
    time.sleep(0.05)
    resp = recv_feature(dev)
    # Response format: [cmd, major, minor, patch, ...]
    major, minor = resp[1], resp[2]
    return f"V{major}.{minor:02d}"


def set_light_mode(dev, mode: int, brightness: int = 15, speed: int = 11):
    """
    mode:       0-19 (see LIGHT_MODES)
    brightness: 0-15 (0=off, 15=max)
    speed:      0-15 (frequency index; 0=slow, 15=fast)
    """
    if mode not in LIGHT_MODES:
        raise ValueError(f"mode must be 0-19, got {mode}")
    brightness = max(0, min(15, brightness))
    send_feature(dev, bytes([CMD_SET_LIGHT_MODE, mode, brightness, speed]))
    print(f"Light mode set: {LIGHT_MODES[mode]} (brightness={brightness}, speed={speed})")


def set_light_color(dev, mode: int, r: int, g: int, b: int):
    """Set the primary color for the given light mode."""
    send_feature(dev, bytes([CMD_SET_LIGHT_COLOR, mode, r, g, b]))
    print(f"Color for mode {LIGHT_MODES.get(mode, mode)}: R={r} G={g} B={b}")


def switch_profile(dev, profile: int):
    """Switch to profile 0, 1, or 2."""
    if profile not in (0, 1, 2):
        raise ValueError("profile must be 0, 1, or 2")
    send_feature(dev, bytes([CMD_PROFILE_SWITCH, profile]))
    print(f"Switched to Profile {profile + 1}")


def save_to_flash(dev):
    """Persist current settings to the EEPROM emulation area (0xEE9C-0xFFFC in flash)."""
    send_feature(dev, bytes([CMD_SAVE_TO_FLASH]))
    time.sleep(0.5)
    print("Settings saved to flash.")


# ── Key matrix coordinates ────────────────────────────────────────────────────
# From firmware: 6 rows × 16 columns = 96 positions (71 physical keys used)
# Key index = row * 16 + col  (matches UIText KeyCompare IDs: ROW_COL)
# Standard HID key codes embedded in firmware at ~0x78F0

HID_KEYCODES = {
    # Modifier keys
    0xE0: "LCtrl", 0xE1: "LShift", 0xE2: "LAlt", 0xE3: "LWin",
    0xE4: "RCtrl", 0xE5: "RShift", 0xE6: "RAlt", 0xE7: "RWin",
    # Row 0 (F-row)
    0x29: "Esc",  0x3A: "F1",  0x3B: "F2",  0x3C: "F3",  0x3D: "F4",
    0x3E: "F5",   0x3F: "F6",  0x40: "F7",  0x41: "F8",  0x42: "F9",
    0x43: "F10",  0x44: "F11", 0x45: "F12", 0x46: "PrtSc", 0x47: "ScrLk", 0x48: "Pause",
    # Row 1 (number row)
    0x35: "`", 0x1E: "1", 0x1F: "2", 0x20: "3", 0x21: "4", 0x22: "5",
    0x23: "6", 0x24: "7", 0x25: "8", 0x26: "9", 0x27: "0",
    0x2D: "-", 0x2E: "=", 0x2A: "Backspace",
    0x49: "Insert", 0x4A: "Home", 0x4B: "PgUp",
    # Row 2 (QWERTY)
    0x2B: "Tab", 0x14: "Q", 0x1A: "W", 0x08: "E", 0x15: "R", 0x17: "T",
    0x1C: "Y", 0x18: "U", 0x0C: "I", 0x12: "O", 0x13: "P",
    0x2F: "[", 0x30: "]", 0x31: "\\",
    0x4C: "Delete", 0x4D: "End", 0x4E: "PgDn",
    # Row 3 (ASDF)
    0x39: "CapsLk", 0x04: "A", 0x16: "S", 0x07: "D", 0x09: "F", 0x0A: "G",
    0x0B: "H", 0x0D: "J", 0x0E: "K", 0x0F: "L", 0x33: ";", 0x34: "'", 0x28: "Enter",
    # Row 4 (ZXCV)
    0x50: "LShift", 0x1D: "Z", 0x1B: "X", 0x06: "C", 0x19: "V", 0x05: "B",
    0x11: "N", 0x10: "M", 0x36: ",", 0x37: ".", 0x38: "/", 0x52: "RShift",
    0x4F: "Right", 0x51: "Up",
    # Row 5 (bottom row)
    0x52: "LCtrl", 0x53: "LWin", 0x54: "LAlt", 0x2C: "Space",
    0x55: "RAlt", 0x56: "FN", 0x65: "App", 0x57: "RCtrl",
    0x50: "Left", 0x51: "Down",
    # Media keys (Consumer Control, 2-byte)
    # Sent via Interface 1 (Consumer HID)
}

# Fn-layer consumer key codes (from firmware @ 0x7A70)
FN_MEDIA_KEYS = {
    "F1":  0x00B5,  # Scan Next Track
    "F2":  0x00B6,  # Scan Previous Track
    "F3":  0x00B7,  # Stop
    "F4":  0x00CD,  # Play/Pause
    "F5":  0x00E0,  # Mute? (non-standard)
    "F9":  0x00E2,  # Mute
    "F10": 0x00E9,  # Volume Down
    "F11": 0x00EA,  # Volume Up
    "PrtSc": 0x0152, # AC Home
}


# ── Main demo ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "isp":
        enter_isp_mode()
        sys.exit(0)

    print("RK71 RGB Keyboard - HID communication demo")
    print("Usage: python rk71_hid.py isp   <- enter ISP/DFU bootloader mode")
    print()
    print("Available light modes:")
    for idx, name in LIGHT_MODES.items():
        print(f"  {idx:2d}: {name}")
    print()

    try:
        dev = open_keyboard()
    except RuntimeError as e:
        print(f"Error: {e}")
        sys.exit(1)

    try:
        print("Reading firmware version...")
        ver = get_firmware_version(dev)
        print(f"Firmware: {ver}")
        print()
        print("Setting Spectrum Cycling mode (mode 7), brightness 12/15...")
        set_light_mode(dev, 7, brightness=12, speed=11)
        time.sleep(1)
        print()
        print("Done. Close with Ctrl+C or let the script exit.")
    finally:
        dev.close()
