"""
Bootmagic test: watches for VID_0C45/7040 (ISP mode).
Instructions:
  1. Hold Space + B on the RK71
  2. Unplug the USB cable (keep holding Space+B)
  3. Plug USB back in (keep holding for 2 more seconds)
  4. If bootmagic works, ISP mode (VID_0C45/7040) will appear here
"""
import os, sys, time

LIBUSB_DIR = os.path.join(os.path.dirname(__file__), "sonixflasher")
os.add_dll_directory(LIBUSB_DIR)
import usb1

ISP_VID, ISP_PID = 0x0C45, 0x7040
NORMAL_VID, NORMAL_PID = 0x05AC, 0x024F

print("=== Bootmagic Test ===")
print()
print("Steps:")
print("  1. Hold Space + B on the keyboard")
print("  2. Unplug USB (keep holding)")
print("  3. Plug USB back in (keep holding 2 more seconds)")
print("  4. This script will detect if ISP mode appears")
print()
print("Monitoring USB for 30 seconds...")
print()

ctx = usb1.USBContext()
normal_seen = False
isp_seen    = False
start = time.time()

while time.time() - start < 30:
    devs = {(d.getVendorID(), d.getProductID()) for d in ctx.getDeviceList(skip_on_error=True)}

    if (NORMAL_VID, NORMAL_PID) in devs:
        if not normal_seen:
            print(f"[{time.time()-start:.1f}s] Keyboard in NORMAL mode (VID_{NORMAL_VID:04X}/PID_{NORMAL_PID:04X})")
            normal_seen = True
            isp_seen = False
    else:
        if normal_seen and not isp_seen:
            print(f"[{time.time()-start:.1f}s] Normal keyboard DISCONNECTED")

    if (ISP_VID, ISP_PID) in devs:
        if not isp_seen:
            print(f"[{time.time()-start:.1f}s] *** ISP MODE DETECTED! VID_{ISP_VID:04X}/PID_{ISP_PID:04X} ***")
            print()
            print("BOOTMAGIC WORKS! Space+B triggers ISP mode.")
            print("Future remote reflashing is possible without physical access.")
            isp_seen = True
            normal_seen = False
            ctx.close()
            sys.exit(0)

    time.sleep(0.05)

ctx.close()
print()
if not isp_seen:
    print("ISP mode NOT detected.")
    print()
    print("Either:")
    print("  - Bootmagic key matrix is wrong (Space or B on wrong pins)")
    print("  - Or keyboard didn't unplug/replug during the 30s window")
    print()
    print("Try again, OR try: hold Esc, unplug, plug back in (alternative ISP trigger)")
