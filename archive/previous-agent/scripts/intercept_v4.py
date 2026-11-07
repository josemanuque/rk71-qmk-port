"""
ISP Interceptor v4.
Key insight: DON'T kill the EXE until VID_0C45 appears in hidapi.
Previous attempts killed the EXE immediately after VID_05AC disappeared, but
VID_0C45 wasn't accessible yet (HidUsb hadn't loaded).

Correct sequence:
  1. Wait for VID_05AC to disappear (ISP triggered)
  2. Wait for VID_0C45 to appear in hid.enumerate() — this proves HidUsb is loaded
  3. THEN kill the EXE (releases exclusive handle)
  4. Immediately open and flash QMK (< 200ms after kill)
"""
import hid, time, subprocess, os, sys, ctypes, ctypes.wintypes

WORKDIR   = r"C:\Users\<user>\Documents\rk71_mod"
EXE_NAME  = "RK71 RGB Firmware_V1.12_190603.exe"
FLASH_PY  = os.path.join(WORKDIR, "flash_qmk.py")

NORMAL_VID, NORMAL_PID = 0x05AC, 0x024F
ISP_CANDIDATES = [(0x0C45, 0x8006), (0x0C45, 0x7040), (0x0C45, 0x7900), (0x0C45, 0x7010)]

# Known HID device path from registry ghost entry (port 0&3, ParentIdPrefix=6&12c49426&0)
# Used as a fast-path fallback if hid.enumerate() is slow
KNOWN_HID_PATH = (
    r"\\.\HID#VID_0C45&PID_7040#6&12c49426&0&0000"
    r"#{4d1e55b2-f16f-11cf-88cb-001111000030}"
)

kernel32 = ctypes.windll.kernel32
kernel32.CreateFileW.restype  = ctypes.wintypes.HANDLE
kernel32.CreateFileW.argtypes = [
    ctypes.wintypes.LPCWSTR, ctypes.wintypes.DWORD, ctypes.wintypes.DWORD,
    ctypes.c_void_p, ctypes.wintypes.DWORD, ctypes.wintypes.DWORD,
    ctypes.wintypes.HANDLE,
]
GENERIC_READ  = 0x80000000
GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3
INVALID_HANDLE = ctypes.wintypes.HANDLE(-1).value

def kill_exe():
    r = subprocess.run(['taskkill', '/F', '/IM', EXE_NAME], capture_output=True)
    print(f"[!] Kill EXE: exit={r.returncode}")

def normal_present():
    return bool(hid.enumerate(NORMAL_VID, NORMAL_PID))

def isp_in_hidapi():
    for d in hid.enumerate():
        for vid, pid in ISP_CANDIDATES:
            if d['vendor_id'] == vid and d['product_id'] == pid:
                return d['path'], vid, pid
    return None, None, None

def try_known_path():
    h = kernel32.CreateFileW(
        KNOWN_HID_PATH,
        GENERIC_READ | GENERIC_WRITE,
        0,          # exclusive
        None, OPEN_EXISTING, 0, None
    )
    if h == INVALID_HANDLE:
        return False
    kernel32.CloseHandle(h)
    return True

print("=== ISP Interceptor v4 ===")
print("Open EXE, click Flash, wait for P-flash, press Fn+P ...")

# ── Phase 1: wait for normal keyboard to disappear ───────────────────────────
print("\n[Phase 1] Waiting for VID_05AC to disappear (Fn+P confirmation)...")
deadline1 = time.time() + 180
while time.time() < deadline1:
    if not normal_present():
        print(f"[+] Keyboard disconnected at t={time.time():.2f}")
        break
    time.sleep(0.005)
else:
    print("[FAIL] 3-minute timeout: keyboard never disconnected.")
    sys.exit(1)

t_disconnect = time.time()

# ── Phase 2: wait for VID_0C45 in hid.enumerate (DON'T kill EXE yet) ────────
print("\n[Phase 2] Waiting for VID_0C45 in hid.enumerate (HidUsb must load first)...")
print("        EXE is still running; we wait to confirm access before killing it.")
deadline2 = time.time() + 20
found_path = None
found_via  = None

while time.time() < deadline2:
    path, vid, pid = isp_in_hidapi()
    if path:
        found_path = path
        found_via  = f"hidapi VID=0x{vid:04X} PID=0x{pid:04X}"
        break

    # Also try the known direct path as a fast fallback
    if try_known_path():
        found_path = KNOWN_HID_PATH
        found_via  = "known_path direct open"
        break

    time.sleep(0.005)

if not found_path:
    print(f"[FAIL] ISP not found in hidapi/direct within 20s.")
    print("  Possible causes:")
    print("  - HidUsb never loaded (device at different port than ghost entry)")
    print("  - EXE flashed so fast ISP window closed")
    sys.exit(1)

t_found = time.time()
print(f"[+] ISP accessible via {found_via}  (at t+{t_found-t_disconnect:.2f}s after disconnect)")

# ── Phase 3: kill EXE, flash immediately ─────────────────────────────────────
print("\n[Phase 3] Killing EXE and flashing QMK immediately...")
kill_exe()
time.sleep(0.08)   # 80ms for handle release — keep short!

r = subprocess.run([sys.executable, FLASH_PY], cwd=WORKDIR)
if r.returncode == 0:
    print("\n[SUCCESS] QMK flashed!")
else:
    print(f"\n[FAIL] flash_qmk.py exited with code {r.returncode}")
sys.exit(r.returncode)
