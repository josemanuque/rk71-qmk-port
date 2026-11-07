#!/usr/bin/env python3
"""
RK71 ISP trigger from EXE decompile.

The EXE sends via HidD_SetFeature (report_id=0x00):
  Cmd1 (unlock): 00 00 00 00 00 00 00 00 00 00 00 00 AA 55 A5 5A FF 00 33 ?? 00 ... (64 bytes)
  Cmd2 (trigger): AA 55 A5 5A FF ?? 33 81 (8 bytes)

The HID wrapper prepends report_id=0x00, so the firmware sees the bytes directly.
"""
import sys, time, subprocess, os

try:
    import hid
except ImportError:
    print("pip install hidapi"); sys.exit(1)

NORMAL_VID = 0x05AC
NORMAL_PID = 0x024F
ISP_VID    = 0x0C45
ISP_PIDS   = [0x8006, 0x7040, 0x7900, 0x7010]
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def check_isp():
    for d in hid.enumerate():
        if d['vendor_id'] == ISP_VID and d['product_id'] in ISP_PIDS:
            return d['product_id']
    return None

def wait_isp(secs=5):
    t = time.time()
    while time.time() - t < secs:
        p = check_isp()
        if p: return p
        time.sleep(0.1)
    return None

def send_feature(pkt, label=''):
    """Send feature report to all RK71 HID interfaces."""
    sent = []
    for d in hid.enumerate(NORMAL_VID, NORMAL_PID):
        iface = d.get('interface_number', -1)
        up = d.get('usage_page', 0)
        for rid in [0x00, 0x01]:
            try:
                dev = hid.device()
                dev.open_path(d['path'])
                # prepend report_id
                buf = bytes([rid]) + pkt[:63]
                r = dev.send_feature_report(buf)
                dev.close()
                if r > 0:
                    sent.append(f"feat iface={iface} UP=0x{up:04X} rid={rid}")
            except Exception: pass
        # Also interrupt write
        try:
            dev = hid.device()
            dev.open_path(d['path'])
            r = dev.write(bytes([0x00]) + pkt[:63])
            dev.close()
            if r > 0:
                sent.append(f"intr iface={iface} UP=0x{up:04X}")
        except Exception: pass
    if sent and label:
        print(f"  [{label}] sent via: {', '.join(sent[:3])}")
    return bool(sent)

def run_flash():
    print("\n[*] Flashing QMK...")
    r = subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, 'flash_qmk.py')])
    return r.returncode == 0

def main():
    print("=== RK71 ISP trigger (from EXE decompile) ===\n")

    if check_isp():
        print("[+] Already in ISP mode!"); run_flash(); return

    if not hid.enumerate(NORMAL_VID, NORMAL_PID):
        print("ERROR: Keyboard not found (VID=0x05AC PID=0x024F)"); sys.exit(1)

    print("Interfaces:")
    for d in hid.enumerate(NORMAL_VID, NORMAL_PID):
        print(f"  iface={d['interface_number']} UP=0x{d.get('usage_page',0):04X}")

    # --- Attempt 1: EXE exact sequence ---
    # Step A: 64-byte "unlock" command (0x33 + 0x00 sub-cmd)
    # Buffer: [0x00×12, AA, 55, A5, 5A, FF, 00, 33, 00, 0x00×44]
    unlock_pkt = bytearray(64)
    unlock_pkt[12] = 0xAA; unlock_pkt[13] = 0x55
    unlock_pkt[14] = 0xA5; unlock_pkt[15] = 0x5A
    unlock_pkt[16] = 0xFF; unlock_pkt[17] = 0x00
    unlock_pkt[18] = 0x33; unlock_pkt[19] = 0x00
    unlock_pkt[20] = 0x00

    # Step B: 8-byte ISP trigger (0x33 + 0x81 sub-cmd)
    trigger_pkt = bytearray(8)
    trigger_pkt[0] = 0xAA; trigger_pkt[1] = 0x55
    trigger_pkt[2] = 0xA5; trigger_pkt[3] = 0x5A
    trigger_pkt[4] = 0xFF; trigger_pkt[5] = 0x00
    trigger_pkt[6] = 0x33; trigger_pkt[7] = 0x81

    print("\n[*] Attempt 1: EXE exact sequence (unlock+trigger)")
    send_feature(bytes(unlock_pkt), "cmd=0x33/0x00 unlock")
    time.sleep(0.1)
    send_feature(bytes(trigger_pkt), "cmd=0x33/0x81 trigger")
    p = wait_isp(5)
    if p: print(f"[SUCCESS] ISP 0x{p:04X}!"); run_flash(); return

    # --- Attempt 2: Vary the bl register byte (5th byte after magic) ---
    print("[*] Attempt 2: Vary bl=0x01..0x0A")
    for bl_val in [0x01, 0x02, 0x03, 0x04, 0x05, 0x0A, 0x0F, 0xFF]:
        t_pkt = bytearray(trigger_pkt)
        t_pkt[5] = bl_val
        u_pkt = bytearray(unlock_pkt)
        u_pkt[19] = bl_val
        send_feature(bytes(u_pkt), f"unlock bl={bl_val:02X}")
        time.sleep(0.05)
        send_feature(bytes(t_pkt), f"trigger bl={bl_val:02X}")
        p = wait_isp(2)
        if p: print(f"[SUCCESS] bl=0x{bl_val:02X} -> ISP 0x{p:04X}!"); run_flash(); return

    # --- Attempt 3: Trigger without unlock, all bl variants ---
    print("[*] Attempt 3: Direct trigger only (no unlock), all bl values")
    for bl_val in range(0x00, 0x20):
        t_pkt = bytearray(trigger_pkt)
        t_pkt[5] = bl_val
        send_feature(bytes(t_pkt), f"direct bl={bl_val:02X}")
        p = wait_isp(1)
        if p: print(f"[SUCCESS] bl=0x{bl_val:02X} -> ISP 0x{p:04X}!"); run_flash(); return

    # --- Attempt 4: Need to precede with standard protocol (cmd 01 AA 55) ---
    print("[*] Attempt 4: Full protocol sequence (cmd=1 probe + cmd=33 trigger)")
    probe = bytearray(8)
    probe[0] = 0x01; probe[1] = 0xAA; probe[2] = 0x55
    send_feature(bytes(probe), "cmd=01 AA 55 probe")
    time.sleep(0.1)
    send_feature(bytes(unlock_pkt), "cmd=0x33/0x00 unlock")
    time.sleep(0.1)
    send_feature(bytes(trigger_pkt), "cmd=0x33/0x81 trigger")
    p = wait_isp(5)
    if p: print(f"[SUCCESS] ISP 0x{p:04X}!"); run_flash(); return

    # --- Attempt 5: Try with 64-byte trigger (not 8-byte) ---
    print("[*] Attempt 5: 64-byte trigger variant")
    big_trigger = bytearray(64)
    big_trigger[0] = 0xAA; big_trigger[1] = 0x55
    big_trigger[2] = 0xA5; big_trigger[3] = 0x5A
    big_trigger[4] = 0xFF; big_trigger[5] = 0x00
    big_trigger[6] = 0x33; big_trigger[7] = 0x81
    send_feature(bytes(big_trigger), "64-byte trigger")
    p = wait_isp(5)
    if p: print(f"[SUCCESS] ISP 0x{p:04X}!"); run_flash(); return

    # --- Attempt 6: pyusb ctrl_transfer with same commands ---
    print("[*] Attempt 6: pyusb ctrl_transfer")
    try:
        import usb.core, usb.util
        backends = []
        try:
            import libusb_package
            b = libusb_package.get_libusb1_backend()
            if b: backends.append(b)
        except Exception: pass
        try:
            import usb.backend.libusb1
            b = usb.backend.libusb1.get_backend()
            if b: backends.append(b)
        except Exception: pass
        for backend in (backends or [None]):
            dev = usb.core.find(idVendor=NORMAL_VID, idProduct=NORMAL_PID, backend=backend)
            if not dev: continue
            print(f"  Found device via pyusb")
            for pkt, lbl in [(bytes(unlock_pkt), 'unlock'), (bytes(trigger_pkt), 'trigger')]:
                for iface in range(4):
                    for rt in [0x02, 0x03]:
                        for rid in [0x00, 0x01]:
                            try:
                                r = dev.ctrl_transfer(0x21, 0x09, (rt<<8)|rid, iface, pkt, 300)
                                if r > 0: print(f"    ctrl {lbl} iface={iface} rt={rt} rid={rid}: {r}B")
                            except Exception: pass
    except Exception as e:
        print(f"  pyusb: {e}")

    p = wait_isp(8)
    if p: print(f"[SUCCESS] ISP 0x{p:04X}!"); run_flash(); return

    print("\n[FAILED] ISP not triggered by software.")
    print("The EXE may require a specific keyboard state or initialization sequence.")
    print("\nOption: Run the official EXE manually and click Flash,")
    print("then immediately run this script with --wait flag:")
    print(f"  python isp_trigger.py --wait")

if __name__ == '__main__':
    if '--wait' in sys.argv:
        print("=== Waiting for ISP mode (plug/replug or run EXE) ===")
        print("Watching for VID=0x0C45...")
        while True:
            p = check_isp()
            if p:
                print(f"[+] ISP detected! PID=0x{p:04X}")
                run_flash()
                break
            time.sleep(0.1)
    else:
        main()
