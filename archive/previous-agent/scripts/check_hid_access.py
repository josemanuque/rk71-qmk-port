#!/usr/bin/env python3
"""Diagnose HID access issues and try USB control transfers."""
import sys
import struct

try:
    import hid
    HAS_HID = True
except ImportError:
    HAS_HID = False

# Check what libs are available
print("Checking available USB/HID libraries:")
libs = {}
for name in ['hid', 'usb', 'pywinusb', 'win32file', 'win32api']:
    try:
        __import__(name)
        libs[name] = True
        print(f"  {name}: AVAILABLE")
    except ImportError:
        libs[name] = False
        print(f"  {name}: NOT INSTALLED")

print()

NORMAL_VID = 0x05AC
NORMAL_PID = 0x024F

if HAS_HID:
    devices = hid.enumerate(NORMAL_VID, NORMAL_PID)
    print(f"HID interfaces for VID=0x{NORMAL_VID:04X}/PID=0x{NORMAL_PID:04X}:")
    for d in devices:
        print(f"  Interface {d.get('interface_number')}: "
              f"usage_page=0x{d.get('usage_page',0):04X}  "
              f"usage=0x{d.get('usage',0):04X}  "
              f"path={d.get('path',b'').decode('ascii','ignore')[:60]}")
    print()

    # Try opening vendor interface and checking error
    for d in devices:
        if d.get('usage_page') == 0xFFFF:
            print(f"Testing vendor interface (0xFFFF/0x{d.get('usage',0):04X}):")
            dev = hid.device()
            try:
                dev.open_path(d['path'])
                print(f"  Opened OK")
                print(f"  Error after open: {dev.error()}")

                # Try write with report ID 0x00
                pkt = bytes([0x00, 0x00, 0x00, 0xE5, 0x30] + [0x00]*60)
                r = dev.write(pkt)
                print(f"  write(0x00, ...) returned {r}")
                print(f"  Error after write: {dev.error()}")

                # Try feature report
                r2 = dev.send_feature_report(bytes([0x00, 0x00, 0x00, 0xE5, 0x30] + [0x00]*60))
                print(f"  send_feature_report(0x00, ...) returned {r2}")
                print(f"  Error after feature: {dev.error()}")

                # Try getting feature report (read back)
                try:
                    data = dev.get_feature_report(0x00, 65)
                    print(f"  get_feature_report: {data[:8]}")
                except Exception as e:
                    print(f"  get_feature_report failed: {e}")

                dev.close()
            except Exception as e:
                print(f"  open failed: {e}")
            print()

    # Try ALL interfaces with detailed error info
    print("Trying all interfaces with error reporting:")
    for d in devices:
        iface = d.get('interface_number')
        up = d.get('usage_page', 0)
        u = d.get('usage', 0)

        # Try with different report IDs
        for report_id in [0x00, 0x01, 0x02, 0x06, 0x07, 0x0A, 0xFF]:
            pkt = bytes([report_id, 0x00, 0x00, 0xE5, 0x30] + [0x00]*60)
            try:
                dev = hid.device()
                dev.open_path(d['path'])
                r = dev.write(pkt)
                err = dev.error()
                dev.close()
                if r > 0:
                    print(f"  IFACE {iface} UP=0x{up:04X} RID=0x{report_id:02X}: WRITE OK! ({r} bytes)")
                elif r == -1:
                    print(f"  IFACE {iface} UP=0x{up:04X} RID=0x{report_id:02X}: write=-1 err={err}")
                    break
            except Exception as e:
                print(f"  IFACE {iface} UP=0x{up:04X} RID=0x{report_id:02X}: exception: {e}")
                break

# Try pyusb control transfers
if libs.get('usb'):
    import usb.core
    print("\nTrying pyusb control transfers...")
    dev = usb.core.find(idVendor=NORMAL_VID, idProduct=NORMAL_PID)
    if dev:
        print(f"Found device via pyusb: {dev}")
        try:
            # Try HID SET_REPORT (output report type=2)
            # bmRequestType=0x21 (host->device, class, interface)
            # bRequest=0x09 (SET_REPORT)
            # wValue = (type << 8) | report_id
            #   type: 1=input, 2=output, 3=feature
            data = bytes([0x00, 0x00, 0xE5, 0x30] + [0x00]*60)  # 64 bytes, no report ID prefix

            for iface_num in [0, 1]:
                for report_type in [2, 3]:  # output=2, feature=3
                    for report_id in [0x00, 0x01, 0x02]:
                        try:
                            wValue = (report_type << 8) | report_id
                            r = dev.ctrl_transfer(
                                bmRequestType=0x21,
                                bRequest=0x09,
                                wValue=wValue,
                                wIndex=iface_num,
                                data_or_wLength=data,
                                timeout=100
                            )
                            print(f"  ctrl_transfer iface={iface_num} type={report_type} ID=0x{report_id:02X}: {r} bytes OK!")
                        except usb.core.USBError as e:
                            if 'timeout' not in str(e).lower() and 'pipe' not in str(e).lower():
                                print(f"  ctrl_transfer iface={iface_num} type={report_type} ID=0x{report_id:02X}: {e}")
        except Exception as e:
            print(f"pyusb error: {e}")
    else:
        print(f"Device VID=0x{NORMAL_VID:04X}/PID=0x{NORMAL_PID:04X} not found via pyusb")

# Search for HID descriptor in firmware to understand report structure
print("\nSearching firmware for HID report descriptor...")
fw = open("C:/Users/<user>/Documents/rk71_mod/rk71_fw.bin", "rb").read()

# HID descriptor items we care about:
# 0x91 = Output item (HID output report)
# 0x81 = Input item
# 0x85 = Report ID
# 0xA1 0x01 = Collection Application
# 0x09 0x61 = Usage 0x61

# Look for 0x91 (output report tag)
print("  HID Output Report (0x91) tags:")
for i in range(0, len(fw)-1):
    if fw[i] == 0x91:
        # 0x91 xx where xx contains size and type info
        # 0x91 0x02 = Data, Variable, Absolute output
        context = fw[max(0,i-16):i+4]
        print(f"    0x{i:04X}: 91 {fw[i+1]:02X} | ctx: {context.hex()}")
        if i > 0x9000:  # Stop after searching relevant area
            break

# Look for A1 01 (Collection Application)
print("  Collection Application (A1 01):")
for i in range(0, min(0x9000, len(fw))-1):
    if fw[i] == 0xA1 and fw[i+1] == 0x01:
        ctx = fw[max(0,i-8):i+16]
        print(f"    0x{i:04X}: {ctx.hex()}")
