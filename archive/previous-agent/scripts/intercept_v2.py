"""
Fast ISP interceptor v2.
1. Waits for VID=0x05AC to disappear (= ISP trigger fired)
2. IMMEDIATELY kills the EXE before it can grab the ISP device
3. Polls hard for VID=0x0C45 ISP and flashes QMK the moment it appears
"""
import hid, time, subprocess, os, sys, signal

NORMAL_VID = 0x05AC
NORMAL_PID = 0x024F
ISP_VID    = 0x0C45
ISP_PIDS   = [0x8006, 0x7040, 0x7900, 0x7010]
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EXE_NAME   = "RK71 RGB Firmware_V1.12_190603.exe"

def kill_exe():
    """Kill the RK71 firmware EXE process."""
    import ctypes
    kernel32 = ctypes.windll.kernel32
    # Use taskkill for certainty
    r1 = subprocess.run(['taskkill', '/F', '/IM', EXE_NAME],
                        capture_output=True, text=True)
    r2 = subprocess.run(['taskkill', '/F', '/IM', EXE_NAME.replace(' ','*')[:20]+'*'],
                        capture_output=True, text=True)
    print("[!] kill result: %s %s" % (r1.returncode, r2.returncode))
    sys.stdout.flush()

def normal_present():
    return bool(hid.enumerate(NORMAL_VID, NORMAL_PID))

def check_isp():
    for d in hid.enumerate():
        if d['vendor_id'] == ISP_VID and d['product_id'] in ISP_PIDS:
            return d['product_id']
    return None

def run_flash():
    print("[*] Flashing QMK...")
    sys.stdout.flush()
    r = subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, 'flash_qmk.py')])
    return r.returncode == 0

print("=== ISP Interceptor v2 ===")
print("Waiting for VID=0x05AC to disappear (EXE trigger)...")
sys.stdout.flush()

# Phase 1: wait for keyboard to disappear
while normal_present():
    time.sleep(0.005)   # 5ms poll

print("[!] VID=0x05AC GONE — killing EXE NOW")
sys.stdout.flush()
kill_exe()

# Phase 2: tight poll for ISP
print("[*] Polling for ISP (VID=0x0C45)...")
sys.stdout.flush()
deadline = time.time() + 15
while time.time() < deadline:
    pid = check_isp()
    if pid:
        print("[+] ISP detected! PID=0x%04X" % pid)
        sys.stdout.flush()
        time.sleep(0.1)
        run_flash()
        sys.exit(0)
    time.sleep(0.005)

print("[FAIL] ISP never appeared within 15s")
print("  Was EXE running when you clicked Flash?")
sys.exit(1)
