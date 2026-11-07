#!/usr/bin/env python3
"""
RK71 ISP Mode Trigger - Based on firmware RE of SN32F240B at:
  - Write at 0x244E: RAM[0x2000013A] = packet[idx*4+2] when packet[idx*4+3] & 0x70 == 0x30
  - Check at 0x33E8: if RAM[0x2000013A] == 0xE5 → trigger SYSRESETREQ → ISP
  - XOR key at 0x20000132 starts at 0x00 (BSS), so raw bytes = decoded bytes
  - idx comes from OFFSET_184 (starts at 0 in BSS)

So ISP trigger packet (64 bytes):
  byte 2 = 0xE5  (data byte → written to ISP_FLAG)
  byte 3 = 0x30  (type byte → 0x30 & 0x70 == 0x30 ✓)
  all others = 0x00

Target: VID=0x05AC / PID=0x024F (Apple keyboard identity)
ISP: VID=0x0C45 / PID=0x8006
"""

import sys
import time

try:
    import hid
except ImportError:
    print("ERROR: hid library not found. Install with: pip install hidapi")
    sys.exit(1)

NORMAL_VID = 0x05AC
NORMAL_PID = 0x024F
ISP_VID    = 0x0C45
ISP_PID    = 0x8006

def find_device(vid, pid):
    devices = hid.enumerate(vid, pid)
    return devices

def check_isp_mode():
    """Return True if keyboard is in ISP mode."""
    return bool(find_device(ISP_VID, ISP_PID))

def build_isp_packet(byte2=0xE5, byte3=0x30, report_id=None, size=64):
    """Build the ISP trigger HID report."""
    if report_id is not None:
        pkt = bytes([report_id, 0x00, byte2, byte3]) + bytes(size - 4)
    else:
        pkt = bytes([0x00, 0x00, byte2, byte3]) + bytes(size - 4)
    return pkt

def try_send_isp(devices_info, byte2=0xE5, byte3=0x30):
    """Try sending ISP trigger to all matching HID interfaces."""
    sent_any = False

    for dev_info in devices_info:
        path = dev_info['path']
        usage_page = dev_info.get('usage_page', 0)
        usage = dev_info.get('usage', 0)
        iface = dev_info.get('interface_number', -1)

        print(f"  Interface {iface}: usage_page=0x{usage_page:04X} usage=0x{usage:04X}")

        try:
            d = hid.device()
            d.open_path(path)

            # Try without report ID first (some devices don't use report IDs)
            pkt = build_isp_packet(byte2, byte3, report_id=None)
            # hid.write() prepends a 0x00 (report ID placeholder) on Windows
            # so we pass 65 bytes: [0x00, B0, B1, 0xE5, 0x30, ...]
            full_pkt = bytes([0x00, 0x00, 0x00, byte2, byte3]) + bytes(60)

            try:
                r = d.write(full_pkt)
                if r > 0:
                    print(f"    -> write OK ({r} bytes)")
                    sent_any = True
            except Exception as e:
                print(f"    -> write failed: {e}")
                # Try feature report
                try:
                    r = d.send_feature_report(full_pkt)
                    if r > 0:
                        print(f"    -> feature_report OK ({r} bytes)")
                        sent_any = True
                except Exception as e2:
                    print(f"    -> feature_report also failed: {e2}")

            d.close()
        except Exception as e:
            print(f"    -> open failed: {e}")

    return sent_any

def main():
    print("=== RK71 ISP Trigger ===")
    print()

    # Check current state
    if check_isp_mode():
        print("ALREADY IN ISP MODE! VID=0x0C45/PID=0x8006 detected.")
        print("Run flash_qmk.py to flash firmware.")
        return

    devices = find_device(NORMAL_VID, NORMAL_PID)
    if not devices:
        print(f"Keyboard not found at VID=0x{NORMAL_VID:04X}/PID=0x{NORMAL_PID:04X}")
        print("Available HID devices:")
        for d in hid.enumerate():
            if d['vendor_id'] not in (0, 0x06CB, 0x1038):  # skip fingerprint, etc
                print(f"  VID={d['vendor_id']:04X} PID={d['product_id']:04X} "
                      f"iface={d.get('interface_number',-1)} "
                      f"usagepage=0x{d.get('usage_page',0):04X} "
                      f"mfr={d.get('manufacturer_string','')} "
                      f"prod={d.get('product_string','')}")
        return

    print(f"Found {len(devices)} HID interface(s) for VID={NORMAL_VID:04X}/PID={NORMAL_PID:04X}:")
    for d in devices:
        print(f"  Interface {d.get('interface_number')}: "
              f"usage_page=0x{d.get('usage_page',0):04X} "
              f"usage=0x{d.get('usage',0):04X} "
              f"serial={d.get('serial_number','')}")
    print()

    # Strategy 1: Try the firmware-derived packet format
    # From RE: packet[2]=0xE5, packet[3]=0x30 triggers ISP
    print("Strategy 1: Firmware-derived packet (byte[2]=0xE5, byte[3]=0x30)")
    for dev_info in devices:
        path = dev_info['path']
        iface = dev_info.get('interface_number', -1)
        usage_page = dev_info.get('usage_page', 0)

        print(f"  Trying interface {iface} (usage_page=0x{usage_page:04X})...")

        # Build the ISP packet: [0x00(report_id), 0x00, 0x00, 0xE5, 0x30, 0x00...]
        # On Windows HID, write() prepends 0x00 as report ID placeholder
        pkt = bytes([0x00,  # Windows report ID placeholder
                     0x00,  # byte 0 of actual report
                     0x00,  # byte 1
                     0xE5,  # byte 2 → ISP_FLAG value
                     0x30,  # byte 3 → type (& 0x70 = 0x30)
                     ]) + bytes(60)  # bytes 4-63 = 0x00

        try:
            d = hid.device()
            d.open_path(path)
            r = d.write(pkt)
            d.close()
            print(f"    write() returned {r}")
        except Exception as e:
            print(f"    write() error: {e}")
            # Try feature report
            try:
                d = hid.device()
                d.open_path(path)
                r = d.send_feature_report(pkt)
                d.close()
                print(f"    send_feature_report() returned {r}")
            except Exception as e2:
                print(f"    send_feature_report() error: {e2}")

    # Check if ISP mode triggered
    print()
    print("Waiting 2s for keyboard to reset...")
    time.sleep(2)

    if check_isp_mode():
        print("SUCCESS! Keyboard entered ISP mode (VID=0x0C45/PID=0x8006)!")
        print("Run: python flash_qmk.py")
        return

    # Strategy 2: Try different byte positions (in case idx != 0)
    print("ISP not triggered yet. Trying other byte positions...")
    print()

    byte_positions = [
        # (data_pos, type_pos, description)
        (0, 1, "bytes[0]=0xE5 bytes[1]=0x30"),
        (1, 0, "bytes[1]=0xE5 bytes[0]=0x30"),
        (4, 5, "bytes[4]=0xE5 bytes[5]=0x30"),
        (6, 7, "bytes[6]=0xE5 bytes[7]=0x30"),
        (2, 3, "bytes[2]=0xE5 bytes[3]=0xE5 (both set)"),
    ]

    for data_pos, type_pos, desc in byte_positions:
        print(f"  Trying: {desc}")
        pkt_data = bytearray(65)  # +1 for Windows report ID placeholder
        pkt_data[data_pos + 1] = 0xE5  # +1 for the leading 0x00 (report ID)
        pkt_data[type_pos + 1] = 0x30

        for dev_info in devices:
            path = dev_info['path']
            try:
                d = hid.device()
                d.open_path(path)
                r = d.write(bytes(pkt_data))
                d.close()
                if r > 0:
                    print(f"    interface {dev_info.get('interface_number')}: write OK")
            except:
                pass

        time.sleep(0.5)
        if check_isp_mode():
            print(f"  SUCCESS with {desc}!")
            return

    # Strategy 3: Try vendor-specific commands (common SONiX/RK patterns)
    print()
    print("Strategy 3: Known SONiX/RK vendor commands...")
    vendor_packets = [
        # (description, bytes list)
        ("SONiX probe 0x05", [0x00, 0x05] + [0x00]*63),
        ("SONiX ISP 0xAA55", [0x00, 0xAA, 0x55] + [0x00]*62),
        ("RK ISP 0x06 0xAA", [0x00, 0x06, 0xAA] + [0x00]*62),
        ("Type 0x30 + 0xE5 at byte1", [0x00, 0xE5, 0x30] + [0x00]*62),
        ("All 0x30s", [0x00, 0x30, 0xE5, 0x30] + [0x00]*61),
        ("Reboot cmd", [0x00, 0xAA, 0x55, 0xBE, 0xEF] + [0x00]*60),
    ]

    for desc, pkt_list in vendor_packets:
        pkt = bytes(pkt_list[:65])
        if len(pkt) < 65:
            pkt += bytes(65 - len(pkt))

        print(f"  Trying: {desc}")
        for dev_info in devices:
            path = dev_info['path']
            try:
                d = hid.device()
                d.open_path(path)
                r = d.write(pkt)
                d.close()
                if r > 0:
                    print(f"    interface {dev_info.get('interface_number')}: write OK ({r})")
            except Exception as e:
                print(f"    interface {dev_info.get('interface_number')}: {e}")

        time.sleep(0.3)
        if check_isp_mode():
            print(f"  SUCCESS with '{desc}'!")
            return

    # Final check
    print()
    if check_isp_mode():
        print("SUCCESS! Keyboard is in ISP mode.")
    else:
        print("ISP mode not triggered. Keyboard is still at VID=0x05AC/PID=0x024F.")
        print()
        print("The firmware analysis shows the ISP path requires:")
        print("  1. FLAG_18D (RAM[0x2000018D]) to be non-zero (USB initialized)")
        print("  2. The endpoint buffer counter to route the packet to function 0x2384")
        print("  3. endpoint_buf[idx*4+2] = 0xE5, endpoint_buf[idx*4+3] = 0x30")
        print()
        print("The XOR key (RAM[0x20000132]) starts at 0x00 so no XOR needed.")
        print()
        print("Possible issues:")
        print("  - Packet sent to wrong interface/endpoint")
        print("  - idx (OFFSET_184) is not 0 (need to check USB enumeration code)")
        print("  - Some prior protocol state is required")
        print("  - The HID vendor interface may not accept our reports")

if __name__ == "__main__":
    main()
