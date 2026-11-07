"""
Try every possible HID write method to send the SONiX reboot-to-ISP magic.
Magic: AA 55 A5 5A FF 00 33 CC (discovered from sonixflasher debug trace)
"""
import ctypes, ctypes.wintypes, hid, sys

kernel32 = ctypes.windll.kernel32
kernel32.CreateFileW.restype = ctypes.wintypes.HANDLE
kernel32.CreateFileW.argtypes = [ctypes.wintypes.LPCWSTR, ctypes.wintypes.DWORD,
    ctypes.wintypes.DWORD, ctypes.c_void_p, ctypes.wintypes.DWORD,
    ctypes.wintypes.DWORD, ctypes.wintypes.HANDLE]

GENERIC_RW = 0x80000000 | 0x40000000
GENERIC_R  = 0x80000000
SHARE_RW   = 0x01 | 0x02
OPEN_EX    = 3
INVALID    = ctypes.wintypes.HANDLE(-1).value

hid_dll = ctypes.windll.hid

# The magic reboot-to-ISP bytes (report ID 0x00 + 64 data bytes)
MAGIC = bytes([0x00,  # report ID
               0xAA, 0x55, 0xA5, 0x5A, 0xFF, 0x00, 0x33, 0xCC,
               0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
               0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
               0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
               0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
               0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
               0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
               0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])

def try_send(path, method, buf):
    h = kernel32.CreateFileW(path, GENERIC_RW, SHARE_RW, None, OPEN_EX, 0, None)
    if h == INVALID:
        h = kernel32.CreateFileW(path, GENERIC_R, SHARE_RW, None, OPEN_EX, 0, None)
    if h == INVALID:
        return False, ctypes.GetLastError()

    try:
        ok = False
        err = 0
        if method == 'SetOutputReport':
            cbuf = (ctypes.c_uint8 * len(buf))(*buf)
            ok = bool(hid_dll.HidD_SetOutputReport(h, cbuf, len(buf)))
            err = ctypes.GetLastError()
        elif method == 'SetFeature':
            cbuf = (ctypes.c_uint8 * len(buf))(*buf)
            ok = bool(hid_dll.HidD_SetFeature(h, cbuf, len(buf)))
            err = ctypes.GetLastError()
        elif method == 'WriteFile':
            written = ctypes.wintypes.DWORD(0)
            cbuf = (ctypes.c_uint8 * len(buf))(*buf)
            ok = bool(kernel32.WriteFile(h, cbuf, len(buf), ctypes.byref(written), None))
            err = ctypes.GetLastError()
            if ok: err = written.value
        return ok, err
    finally:
        kernel32.CloseHandle(h)

# Get all VID_05AC PID_024F paths
devs = hid.enumerate()
kb_paths = [d['path'].decode() if isinstance(d['path'], bytes) else d['path']
            for d in devs if d['vendor_id'] == 0x05AC and d['product_id'] == 0x024F]

print(f"Found {len(kb_paths)} VID_05AC/024F HID paths")
print()

success = False
for path in kb_paths:
    for method in ['SetOutputReport', 'SetFeature', 'WriteFile']:
        ok, info = try_send(path, method, MAGIC)
        status = "OK" if ok else f"FAIL err={info}"
        if ok:
            print(f"[SUCCESS] {method} on {path[-50:]}: {status}")
            success = True
        elif info not in (1, 5, 6):  # skip "invalid func", "access denied", "invalid handle"
            print(f"[INTERESTING] {method} on {path[-50:]}: {status}")

if not success:
    print("All writes returned ERROR_INVALID_FUNCTION (1) or similar.")
    print("sonixflasher must be using a different mechanism (direct USB or WinUSB).")
    print()
    print(">>> Use this instead:")
    print("cd C:\\Users\\<user>\\Documents\\rk71_mod\\sonixflasher")
    print(".\\sonixflasher.exe -v 05ac/024f -r sonix -f ..\\qmk_firmware\\.build\\rk_rk71_default.bin")
