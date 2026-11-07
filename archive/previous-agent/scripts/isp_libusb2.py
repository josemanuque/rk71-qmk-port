#!/usr/bin/env python3
"""
RK71 ISP trigger v2 - uses libusb-package (64-bit) backend.
Tries:
  1. Read feature reports to understand firmware state
  2. Interrupt OUT endpoint via libusb
  3. HID SET_REPORT control transfers
"""
import sys, time, struct

try:
    import hid
except ImportError:
    print("ERROR: hid not found. Install: pip install hidapi")
    sys.exit(1)

try:
    import usb.core, usb.util, usb.backend.libusb1
    HAS_PYUSB = True
except ImportError:
    HAS_PYUSB = False
    print("WARNING: pyusb not found")

try:
    import libusb_package
    HAS_LIBUSB_PKG = True
except ImportError:
    HAS_LIBUSB_PKG = False
    print("WARNING: libusb-package not found")

NORMAL_VID = 0x05AC
NORMAL_PID = 0x024F
ISP_VID    = 0x0C45
ISP_PID    = 0x8006

def check_isp():
    return bool(hid.enumerate(ISP_VID, ISP_PID))

def get_backend():
    if HAS_LIBUSB_PKG:
        try:
            backend = libusb_package.get_libusb1_backend()
            if backend:
                print("[+] Using libusb-package backend")
                return backend
        except Exception as e:
            print("libusb-package failed: %s" % e)
    if HAS_PYUSB:
        try:
            backend = usb.backend.libusb1.get_backend()
            if backend:
                print("[+] Using libusb1 from system")
                return backend
        except Exception as e:
            print("libusb1 failed: %s" % e)
    return None

def build_isp_pkt():
    """64-byte ISP trigger: byte[2]=0xE5, byte[3]=0x30"""
    pkt = bytearray(64)
    pkt[2] = 0xE5
    pkt[3] = 0x30
    return bytes(pkt)

def probe_feature_reports():
    """Read feature reports from all interfaces to understand protocol state."""
    print("\n=== Probing feature reports (read-back) ===")
    devices = hid.enumerate(NORMAL_VID, NORMAL_PID)
    for d in devices:
        iface = d.get('interface_number', -1)
        up = d.get('usage_page', 0)
        for rid in range(0, 5):
            try:
                dev = hid.device()
                dev.open_path(d['path'])
                data = dev.get_feature_report(rid, 65)
                dev.close()
                if data and any(x != 0 for x in data[1:]):
                    print("  Iface %d UP=0x%04X RID=%d: %s" % (
                        iface, up, rid, bytes(data[:16]).hex()))
                elif data:
                    print("  Iface %d UP=0x%04X RID=%d: (all zeros, len=%d)" % (
                        iface, up, rid, len(data)))
            except Exception:
                pass

def try_feature_reports():
    """Send ISP packet as feature report to all interfaces."""
    print("\n=== Trying feature reports ===")
    devices = hid.enumerate(NORMAL_VID, NORMAL_PID)
    isp_pkt = build_isp_pkt()

    for d in devices:
        iface = d.get('interface_number', -1)
        up = d.get('usage_page', 0)
        for rid in range(0, 5):
            pkt = bytes([rid]) + isp_pkt[:63]
            try:
                dev = hid.device()
                dev.open_path(d['path'])
                r = dev.send_feature_report(pkt)
                dev.close()
                if r > 0:
                    print("  Iface %d UP=0x%04X RID=%d: SENT %d bytes!" % (iface, up, rid, r))
            except Exception:
                pass

    time.sleep(0.5)
    if check_isp():
        print("[SUCCESS] ISP mode detected!")
        return True
    return False

def try_libusb_endpoints(dev):
    """List all endpoints and try writing to interrupt OUT ones."""
    print("\n=== USB Endpoint map ===")
    cfg = dev.get_active_configuration()
    out_eps = []
    for intf in cfg:
        num = intf.bInterfaceNumber
        cls = intf.bInterfaceClass
        sub = intf.bInterfaceSubClass
        print("  Interface %d: class=0x%02X sub=0x%02X proto=0x%02X" % (
            num, cls, sub, intf.bInterfaceProtocol))
        for ep in intf:
            dir_str = "IN" if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_IN else "OUT"
            typ = {0:'Ctrl',1:'Iso',2:'Bulk',3:'Intr'}.get(usb.util.endpoint_type(ep.bmAttributes),'?')
            print("    EP 0x%02X (%s %s maxpkt=%d interval=%d)" % (
                ep.bEndpointAddress, dir_str, typ, ep.wMaxPacketSize, ep.bInterval))
            if (dir_str == "OUT" and
                usb.util.endpoint_type(ep.bmAttributes) == usb.util.ENDPOINT_TYPE_INTR):
                out_eps.append((num, ep))

    print("\n=== Writing to interrupt OUT endpoints ===")
    if not out_eps:
        print("  No interrupt OUT endpoints found!")
        return False

    isp_pkt = build_isp_pkt()
    success = False

    for iface_num, ep in out_eps:
        ep_addr = ep.bEndpointAddress
        max_pkt = ep.wMaxPacketSize

        print("  Trying EP 0x%02X on Interface %d (maxpkt=%d)" % (ep_addr, iface_num, max_pkt))
        try:
            if dev.is_kernel_driver_active(iface_num):
                dev.detach_kernel_driver(iface_num)
                print("    Detached kernel driver")
        except Exception as e:
            print("    kernel driver check: %s" % e)

        try:
            usb.util.claim_interface(dev, iface_num)
            print("    Claimed interface %d" % iface_num)

            pkt = isp_pkt[:max_pkt]
            if len(pkt) < max_pkt:
                pkt = pkt + bytes(max_pkt - len(pkt))

            try:
                r = dev.write(ep_addr, pkt, timeout=500)
                print("    Write: %d bytes OK!" % r)
                time.sleep(0.3)
                if check_isp():
                    print("    [SUCCESS] ISP mode triggered!")
                    success = True
            except usb.core.USBError as e:
                print("    Write failed: %s" % e)

            usb.util.release_interface(dev, iface_num)
        except usb.core.USBError as e:
            print("    Could not claim interface: %s" % e)

    return success

def try_ep0_set_report(dev):
    """Try HID SET_REPORT control transfers on EP0."""
    print("\n=== Trying EP0 HID SET_REPORT ===")
    isp_pkt = build_isp_pkt()
    success = False

    for iface_num in range(3):
        for report_type in [2, 3]:  # output=2, feature=3
            for report_id in [0x00, 0x01]:
                wValue = (report_type << 8) | report_id
                try:
                    r = dev.ctrl_transfer(
                        bmRequestType=0x21,  # host->device, class, interface
                        bRequest=0x09,       # SET_REPORT
                        wValue=wValue,
                        wIndex=iface_num,
                        data_or_wLength=isp_pkt,
                        timeout=200)
                    if r > 0:
                        print("  Iface %d type=%d ID=0x%02X: %d bytes sent!" % (
                            iface_num, report_type, report_id, r))
                        time.sleep(0.3)
                        if check_isp():
                            print("  [SUCCESS]")
                            success = True
                            return success
                except Exception:
                    pass

    return success

def main():
    print("=== RK71 ISP trigger v2 (libusb-package) ===\n")

    if check_isp():
        print("[ALREADY IN ISP MODE] VID=0x0C45/PID=0x8006")
        print("Run: python flash_qmk.py")
        return

    devices = hid.enumerate(NORMAL_VID, NORMAL_PID)
    if not devices:
        print("Keyboard not found (VID=0x%04X/PID=0x%04X)" % (NORMAL_VID, NORMAL_PID))
        return

    print("Found %d HID interface(s)" % len(devices))
    for d in devices:
        print("  Interface %d: usage_page=0x%04X usage=0x%04X path=%s" % (
            d.get('interface_number', -1),
            d.get('usage_page', 0),
            d.get('usage', 0),
            d.get('path', b'').decode('ascii', 'ignore')[:50]))

    # Step 1: probe feature reports to understand current state
    probe_feature_reports()

    # Step 2: try feature reports with ISP packet
    if try_feature_reports():
        return

    # Step 3: try via libusb
    if not HAS_PYUSB:
        print("\nERROR: pyusb not installed, skipping libusb path")
    else:
        backend = get_backend()
        if backend is None:
            print("ERROR: No libusb backend available")
        else:
            dev = usb.core.find(idVendor=NORMAL_VID, idProduct=NORMAL_PID, backend=backend)
            if dev is None:
                print("Device not found via libusb")
            else:
                mfr = ""
                prod = ""
                try:
                    mfr = dev.manufacturer
                    prod = dev.product
                except Exception:
                    pass
                print("\nFound via libusb: '%s' '%s'" % (mfr, prod))

                if try_libusb_endpoints(dev):
                    return
                if try_ep0_set_report(dev):
                    return

    print("\n--- RESULT ---")
    if check_isp():
        print("[SUCCESS] Keyboard is in ISP mode!")
        print("Run: python flash_qmk.py")
    else:
        print("ISP not triggered.")
        print()
        print("DIAGNOSIS: If no interrupt OUT endpoint was found, the config channel")
        print("           might use a different mechanism. Check USB descriptor more")
        print("           carefully or try Zadig to install WinUSB on the vendor interface.")

if __name__ == '__main__':
    main()
