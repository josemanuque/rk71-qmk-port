#!/usr/bin/env python3
"""
RK71 ISP trigger + auto-flash
Strategy:
  1. Send ISP_FLAG=0xE5 command (pkt[2]=0xE5, pkt[3]=0x30)
  2. Trigger USB device reset so startup code detects ISP_FLAG=0xE5
  3. Wait for ISP VID/PID (0x0C45/0x8006) to appear
  4. Run flash_qmk.py automatically
"""
import sys, time, os, subprocess, struct

try:
    import hid
except ImportError:
    print("ERROR: pip install hidapi"); sys.exit(1)

try:
    import usb.core, usb.util
    HAS_PYUSB = True
except ImportError:
    HAS_PYUSB = False
    print("WARNING: pip install pyusb  (needed for USB reset)")

NORMAL_VID = 0x05AC
NORMAL_PID = 0x024F
ISP_VID    = 0x0C45
ISP_PID    = 0x8006

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FLASH_SCRIPT = os.path.join(SCRIPT_DIR, "flash_qmk.py")

def check_isp():
    return bool(hid.enumerate(ISP_VID, ISP_PID))

def check_normal():
    return bool(hid.enumerate(NORMAL_VID, NORMAL_PID))

def isp_pkt():
    p = bytearray(64)
    p[2] = 0xE5
    p[3] = 0x30
    return bytes(p)

def set_isp_flag():
    """Write ISP_FLAG=0xE5 via all available HID interfaces."""
    print("[*] Writing ISP_FLAG=0xE5 via HID...")
    pkt = isp_pkt()
    sent = False
    for d in hid.enumerate(NORMAL_VID, NORMAL_PID):
        iface = d.get('interface_number', -1)
        up = d.get('usage_page', 0)
        for rid in range(5):
            try:
                dev = hid.device()
                dev.open_path(d['path'])
                r = dev.send_feature_report(bytes([rid]) + pkt[:63])
                dev.close()
                if r > 0:
                    print(f"    Sent to iface {iface} (UP=0x{up:04X}) RID={rid}: {r} bytes")
                    sent = True
            except Exception:
                pass
            # Also try interrupt write
            try:
                dev = hid.device()
                dev.open_path(d['path'])
                r = dev.write(bytes([0x00]) + pkt[:63])
                dev.close()
                if r > 0:
                    print(f"    INT write iface {iface}: {r} bytes")
                    sent = True
            except Exception:
                pass
    return sent

def verify_isp_flag_written():
    """Read back feature report to confirm ISP_FLAG=0xE5 was written."""
    for d in hid.enumerate(NORMAL_VID, NORMAL_PID):
        for rid in range(5):
            try:
                dev = hid.device()
                dev.open_path(d['path'])
                data = dev.get_feature_report(rid, 65)
                dev.close()
                if data and len(data) >= 4 and data[2] == 0xE5:
                    print(f"[+] CONFIRMED: ISP_FLAG=0xE5 visible in readback: {bytes(data[:8]).hex()}")
                    return True
            except Exception:
                pass
    return False

def reset_via_pyusb():
    """Send USB bus reset to force MCU re-init (preserves RAM on SN32F240B)."""
    if not HAS_PYUSB:
        print("[!] pyusb not available, skipping USB reset")
        return False

    # Try with libusb-package first
    backends = []
    try:
        import libusb_package
        b = libusb_package.get_libusb1_backend()
        if b: backends.append(b)
    except Exception:
        pass
    try:
        import usb.backend.libusb1
        b = usb.backend.libusb1.get_backend()
        if b: backends.append(b)
    except Exception:
        pass

    for backend in backends:
        try:
            dev = usb.core.find(idVendor=NORMAL_VID, idProduct=NORMAL_PID, backend=backend)
            if dev:
                print("[*] Sending USB bus reset via libusb...")
                dev.reset()
                print("[+] USB reset sent")
                return True
        except Exception as e:
            print(f"    USB reset failed: {e}")

    print("[!] Could not send USB reset")
    return False

def reset_via_winusb_control():
    """Try sending a 'soft reset' control transfer that the firmware might handle."""
    if not HAS_PYUSB:
        return False

    backends = []
    try:
        import libusb_package
        b = libusb_package.get_libusb1_backend()
        if b: backends.append(b)
    except Exception:
        pass
    try:
        import usb.backend.libusb1
        b = usb.backend.libusb1.get_backend()
        if b: backends.append(b)
    except Exception:
        pass

    for backend in backends:
        try:
            dev = usb.core.find(idVendor=NORMAL_VID, idProduct=NORMAL_PID, backend=backend)
            if not dev: continue

            pkt = isp_pkt()
            # Try various SET_REPORT combinations on all interfaces
            for iface in range(4):
                for rt in [2, 3]:  # output=2, feature=3
                    for rid in [0x00, 0x01, 0x02]:
                        try:
                            r = dev.ctrl_transfer(
                                bmRequestType=0x21, bRequest=0x09,
                                wValue=(rt << 8) | rid, wIndex=iface,
                                data_or_wLength=pkt, timeout=200)
                            if r > 0:
                                print(f"    ctrl_transfer iface={iface} rt={rt} rid=0x{rid:02X}: {r}B")
                        except Exception:
                            pass
        except Exception:
            pass
    return False

def reset_via_devcon():
    """Use devcon/pnputil to reset the USB device (Windows)."""
    print("[*] Trying Windows PnP device restart...")
    # Find device instance ID
    try:
        result = subprocess.run(
            ['powershell', '-NonInteractive', '-Command',
             f'Get-PnpDevice | Where-Object {{$_.HardwareID -like "*VID_05AC&PID_024F*"}} | Select-Object -ExpandProperty InstanceId'],
            capture_output=True, text=True, timeout=10)
        ids = [l.strip() for l in result.stdout.strip().splitlines() if l.strip()]
        if not ids:
            print("    No device found via PnP")
            return False

        for inst_id in ids:
            print(f"    Restarting: {inst_id}")
            subprocess.run(
                ['powershell', '-NonInteractive', '-Command',
                 f'Restart-PnpDevice -InstanceId "{inst_id}" -Confirm:$false'],
                capture_output=True, text=True, timeout=15)
        return True
    except Exception as e:
        print(f"    devcon failed: {e}")
        return False

def wait_for_isp(timeout=15):
    """Poll for ISP mode VID/PID."""
    print(f"[*] Waiting up to {timeout}s for ISP mode (0x{ISP_VID:04X}:0x{ISP_PID:04X})...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        if check_isp():
            return True
        time.sleep(0.3)
    return False

def run_flash():
    """Run flash_qmk.py."""
    if not os.path.exists(FLASH_SCRIPT):
        print(f"ERROR: {FLASH_SCRIPT} not found")
        return False
    print(f"\n[*] Running flash_qmk.py...")
    result = subprocess.run([sys.executable, FLASH_SCRIPT], cwd=SCRIPT_DIR)
    return result.returncode == 0

def wait_for_isp_long(timeout=120):
    """Wait up to N seconds for ISP mode, showing countdown."""
    print(f"Waiting up to {timeout}s for ISP mode (0x{ISP_VID:04X}:0x{ISP_PID:04X}) ...")
    print(">>> REPLUG KEYBOARD NOW while holding the ISP key combo <<<")
    deadline = time.time() + timeout
    last_print = time.time()
    while time.time() < deadline:
        if check_isp():
            return True
        if time.time() - last_print > 5:
            remaining = int(deadline - time.time())
            print(f"  ... waiting {remaining}s ...")
            last_print = time.time()
        time.sleep(0.2)
    return False

def main():
    print("=== RK71 ISP trigger + auto-flash ===\n")

    if check_isp():
        print("[+] Already in ISP mode!")
        run_flash()
        return

    # --wait mode: just watch for ISP and flash when found
    if "--wait" in sys.argv:
        print("WAIT MODE: polling for ISP mode (0x0C45:0x8006)")
        print("Replug keyboard while holding ISP key combo (try Esc, Space, or FN+Esc)")
        print("Ctrl+C to cancel\n")
        try:
            while True:
                if check_isp():
                    print("\n[SUCCESS] ISP mode detected!")
                    run_flash()
                    return
                time.sleep(0.3)
        except KeyboardInterrupt:
            print("\nCancelled.")
        return

    if not check_normal():
        print("ERROR: Keyboard not found (VID=0x05AC/PID=0x024F)")
        return

    print("[+] Keyboard found in normal mode")
    for d in hid.enumerate(NORMAL_VID, NORMAL_PID):
        print(f"    Interface {d.get('interface_number')} UP=0x{d.get('usage_page',0):04X}")

    # Software attempts (may not work due to firmware security)
    print("\n--- Software ISP trigger attempts ---")
    print("NOTE: Firmware security blocks USB-only ISP trigger.")
    print("      These attempts run but physical replug may still be needed.\n")

    set_isp_flag()
    time.sleep(0.2)
    verify_isp_flag_written()
    reset_via_pyusb()
    if wait_for_isp(5):
        print("[SUCCESS] ISP mode!"); run_flash(); return

    if check_normal():
        set_isp_flag()
        reset_via_winusb_control()
        time.sleep(0.2)
        reset_via_devcon()
    if wait_for_isp(10):
        print("[SUCCESS] ISP mode!"); run_flash(); return

    # Physical replug prompt
    print("\n--- Physical replug required ---")
    print("Software trigger failed. Physical access needed.")
    print("To flash:")
    print("  1. Unplug the keyboard")
    print("  2. Hold Esc (or Spacebar, or FN+Esc) while plugging back in")
    print("  3. This script will auto-detect ISP mode and flash QMK\n")
    if wait_for_isp_long(120):
        print("[SUCCESS] ISP mode detected!")
        run_flash()
    else:
        print("\n[TIMEOUT] ISP mode not detected in 2 minutes.")
        print("Run: python trigger_and_flash.py --wait")
        print("     then replug keyboard while holding the ISP key combo")

if __name__ == '__main__':
    main()
