"""Put a keyboard running the STOCK Royal Kludge firmware into the SN32 ROM bootloader (Windows only).

This does what the vendor updater ("HFD ISP Tool", stock/RK71 RGB Firmware_V1.12_190603.exe) does
when you click Start:

  1. find the keyboard's HID interface 0 (05AC:024F, path contains "mi_00")
  2. open it with NO read/write access (Windows keeps keyboards open exclusively; asking for read or
     write access is refused, and that is why earlier attempts "did not work reliably")
  3. HidD_SetFeature with report ID 0 + 64 bytes: AA 42 89 5A FF 71 62 CC, then zeros

The stock firmware (USB EP0 handler @0x18C8 / @0x1818) checks those 8 bytes and jumps straight into the
ROM bootloader at 0x1FFF0301. The keyboard re-enumerates as 0C45:7040 within a second, ready for
`bash tools/flash_rk71.sh <image>.bin` (or `sonixflasher -v 0c45/7040 -f <image>.bin`).

SonixFlasher's `-r hfd` option sends the same packet, so `sonixflasher -v 05ac/024f -r hfd -f <bin>` is
the one-step equivalent.

Usage:  python tools/stock_enter_isp.py [--vid 05ac --pid 024f] [--dry-run]
Only stock firmware understands this. QMK (0C45:8071) uses Fn+Pause instead.
"""

import argparse
import ctypes
import ctypes.wintypes as wt
import sys
import time

MAGIC = bytes([0xAA, 0x42, 0x89, 0x5A, 0xFF, 0x71, 0x62, 0xCC])

setupapi = ctypes.WinDLL("setupapi", use_last_error=True)
hid = ctypes.WinDLL("hid", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)


class GUID(ctypes.Structure):
    _fields_ = [("Data1", wt.DWORD), ("Data2", wt.WORD), ("Data3", wt.WORD), ("Data4", ctypes.c_ubyte * 8)]


class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("InterfaceClassGuid", GUID), ("Flags", wt.DWORD), ("Reserved", ctypes.c_void_p)]


class HIDP_CAPS(ctypes.Structure):
    _fields_ = [
        ("Usage", wt.USHORT), ("UsagePage", wt.USHORT),
        ("InputReportByteLength", wt.USHORT), ("OutputReportByteLength", wt.USHORT),
        ("FeatureReportByteLength", wt.USHORT), ("Reserved", wt.USHORT * 17),
        ("rest", wt.USHORT * 10),
    ]


DIGCF_PRESENT, DIGCF_DEVICEINTERFACE = 0x2, 0x10
FILE_SHARE_READ, FILE_SHARE_WRITE, OPEN_EXISTING = 1, 2, 3
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

setupapi.SetupDiGetClassDevsW.restype = ctypes.c_void_p
setupapi.SetupDiGetClassDevsW.argtypes = [ctypes.POINTER(GUID), wt.LPCWSTR, wt.HWND, wt.DWORD]
setupapi.SetupDiEnumDeviceInterfaces.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(GUID), wt.DWORD,
                                                 ctypes.POINTER(SP_DEVICE_INTERFACE_DATA)]
setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [ctypes.c_void_p, ctypes.POINTER(SP_DEVICE_INTERFACE_DATA),
                                                      ctypes.c_void_p, wt.DWORD, ctypes.POINTER(wt.DWORD), ctypes.c_void_p]
setupapi.SetupDiDestroyDeviceInfoList.argtypes = [ctypes.c_void_p]
kernel32.CreateFileW.restype = ctypes.c_void_p
kernel32.CreateFileW.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD, ctypes.c_void_p, wt.DWORD, wt.DWORD, ctypes.c_void_p]
kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
hid.HidD_GetHidGuid.argtypes = [ctypes.POINTER(GUID)]
hid.HidD_SetFeature.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wt.ULONG]
hid.HidD_GetPreparsedData.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
hid.HidD_FreePreparsedData.argtypes = [ctypes.c_void_p]
hid.HidP_GetCaps.argtypes = [ctypes.c_void_p, ctypes.POINTER(HIDP_CAPS)]


def hid_paths():
    guid = GUID()
    hid.HidD_GetHidGuid(ctypes.byref(guid))
    info = setupapi.SetupDiGetClassDevsW(ctypes.byref(guid), None, None, DIGCF_PRESENT | DIGCF_DEVICEINTERFACE)
    paths = []
    try:
        i = 0
        while True:
            ifd = SP_DEVICE_INTERFACE_DATA()
            ifd.cbSize = ctypes.sizeof(ifd)
            if not setupapi.SetupDiEnumDeviceInterfaces(info, None, ctypes.byref(guid), i, ctypes.byref(ifd)):
                break
            i += 1
            need = wt.DWORD()
            setupapi.SetupDiGetDeviceInterfaceDetailW(info, ctypes.byref(ifd), None, 0, ctypes.byref(need), None)
            buf = ctypes.create_string_buffer(need.value)
            # SP_DEVICE_INTERFACE_DETAIL_DATA_W.cbSize: 8 on 64-bit Python, 6 on 32-bit
            ctypes.c_uint32.from_buffer(buf).value = 8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 6
            if setupapi.SetupDiGetDeviceInterfaceDetailW(info, ctypes.byref(ifd), buf, need, None, None):
                paths.append(ctypes.wstring_at(ctypes.addressof(buf) + 4))
    finally:
        setupapi.SetupDiDestroyDeviceInfoList(info)
    return paths


def feature_length(handle):
    pp = ctypes.c_void_p()
    if not hid.HidD_GetPreparsedData(handle, ctypes.byref(pp)):
        return 0
    try:
        caps = HIDP_CAPS()
        hid.HidP_GetCaps(pp, ctypes.byref(caps))
        return caps.FeatureReportByteLength
    finally:
        hid.HidD_FreePreparsedData(pp)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--vid", default="05ac")
    ap.add_argument("--pid", default="024f")
    ap.add_argument("--dry-run", action="store_true", help="only list the matching interface")
    a = ap.parse_args()

    tag = f"vid_{a.vid.lower()}&pid_{a.pid.lower()}"
    cands = [p for p in hid_paths() if tag in p.lower() and ("mi_00" in p.lower() or "&mi_" not in p.lower())]
    if not cands:
        others = [p for p in hid_paths() if "vid_0c45&pid_8071" in p.lower()]
        print(f"No stock keyboard ({a.vid}:{a.pid}) found." + (" QMK is running: use Fn+Pause." if others else ""))
        return 1
    for path in cands:
        h = kernel32.CreateFileW(path, 0, FILE_SHARE_READ | FILE_SHARE_WRITE, None, OPEN_EXISTING, 0, None)
        if h in (None, INVALID_HANDLE_VALUE):
            print("cannot open", path, "error", ctypes.get_last_error())
            continue
        try:
            n = feature_length(h)
            print(f"{path}\n  feature report length {n} (expected 65 = report ID + 64)")
            if n != 65:
                continue
            if a.dry_run:
                return 0
            buf = (ctypes.c_ubyte * n)(0, *MAGIC)
            ok = hid.HidD_SetFeature(h, buf, n)
            # The firmware jumps to the bootloader at the end of the transfer, so an error here is normal.
            print("  sent ISP command", "(ok)" if ok else f"(error {ctypes.get_last_error()}, usually harmless)")
        finally:
            kernel32.CloseHandle(h)
        for _ in range(50):
            time.sleep(0.1)
            if any("vid_0c45&pid_7040" in p.lower() for p in hid_paths()):
                print("Bootloader 0C45:7040 is up. Flash now: bash tools/flash_rk71.sh <image>.bin")
                return 0
        print("Bootloader did not appear within 5 s.")
        return 2
    print("No interface with a 64-byte feature report found.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
