"""
Passive ISP monitor — run this ALONGSIDE the EXE, don't kill anything.
Logs when VID_0C45 appears at USB level (usb1, no driver) vs HID level (hidapi).
Run EXE normally: Flash → wait P flash → Fn+P → let EXE complete the flash.
"""
import hid, time, sys, os

USB_AVAILABLE = False
try:
    import usb1
    _DLL_DIR = r"C:\Users\<user>\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\usb1"
    if os.path.isdir(_DLL_DIR):
        os.add_dll_directory(_DLL_DIR)
    USB_AVAILABLE = True
except Exception as e:
    print(f"[!] usb1 not available: {e}")

NORMAL_VID, NORMAL_PID = 0x05AC, 0x024F
ISP_VID = 0x0C45

def stamp(): return f"t+{time.time()-T0:.3f}s"

print("=== Passive ISP Monitor ===")
print("Run EXE normally. This script will NOT kill anything.")
print("It just logs when VID_0C45 appears at USB vs HID level.")
print()
print("Waiting for keyboard to disconnect (Fn+P)...")

T0 = time.time()
kb_gone = False
isp_seen_usb = False
isp_seen_hid = False

ctx = usb1.USBContext() if USB_AVAILABLE else None

try:
    while time.time() - T0 < 120:
        t = time.time() - T0

        # --- HID check ---
        hid_devs = hid.enumerate()
        normal_hid = any(d['vendor_id'] == NORMAL_VID and d['product_id'] == NORMAL_PID for d in hid_devs)
        isp_hid_dev = next((d for d in hid_devs if d['vendor_id'] == ISP_VID), None)

        if not kb_gone and not normal_hid:
            print(f"[{stamp()}] KEYBOARD DISCONNECTED (HID level)")
            kb_gone = True

        if isp_hid_dev and not isp_seen_hid:
            print(f"[{stamp()}] VID_0C45 APPEARED in hid.enumerate()!")
            print(f"  VID=0x{isp_hid_dev['vendor_id']:04X} PID=0x{isp_hid_dev['product_id']:04X}")
            print(f"  Path: {isp_hid_dev.get('path', '?')}")
            print(f"  Product: {isp_hid_dev.get('product_string', '?')}")
            isp_seen_hid = True

        # --- USB level check ---
        if ctx:
            try:
                for dev in ctx.getDeviceList(skip_on_error=True):
                    if dev.getVendorID() == ISP_VID and not isp_seen_usb:
                        print(f"[{stamp()}] VID_0C45 APPEARED at USB level (usb1)!")
                        print(f"  VID=0x{dev.getVendorID():04X} PID=0x{dev.getProductID():04X}")
                        print(f"  devClass=0x{dev.getDeviceClass():02X}")
                        try:
                            for cfg in dev:
                                for iface in cfg:
                                    for s in iface:
                                        eps = [f"EP0x{ep.getAddress():02X}" for ep in s]
                                        print(f"  IF{s.getNumber()} class=0x{s.getClass():02X} EPs={eps}")
                        except Exception as e2:
                            print(f"  (descriptor read error: {e2})")
                        isp_seen_usb = True
            except Exception as e3:
                pass  # ignore transient errors

        # Detect when VID_0C45 disappears (bootloader done)
        if isp_seen_hid and not any(d['vendor_id'] == ISP_VID for d in hid_devs):
            print(f"[{stamp()}] VID_0C45 GONE from hid.enumerate()")
            isp_seen_hid = False
        if ctx and isp_seen_usb:
            try:
                still_there = any(d.getVendorID() == ISP_VID for d in ctx.getDeviceList(skip_on_error=True))
                if not still_there:
                    print(f"[{stamp()}] VID_0C45 GONE from USB level")
                    isp_seen_usb = False
            except:
                pass

        # Normal keyboard came back
        if kb_gone and normal_hid:
            print(f"[{stamp()}] Keyboard reconnected (back to normal)")
            break

        time.sleep(0.002)  # 2ms poll

finally:
    if ctx:
        ctx.close()
    print(f"\nDone at t+{time.time()-T0:.1f}s")
    print(f"USB detection seen: {isp_seen_usb}")
    print(f"HID detection seen: {isp_seen_hid}")
