#!/usr/bin/env python3
"""
RK71 ISP trigger via raw USB endpoint access.
Uses libusb/pyusb to bypass Windows HID stack and write directly
to the keyboard's USB interrupt OUT endpoint.

Based on firmware RE: packet[2]=0xE5, packet[3]=0x30 triggers ISP.
"""
import sys
import os
import time
import ctypes

# Add current dir to PATH so libusb-1.0.dll is found
os.environ['PATH'] = os.path.dirname(os.path.abspath(__file__)) + os.pathsep + os.environ.get('PATH','')
# Also set the DLL search path explicitly for pyusb
dll_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'libusb-1.0.dll')

try:
    import usb.core
    import usb.util
    import usb.backend.libusb1
    HAS_USB = True
except ImportError:
    HAS_USB = False
    print("ERROR: pyusb not found. Install with: pip install pyusb")
    sys.exit(1)

try:
    import hid
    HAS_HID = True
except ImportError:
    HAS_HID = False

NORMAL_VID = 0x05AC
NORMAL_PID = 0x024F
ISP_VID    = 0x0C45
ISP_PID    = 0x8006

def get_backend():
    """Try to get libusb backend."""
    # Try with explicit DLL path
    if os.path.exists(dll_path):
        try:
            backend = usb.backend.libusb1.get_backend(find_library=lambda x: dll_path)
            if backend:
                print(f"Using libusb-1.0.dll from: {dll_path}")
                return backend
        except Exception as e:
            print(f"libusb1 with explicit path failed: {e}")

    # Try default
    try:
        backend = usb.backend.libusb1.get_backend()
        if backend:
            print("Using libusb1 from system")
            return backend
    except Exception as e:
        print(f"libusb1 default failed: {e}")

    # Try libusb0 (libusb-win32)
    try:
        import usb.backend.libusb0
        backend = usb.backend.libusb0.get_backend()
        if backend:
            print("Using libusb0 (libusb-win32)")
            return backend
    except Exception as e:
        print(f"libusb0 failed: {e}")

    return None

def check_isp():
    if HAS_HID:
        return bool(hid.enumerate(ISP_VID, ISP_PID))
    return False

def build_isp_pkt():
    """64-byte ISP trigger packet: byte[2]=0xE5, byte[3]=0x30"""
    pkt = bytearray(64)
    pkt[2] = 0xE5
    pkt[3] = 0x30
    return bytes(pkt)

def main():
    print("=== RK71 ISP via raw USB ===\n")

    if check_isp():
        print("Already in ISP mode! Run flash_qmk.py")
        return

    backend = get_backend()
    if not backend:
        print("ERROR: No libusb backend available.")
        print("The libusb-1.0.dll was copied but couldn't load.")
        print("\nTrying ctypes fallback to load DLL...")
        try:
            ctypes.cdll.LoadLibrary(dll_path)
            print("DLL loaded via ctypes, retrying backend...")
            backend = usb.backend.libusb1.get_backend(find_library=lambda x: dll_path)
        except Exception as e:
            print(f"ctypes load failed: {e}")

        if not backend:
            print("\nFallback: trying HID control transfers instead")
            try_hid_control_transfers()
            return

    # Find the keyboard via libusb
    dev = usb.core.find(idVendor=NORMAL_VID, idProduct=NORMAL_PID, backend=backend)
    if dev is None:
        print(f"Device VID=0x{NORMAL_VID:04X}/PID=0x{NORMAL_PID:04X} not found via libusb")
        return

    print(f"Found keyboard via libusb: {dev.manufacturer} {dev.product}")
    print()

    # List all endpoints
    print("USB Configuration:")
    cfg = dev.get_active_configuration()
    for intf in cfg:
        print(f"  Interface {intf.bInterfaceNumber} alt={intf.bAlternateSetting}: "
              f"class=0x{intf.bInterfaceClass:02X} subclass=0x{intf.bInterfaceSubClass:02X}")
        for ep in intf:
            direction = "IN" if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_IN else "OUT"
            eptype = {0:'Control',1:'Isochronous',2:'Bulk',3:'Interrupt'}.get(usb.util.endpoint_type(ep.bmAttributes),'?')
            print(f"    EP 0x{ep.bEndpointAddress:02X} ({direction}, {eptype}, maxpkt={ep.wMaxPacketSize})")
    print()

    isp_pkt = build_isp_pkt()
    print(f"ISP packet: {isp_pkt[:8].hex()}...")
    print()

    # Strategy 1: Try HID SET_REPORT control transfer to EP0
    print("Strategy 1: HID SET_REPORT via control EP0...")
    for iface_num in [0, 1]:
        for report_type in [2, 3]:  # output=2, feature=3
            for report_id in [0x00, 0x01]:
                try:
                    wValue = (report_type << 8) | report_id
                    r = dev.ctrl_transfer(
                        bmRequestType=0x21,  # host->device, class, interface
                        bRequest=0x09,        # SET_REPORT
                        wValue=wValue,
                        wIndex=iface_num,
                        data_or_wLength=isp_pkt,
                        timeout=200
                    )
                    print(f"  ctrl_transfer iface={iface_num} type={report_type} ID=0x{report_id:02X}: {r} bytes SENT!")
                    time.sleep(0.5)
                    if check_isp():
                        print("SUCCESS! ISP mode triggered!")
                        return
                except usb.core.USBError as e:
                    if 'timeout' not in str(e).lower():
                        pass  # Expected failures are ok

    # Strategy 2: Write to interrupt OUT endpoints directly
    print("Strategy 2: Write to interrupt OUT endpoints...")
    cfg = dev.get_active_configuration()
    for intf in cfg:
        iface_num = intf.bInterfaceNumber

        # Find interrupt OUT endpoints
        out_eps = [ep for ep in intf
                   if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_OUT
                   and usb.util.endpoint_type(ep.bmAttributes) == usb.util.ENDPOINT_TYPE_INTR]

        if not out_eps:
            continue

        print(f"  Interface {iface_num} has {len(out_eps)} interrupt OUT endpoint(s)")

        # Need to claim interface (may fail if OS has it)
        try:
            if dev.is_kernel_driver_active(iface_num):
                dev.detach_kernel_driver(iface_num)
                print(f"  Detached kernel driver from interface {iface_num}")
        except Exception as e:
            print(f"  Note: {e}")

        try:
            usb.util.claim_interface(dev, iface_num)
            print(f"  Claimed interface {iface_num}")

            for ep in out_eps:
                ep_addr = ep.bEndpointAddress
                max_pkt = ep.wMaxPacketSize
                print(f"  Writing to EP 0x{ep_addr:02X} (maxpkt={max_pkt})...")

                # Send ISP packet, truncated to max packet size
                pkt = isp_pkt[:max_pkt]
                if len(pkt) < max_pkt:
                    pkt = pkt + bytes(max_pkt - len(pkt))

                try:
                    r = dev.write(ep_addr, pkt, timeout=500)
                    print(f"    Wrote {r} bytes OK!")
                    time.sleep(0.5)
                    if check_isp():
                        print("SUCCESS! ISP mode triggered!")
                        usb.util.release_interface(dev, iface_num)
                        return
                except usb.core.USBError as e:
                    print(f"    Write failed: {e}")

            usb.util.release_interface(dev, iface_num)
        except usb.core.USBError as e:
            print(f"  Could not claim interface {iface_num}: {e}")

    # Strategy 3: Try USB vendor-specific control requests
    print("Strategy 3: Vendor control transfers (bRequest=0x01-0x0F)...")
    for breq in [0x01, 0x02, 0x03, 0x05, 0x06, 0x07, 0x09, 0x0A]:
        for iface in [0, 1]:
            try:
                r = dev.ctrl_transfer(
                    bmRequestType=0x41,  # host->device, vendor, interface
                    bRequest=breq,
                    wValue=0x0000,
                    wIndex=iface,
                    data_or_wLength=isp_pkt[:8],
                    timeout=100
                )
                print(f"  Vendor req 0x{breq:02X} to iface {iface}: {r} bytes sent!")
                time.sleep(0.3)
                if check_isp():
                    print("SUCCESS!")
                    return
            except usb.core.USBError:
                pass

    print()
    if check_isp():
        print("SUCCESS! Keyboard is in ISP mode.")
        print("Run: python flash_qmk.py")
    else:
        print("ISP mode not triggered.")
        print()
        print("The keyboard does not appear to have an accessible interrupt OUT endpoint.")
        print("The config channel is likely via a USB endpoint that Windows HID claims exclusively.")
        print()
        print("NEXT STEP: Use Zadig (https://zadig.akeo.ie) to:")
        print("  1. Select the vendor interface (Interface 1 'Col05')")
        print("  2. Install WinUSB driver for that interface")
        print("  3. Then re-run this script")

def try_hid_control_transfers():
    """Fallback: use HID library control transfers."""
    if not HAS_HID:
        print("HID library not available")
        return

    devices = hid.enumerate(NORMAL_VID, NORMAL_PID)
    isp_pkt = build_isp_pkt()

    print("Trying HID send_feature_report with various sizes...")
    for d in devices:
        iface = d.get('interface_number')
        up = d.get('usage_page', 0)

        # Only try vendor interface and consumer interface
        if up not in (0xFFFF, 0x000C, 0x0001):
            continue

        for report_id in range(0, 10):
            pkt = bytes([report_id]) + isp_pkt[:63]
            try:
                dev = hid.device()
                dev.open_path(d['path'])
                r = dev.send_feature_report(pkt)
                dev.close()
                if r > 0:
                    print(f"  IFACE {iface} UP=0x{up:04X} RID={report_id}: feature_report OK! ({r})")
                    if check_isp():
                        print("SUCCESS!")
                        return
            except Exception:
                pass

if __name__ == '__main__':
    main()
