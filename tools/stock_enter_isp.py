"""Put a keyboard running the STOCK Royal Kludge firmware into the SN32 ROM bootloader.

Windows: no dependencies. Linux / macOS: `pip install hidapi`. Linux also needs
tools/udev/50-rk71.rules (or sudo). macOS may ask for Input Monitoring permission.

This does what the vendor updater ("HFD ISP Tool", RK71 RGB Firmware_V1.12_190603.exe) does
when you click Start:

  1. find the keyboard's HID interface 0 (05AC:024F, interface 0, which has the 64-byte feature report)
  2. open it. On Windows the device must be opened with NO read/write access: Windows keeps keyboards
     open exclusively, and asking for read or write access is refused. That is why earlier attempts
     "did not work reliably".
  3. send a feature report with report ID 0 + 64 bytes: AA 42 89 5A FF 71 62 CC, then zeros

The stock firmware (USB EP0 handler @0x18C8 / @0x1818) checks those 8 bytes and jumps straight into the
ROM bootloader at 0x1FFF0301. The keyboard re-enumerates as 0C45:7040 within a second, ready for
`bash tools/flash_rk71.sh <image>.bin`.

SonixFlasher's `-r hfd` option sends the same packet, so `sonixflasher -v 05ac/024f -r hfd -f <bin>` is
the one-step equivalent.

Usage:  python3 tools/stock_enter_isp.py [--vid 05ac --pid 024f] [--dry-run]
Only stock firmware understands this, and only over the USB cable (not Bluetooth).
QMK (0C45:8071) uses Fn+Pause instead.
"""

import argparse
import sys
import time

MAGIC = bytes([0xAA, 0x42, 0x89, 0x5A, 0xFF, 0x71, 0x62, 0xCC])
REPORT_LEN = 65  # report ID 0 + 64 data bytes
BOOTLOADER = (0x0C45, 0x7040)
QMK = (0x0C45, 0x8071)


# ---- Windows: SetupAPI + HID.DLL via ctypes (no dependencies) -----------------------------------
class WindowsBackend:
    def __init__(self):
        import ctypes
        import ctypes.wintypes as wt

        self.ctypes, self.wt = ctypes, wt

        class GUID(ctypes.Structure):
            _fields_ = [("Data1", wt.DWORD), ("Data2", wt.WORD), ("Data3", wt.WORD), ("Data4", ctypes.c_ubyte * 8)]

        class IFDATA(ctypes.Structure):  # SP_DEVICE_INTERFACE_DATA
            _fields_ = [("cbSize", wt.DWORD), ("Guid", GUID), ("Flags", wt.DWORD), ("Reserved", ctypes.c_void_p)]

        class CAPS(ctypes.Structure):  # HIDP_CAPS
            _fields_ = [("Usage", wt.USHORT), ("UsagePage", wt.USHORT), ("In", wt.USHORT), ("Out", wt.USHORT),
                        ("Feature", wt.USHORT), ("Reserved", wt.USHORT * 17), ("Counts", wt.USHORT * 10)]

        self.GUID, self.IFDATA, self.CAPS = GUID, IFDATA, CAPS
        sa = self.setupapi = ctypes.WinDLL("setupapi", use_last_error=True)
        hd = self.hid = ctypes.WinDLL("hid", use_last_error=True)
        k = self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        vp = ctypes.c_void_p
        sa.SetupDiGetClassDevsW.restype = vp
        sa.SetupDiGetClassDevsW.argtypes = [ctypes.POINTER(GUID), wt.LPCWSTR, wt.HWND, wt.DWORD]
        sa.SetupDiEnumDeviceInterfaces.argtypes = [vp, vp, ctypes.POINTER(GUID), wt.DWORD, ctypes.POINTER(IFDATA)]
        sa.SetupDiGetDeviceInterfaceDetailW.argtypes = [vp, ctypes.POINTER(IFDATA), vp, wt.DWORD,
                                                        ctypes.POINTER(wt.DWORD), vp]
        sa.SetupDiDestroyDeviceInfoList.argtypes = [vp]
        k.CreateFileW.restype = vp
        k.CreateFileW.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD, vp, wt.DWORD, wt.DWORD, vp]
        k.CloseHandle.argtypes = [vp]
        hd.HidD_GetHidGuid.argtypes = [ctypes.POINTER(GUID)]
        hd.HidD_SetFeature.argtypes = [vp, vp, wt.ULONG]
        hd.HidD_GetPreparsedData.argtypes = [vp, ctypes.POINTER(vp)]
        hd.HidD_FreePreparsedData.argtypes = [vp]
        hd.HidP_GetCaps.argtypes = [vp, ctypes.POINTER(CAPS)]

    def _paths(self):
        c, wt = self.ctypes, self.wt
        guid = self.GUID()
        self.hid.HidD_GetHidGuid(c.byref(guid))
        info = self.setupapi.SetupDiGetClassDevsW(c.byref(guid), None, None, 0x2 | 0x10)  # PRESENT | INTERFACE
        paths = []
        try:
            i = 0
            while True:
                ifd = self.IFDATA()
                ifd.cbSize = c.sizeof(ifd)
                if not self.setupapi.SetupDiEnumDeviceInterfaces(info, None, c.byref(guid), i, c.byref(ifd)):
                    break
                i += 1
                need = wt.DWORD()
                self.setupapi.SetupDiGetDeviceInterfaceDetailW(info, c.byref(ifd), None, 0, c.byref(need), None)
                buf = c.create_string_buffer(need.value)
                # SP_DEVICE_INTERFACE_DETAIL_DATA_W.cbSize: 8 on 64-bit Python, 6 on 32-bit
                c.c_uint32.from_buffer(buf).value = 8 if c.sizeof(c.c_void_p) == 8 else 6
                if self.setupapi.SetupDiGetDeviceInterfaceDetailW(info, c.byref(ifd), buf, need, None, None):
                    paths.append(c.wstring_at(c.addressof(buf) + 4))
        finally:
            self.setupapi.SetupDiDestroyDeviceInfoList(info)
        return paths

    def present(self, vid, pid):
        tag = f"vid_{vid:04x}&pid_{pid:04x}"
        return any(tag in p.lower() for p in self._paths())

    def send(self, vid, pid, data, dry_run):
        c = self.ctypes
        tag = f"vid_{vid:04x}&pid_{pid:04x}"  # USB only: Bluetooth paths look like "_vid&0002…"
        found = False
        for path in self._paths():
            low = path.lower()
            if tag not in low or ("&mi_" in low and "mi_00" not in low):
                continue
            h = self.kernel32.CreateFileW(path, 0, 1 | 2, None, 3, 0, None)  # no access, share r/w, existing
            if h in (None, c.c_void_p(-1).value):
                continue
            try:
                pp = c.c_void_p()
                caps = self.CAPS()
                if self.hid.HidD_GetPreparsedData(h, c.byref(pp)):
                    self.hid.HidP_GetCaps(pp, c.byref(caps))
                    self.hid.HidD_FreePreparsedData(pp)
                if caps.Feature != REPORT_LEN:
                    continue
                found = True
                print(f"Found {path}")
                if not dry_run:
                    buf = (c.c_ubyte * REPORT_LEN)(*data)
                    self.hid.HidD_SetFeature(h, buf, REPORT_LEN)
            finally:
                self.kernel32.CloseHandle(h)
            break
        return found


# ---- Linux / macOS: hidapi ------------------------------------------------------------------------
class HidapiBackend:
    def __init__(self):
        try:
            import hid  # pip install hidapi
        except ImportError:
            sys.exit("This needs the hidapi Python package: pip install hidapi")
        self.hid = hid

    def present(self, vid, pid):
        return bool(self.hid.enumerate(vid, pid))

    def send(self, vid, pid, data, dry_run):
        # Interface 0 is the keyboard interface that has the 64-byte vendor feature report.
        devs = [d for d in self.hid.enumerate(vid, pid) if d.get("interface_number") in (0, -1)]
        if not devs:
            return False
        d = devs[0]
        print(f"Found {d['path']!r}")
        if dry_run:
            return True
        dev = self.hid.device()
        try:
            dev.open_path(d["path"])
        except OSError as e:
            sys.exit(f"Cannot open the keyboard ({e}). Linux: install tools/udev/50-rk71.rules or use sudo. "
                     "macOS: allow Input Monitoring for your terminal.")
        try:
            dev.send_feature_report(bytes(data))
        except OSError:
            pass  # the firmware jumps to the bootloader at the end of the transfer; an error here is normal
        finally:
            dev.close()
        return True


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--vid", default="05ac")
    ap.add_argument("--pid", default="024f")
    ap.add_argument("--dry-run", action="store_true", help="only find the keyboard, send nothing")
    a = ap.parse_args()
    vid, pid = int(a.vid, 16), int(a.pid, 16)

    be = WindowsBackend() if sys.platform == "win32" else HidapiBackend()
    if be.present(*BOOTLOADER):
        print("Already in the bootloader (0C45:7040). Flash now: bash tools/flash_rk71.sh <image>.bin")
        return 0
    data = bytes([0]) + MAGIC + bytes(REPORT_LEN - 1 - len(MAGIC))
    if not be.send(vid, pid, data, a.dry_run):
        hint = " QMK is running: use Fn+Pause." if be.present(*QMK) else ""
        print(f"No stock keyboard ({a.vid}:{a.pid}) found on USB.{hint}")
        return 1
    if a.dry_run:
        return 0
    print("Sent the ISP command. Waiting for the bootloader...")
    for _ in range(50):
        time.sleep(0.1)
        if be.present(*BOOTLOADER):
            print("Bootloader 0C45:7040 is up. Flash now: bash tools/flash_rk71.sh <image>.bin")
            return 0
    print("Bootloader did not appear within 5 s.")
    return 2


if __name__ == "__main__":
    sys.exit(main())
