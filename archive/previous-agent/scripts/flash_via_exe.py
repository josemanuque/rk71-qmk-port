#!/usr/bin/env python3
"""
Flash QMK by hijacking the official RK71 firmware EXE's ISP trigger.

Steps:
  1. Launch RK71 RGB Firmware_V1.12_190603.exe (it triggers ISP without key presses)
  2. The moment ISP mode appears (VID=0x0C45), kill the EXE
  3. Flash QMK firmware via flash_qmk.py

Usage:  python flash_via_exe.py
"""
import sys, os, time, subprocess, hid

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FW_EXE     = os.path.join(SCRIPT_DIR, "RK71 RGB Firmware_V1.12_190603.exe")
FLASH_PY   = os.path.join(SCRIPT_DIR, "flash_qmk.py")

NORMAL_VID = 0x05AC
NORMAL_PID = 0x024F
ISP_VID    = 0x0C45
ISP_PIDS   = [0x8006, 0x7040, 0x7900, 0x7010]

def check_isp():
    for d in hid.enumerate():
        if d['vendor_id'] == ISP_VID and d['product_id'] in ISP_PIDS:
            return d['product_id']
    return None

def check_normal():
    return bool(hid.enumerate(NORMAL_VID, NORMAL_PID))

def main():
    print("=== RK71 QMK auto-flash via firmware EXE ===\n")

    if not os.path.exists(FW_EXE):
        print(f"ERROR: EXE not found: {FW_EXE}")
        sys.exit(1)

    pid = check_isp()
    if pid:
        print(f"[+] Already in ISP mode (PID=0x{pid:04X}), skipping EXE launch")
        print("[*] Flashing QMK...")
        result = subprocess.run([sys.executable, FLASH_PY], cwd=SCRIPT_DIR)
        sys.exit(result.returncode)

    if not check_normal():
        print("ERROR: Keyboard not found in normal mode (VID=0x05AC/PID=0x024F)")
        sys.exit(1)

    print("[+] Keyboard found in normal mode")
    print(f"[*] Launching firmware EXE: {os.path.basename(FW_EXE)}")
    print("    It will trigger ISP mode automatically.")
    print("    We will kill it and flash QMK as soon as ISP appears.\n")

    proc = subprocess.Popen(
        [FW_EXE],
        cwd=SCRIPT_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    print(f"[*] EXE launched (PID {proc.pid}), watching for ISP mode...")

    # Poll tightly for ISP mode
    deadline = time.time() + 30
    isp_pid = None
    while time.time() < deadline:
        isp_pid = check_isp()
        if isp_pid:
            break
        time.sleep(0.1)

    if not isp_pid:
        print("[!] ISP mode not detected within 30s — killing EXE")
        proc.terminate()
        proc.wait(timeout=3)
        print("EXE killed. No ISP mode appeared. Check that the EXE runs correctly.")
        sys.exit(1)

    print(f"[+] ISP mode detected! VID=0x{ISP_VID:04X} PID=0x{isp_pid:04X}")
    print("[*] Killing EXE before it can flash...")
    proc.terminate()
    try:
        proc.wait(timeout=3)
        print("[+] EXE killed")
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        print("[+] EXE force-killed")

    # Brief pause to let the HID handle release
    time.sleep(0.5)

    # Flash QMK
    print("\n[*] Flashing QMK firmware...")
    result = subprocess.run([sys.executable, FLASH_PY], cwd=SCRIPT_DIR)

    if result.returncode == 0:
        print("\n[SUCCESS] QMK flashed!")
        print("Keyboard will restart. Future reflashing: hold Space+B during plug-in.")
    else:
        print("\n[FAILED] Flash failed — see output above")
        sys.exit(1)

if __name__ == '__main__':
    main()
