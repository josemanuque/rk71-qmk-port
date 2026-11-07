"""
Replicate the EXE's exact HID calls via ctypes/Win32 API.
The EXE uses CreateFile + HidD_SetFeature, not hidapi.
We try the vendor UP=0xFFFF interface specifically.
"""
import ctypes, ctypes.wintypes, sys, time, subprocess, os

NORMAL_VID = 0x05AC
NORMAL_PID = 0x024F
ISP_VID    = 0x0C45
ISP_PIDS   = [0x8006, 0x7040, 0x7900, 0x7010]
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

kernel32 = ctypes.windll.kernel32
hid_dll  = ctypes.windll.hid

# Fix 64-bit handle truncation
kernel32.CreateFileW.restype  = ctypes.wintypes.HANDLE
kernel32.CreateFileW.argtypes = [
    ctypes.wintypes.LPCWSTR, ctypes.wintypes.DWORD, ctypes.wintypes.DWORD,
    ctypes.c_void_p, ctypes.wintypes.DWORD, ctypes.wintypes.DWORD, ctypes.wintypes.HANDLE]
kernel32.CloseHandle.argtypes = [ctypes.wintypes.HANDLE]
kernel32.WriteFile.restype  = ctypes.wintypes.BOOL
kernel32.WriteFile.argtypes = [ctypes.wintypes.HANDLE, ctypes.c_void_p,
    ctypes.wintypes.DWORD, ctypes.POINTER(ctypes.wintypes.DWORD), ctypes.c_void_p]
kernel32.ReadFile.restype  = ctypes.wintypes.BOOL
kernel32.ReadFile.argtypes  = [ctypes.wintypes.HANDLE, ctypes.c_void_p,
    ctypes.wintypes.DWORD, ctypes.POINTER(ctypes.wintypes.DWORD), ctypes.c_void_p]
hid_dll.HidD_SetFeature.restype  = ctypes.wintypes.BOOL
hid_dll.HidD_SetFeature.argtypes = [ctypes.wintypes.HANDLE, ctypes.c_void_p, ctypes.wintypes.ULONG]
hid_dll.HidD_GetFeature.restype  = ctypes.wintypes.BOOL
hid_dll.HidD_GetFeature.argtypes = [ctypes.wintypes.HANDLE, ctypes.c_void_p, ctypes.wintypes.ULONG]
hid_dll.HidD_SetOutputReport.restype  = ctypes.wintypes.BOOL
hid_dll.HidD_SetOutputReport.argtypes = [ctypes.wintypes.HANDLE, ctypes.c_void_p, ctypes.wintypes.ULONG]

GENERIC_READ       = 0x80000000
GENERIC_WRITE      = 0x40000000
FILE_SHARE_READ    = 0x1
FILE_SHARE_WRITE   = 0x2
OPEN_EXISTING      = 3
INVALID_HANDLE     = ctypes.wintypes.HANDLE(-1).value

def open_hid(path):
    if isinstance(path, bytes):
        path = path.decode('utf-8')
    h = kernel32.CreateFileW(
        path,
        GENERIC_READ | GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        None, OPEN_EXISTING, 0, None)
    return None if h == INVALID_HANDLE else h

def close_hid(h):
    kernel32.CloseHandle(h)

def set_feature(h, data: bytes) -> bool:
    buf = (ctypes.c_ubyte * len(data))(*data)
    return bool(hid_dll.HidD_SetFeature(h, buf, len(data)))

def set_output_report(h, data: bytes) -> bool:
    buf = (ctypes.c_ubyte * len(data))(*data)
    return bool(hid_dll.HidD_SetOutputReport(h, buf, len(data)))

def write_output(h, data: bytes):
    buf = (ctypes.c_ubyte * len(data))(*data)
    written = ctypes.wintypes.DWORD(0)
    ok = kernel32.WriteFile(h, buf, len(data), ctypes.byref(written), None)
    return bool(ok), written.value

def get_feature(h, rid: int, size: int):
    buf = (ctypes.c_ubyte * size)(rid)
    ok = bool(hid_dll.HidD_GetFeature(h, buf, size))
    return bytes(buf) if ok else None

def check_isp():
    try:
        import hid
        for d in hid.enumerate():
            if d['vendor_id'] == ISP_VID and d['product_id'] in ISP_PIDS:
                return d['product_id']
    except Exception: pass
    return None

def run_flash():
    print("\n[*] Flashing QMK...")
    r = subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, 'flash_qmk.py')])
    return r.returncode == 0

try:
    import hid as hidapi
    all_devs = hidapi.enumerate(NORMAL_VID, NORMAL_PID)
except Exception:
    print("hidapi not available"); sys.exit(1)

print("=== RK71 ISP trigger via ctypes/Win32 ===\n")
print("Interfaces:")
for d in all_devs:
    print(f"  iface={d.get('interface_number',-1)} UP=0x{d.get('usage_page',0):04X}  {d['path']}")

# Find vendor-specific interface (UP=0xFFFF)
vendor_path = None
for d in all_devs:
    if d.get('usage_page') == 0xFFFF:
        vendor_path = d['path']
        print(f"\n[+] Vendor interface (UP=0xFFFF): {vendor_path}")
        break

if not vendor_path:
    print("[!] No UP=0xFFFF interface — trying all interfaces")
    all_paths = [d['path'] for d in all_devs]
else:
    all_paths = [vendor_path] + [d['path'] for d in all_devs if d['path'] != vendor_path]

# --- Build command packets (from EXE decompile) ---
# Unlock: [0x00×12, AA, 55, A5, 5A, FF, 00, 33, 00, 0x00×43] 64 bytes + report_id=0x00
unlock_pkt = bytearray(65)   # [0x00] + 64 bytes
unlock_pkt[0]  = 0x00        # report_id
unlock_pkt[13] = 0xAA; unlock_pkt[14] = 0x55
unlock_pkt[15] = 0xA5; unlock_pkt[16] = 0x5A
unlock_pkt[17] = 0xFF; unlock_pkt[18] = 0x00
unlock_pkt[19] = 0x33; unlock_pkt[20] = 0x00; unlock_pkt[21] = 0x00

# Trigger: [AA, 55, A5, 5A, FF, 00, 33, 81] 8 bytes + report_id=0x00
trigger_pkt = bytearray(9)   # [0x00] + 8 bytes
trigger_pkt[0] = 0x00        # report_id
trigger_pkt[1] = 0xAA; trigger_pkt[2] = 0x55
trigger_pkt[3] = 0xA5; trigger_pkt[4] = 0x5A
trigger_pkt[5] = 0xFF; trigger_pkt[6] = 0x00
trigger_pkt[7] = 0x33; trigger_pkt[8] = 0x81

# Simple probe cmd=01 AA 55
probe_pkt = bytearray(9)
probe_pkt[0] = 0x00
probe_pkt[1] = 0x01; probe_pkt[2] = 0xAA; probe_pkt[3] = 0x55

def try_send(path, pkt, label):
    h = open_hid(path)
    if not h:
        err = kernel32.GetLastError()
        print(f"  {label}: CreateFile FAILED (err={err})")
        return False
    results = []
    # 1. HidD_SetFeature
    ok1 = set_feature(h, bytes(pkt))
    e1 = kernel32.GetLastError() if not ok1 else 0
    results.append(f"SetFeature={'OK' if ok1 else f'FAIL({e1})'}")
    # 2. HidD_SetOutputReport
    ok2 = set_output_report(h, bytes(pkt))
    e2 = kernel32.GetLastError() if not ok2 else 0
    results.append(f"SetOutput={'OK' if ok2 else f'FAIL({e2})'}")
    # 3. WriteFile (interrupt output)
    ok3, nw = write_output(h, bytes(pkt))
    e3 = kernel32.GetLastError() if not ok3 else 0
    results.append(f"WriteFile={'OK '+str(nw)+'B' if ok3 else f'FAIL({e3})'}")
    print(f"  {label}: {' | '.join(results)}")
    if ok1 or ok2 or ok3:
        resp = get_feature(h, 0x00, 65)
        if resp and any(resp):
            print(f"  Response: {resp[:16].hex()}")
    close_hid(h)
    return ok1 or ok2 or ok3

print("\n[*] Trying all interfaces with probe+unlock+trigger:")
for path in all_paths:
    up = next((d.get('usage_page',0) for d in all_devs if d['path']==path), 0)
    iface = next((d.get('interface_number',-1) for d in all_devs if d['path']==path), -1)
    print(f"\nInterface iface={iface} UP=0x{up:04X}:")
    try_send(path, probe_pkt, 'probe')
    time.sleep(0.05)
    try_send(path, unlock_pkt, 'unlock')
    time.sleep(0.05)
    try_send(path, trigger_pkt, 'trigger')
    p = check_isp()
    if p:
        print(f"\n[SUCCESS] ISP 0x{p:04X}!")
        run_flash()
        sys.exit(0)
    time.sleep(0.5)

p = check_isp()
if p:
    print(f"\n[SUCCESS] ISP 0x{p:04X}!")
    run_flash()
else:
    print("\n[FAILED] ISP not triggered")
    print("Exact error codes above tell us why SetFeature failed on each interface.")
