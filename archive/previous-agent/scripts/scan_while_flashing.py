"""Run while P key is flashing to capture exact USB/HID state."""
import hid, time, sys

NORMAL_VID = 0x05AC
NORMAL_PID = 0x024F
ISP_VID    = 0x0C45

print("Scanning every 200ms. Click Flash in EXE then wait...")
seen = set()
t0 = time.time()
while time.time() - t0 < 60:
    for d in hid.enumerate():
        key = (d['vendor_id'], d['product_id'], d.get('interface_number'), d.get('usage_page'))
        if key not in seen:
            seen.add(key)
            vid, pid = d['vendor_id'], d['product_id']
            iface = d.get('interface_number', -1)
            up    = d.get('usage_page', 0)
            name  = d.get('product_string', '')
            print(f"[+] NEW: VID={vid:04X} PID={pid:04X} iface={iface} UP=0x{up:04X} '{name}'")
            if vid == ISP_VID:
                print("    ^^^ ISP MODE DETECTED!")
                sys.stdout.flush()
    time.sleep(0.05)
