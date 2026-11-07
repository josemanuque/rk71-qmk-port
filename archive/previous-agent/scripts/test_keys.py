"""
Listen for key events from the QMK keyboard.
Run this, then press keys on the RK71 to see if any HID reports come through.
"""
import hid, time, sys

devs = hid.enumerate(0x05AC, 0x024F)
keyboard_iface = None
for d in devs:
    if d['interface_number'] == 0:
        keyboard_iface = d
        break

if not keyboard_iface:
    print("Keyboard not found as VID_05AC/024F")
    print("All devices:")
    for d in hid.enumerate():
        print(f"  VID={d['vendor_id']:04X} PID={d['product_id']:04X} iface={d['interface_number']} {d['product_string']!r}")
    sys.exit(1)

print(f"Found keyboard: {keyboard_iface['path']}")
print("Press keys on the RK71 for 15 seconds (Ctrl+C to stop early)...")
print()

try:
    dev = hid.device()
    dev.open_path(keyboard_iface['path'])
    dev.set_nonblocking(True)

    start = time.time()
    report_count = 0
    while time.time() - start < 15:
        data = dev.read(8, timeout_ms=50)
        if data and any(data):
            report_count += 1
            mods = data[0]
            keys = data[2:8]
            active = [f"{k:02X}" for k in keys if k != 0]
            print(f"[{time.time()-start:.1f}s] mods=0x{mods:02X} keys=[{' '.join(active)}]  raw={bytes(data).hex()}")

    dev.close()
    if report_count == 0:
        print("NO key events received. Keys appear non-functional.")
        print()
        print("This could mean:")
        print("  1. Matrix pins are wrong (rows/cols misidentified)")
        print("  2. ROW2COL vs COL2ROW direction is wrong")
        print("  3. The firmware initialized but matrix scan isn't running")
        print()
        print("Try: hold Space+B then plug in USB to test bootmagic (ISP entry)")
    else:
        print(f"\nReceived {report_count} key events - matrix IS working!")
        print("If keys send wrong characters, matrix pin order needs fixing.")
except Exception as e:
    print(f"Error: {e}")
