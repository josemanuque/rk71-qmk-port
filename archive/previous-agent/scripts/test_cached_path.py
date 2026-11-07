"""
Test: try to open the CACHED HID/USB device paths during the EXE flash.
The EXE likely uses CreateFile with the pre-known path rather than enumeration.
Run this ALONGSIDE the EXE (don't kill it). Logs success/failure of each path.
"""
import ctypes, ctypes.wintypes, hid, time, sys

GENERIC_READ  = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ  = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING    = 3
INVALID_HANDLE   = ctypes.wintypes.HANDLE(-1).value

kernel32 = ctypes.windll.kernel32
kernel32.CreateFileW.restype = ctypes.wintypes.HANDLE
kernel32.CreateFileW.argtypes = [
    ctypes.wintypes.LPCWSTR, ctypes.wintypes.DWORD, ctypes.wintypes.DWORD,
    ctypes.c_void_p, ctypes.wintypes.DWORD, ctypes.wintypes.DWORD,
    ctypes.wintypes.HANDLE,
]

# All known cached paths from the registry (both \\?\ and \\.\, shared and exclusive)
PATHS_TO_TRY = [
    # HID device interface (from HID child InstanceId)
    r"\\?\HID#VID_0C45&PID_7040#6&12c49426&0&0000#{4d1e55b2-f16f-11cf-88cb-001111000030}",
    r"\\.\HID#VID_0C45&PID_7040#6&12c49426&0&0000#{4d1e55b2-f16f-11cf-88cb-001111000030}",
    # Lowercase
    r"\\?\hid#vid_0c45&pid_7040#6&12c49426&0&0000#{4d1e55b2-f16f-11cf-88cb-001111000030}",
    # USB device interface (from USB parent InstanceId SymbolicName)
    r"\\?\USB#VID_0C45&PID_7040#5&1fb2a5ee&0&3#{a5dcbf10-6530-11d2-901f-00c04fb951ed}",
    r"\\.\USB#VID_0C45&PID_7040#5&1fb2a5ee&0&3#{a5dcbf10-6530-11d2-901f-00c04fb951ed}",
]

def try_open(path, shared=True):
    share = (FILE_SHARE_READ | FILE_SHARE_WRITE) if shared else 0
    h = kernel32.CreateFileW(path, GENERIC_READ | GENERIC_WRITE, share, None, OPEN_EXISTING, 0, None)
    err = ctypes.GetLastError()
    if h == INVALID_HANDLE:
        return None, err
    return h, 0

def stamp():
    return f"t+{time.time()-T0:.3f}s"

T0 = time.time()
print("=== Cached Path Tester ===")
print("Run the EXE flash simultaneously. This tries all cached paths every 10ms.\n")
print("Waiting for keyboard to disconnect...")

kb_gone = False
found_path = None

deadline = time.time() + 120
while time.time() < deadline:
    hid_devs = hid.enumerate()
    normal = any(d['vendor_id'] == 0x05AC and d['product_id'] == 0x024F for d in hid_devs)

    if not kb_gone and not normal:
        print(f"[{stamp()}] Keyboard disconnected! Trying all cached paths...")
        kb_gone = True

    if kb_gone:
        for path in PATHS_TO_TRY:
            # Try shared first
            h, err = try_open(path, shared=True)
            if h:
                print(f"[{stamp()}] OPENED (shared): {path}")
                # Try a write immediately
                buf = (ctypes.c_uint8 * 65)(0, 0x05, *([0]*63))  # probe cmd
                written = ctypes.wintypes.DWORD(0)
                ok = kernel32.WriteFile(h, buf, 65, ctypes.byref(written), None)
                werr = ctypes.GetLastError()
                print(f"  WriteFile: ok={ok} written={written.value} err={werr}")
                kernel32.CloseHandle(h)
                found_path = path
                break
            elif err not in (2, 3, 5):  # not "file not found" or "access denied"
                print(f"[{stamp()}] path={path[-40:]} err={err}")

        if found_path:
            break

    if kb_gone and normal:
        print(f"[{stamp()}] Keyboard back to normal. Done.")
        break

    time.sleep(0.010)

if found_path:
    print(f"\n[SUCCESS] Usable path found: {found_path}")
else:
    print("\n[FAIL] No cached path opened during the flash window.")
    print("Next step: try SetupDi with DIGCF_ALL_DEVICES to find registered-but-absent interface.")
