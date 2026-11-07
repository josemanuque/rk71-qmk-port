"""
Monitor raw keyboard input from the RK71 using Windows Raw Input API.
Works regardless of which window has focus.
"""
import ctypes, ctypes.wintypes as wt, sys, time, threading

user32   = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

WM_INPUT = 0x00FF
RIM_TYPEKEYBOARD = 1
RID_INPUT = 0x10000003

class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [("usUsagePage", wt.USHORT),
                ("usUsage",     wt.USHORT),
                ("dwFlags",     wt.DWORD),
                ("hwndTarget",  wt.HWND)]

class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [("dwType",   wt.DWORD),
                ("dwSize",   wt.DWORD),
                ("hDevice",  wt.HANDLE),
                ("wParam",   ctypes.c_uint64)]

class RAWKEYBOARD(ctypes.Structure):
    _fields_ = [("MakeCode",          wt.USHORT),
                ("Flags",             wt.USHORT),
                ("Reserved",          wt.USHORT),
                ("VKey",              wt.USHORT),
                ("Message",           wt.UINT),
                ("ExtraInformation",  wt.ULONG)]

class RAWINPUT(ctypes.Structure):
    class _DATA(ctypes.Union):
        class _FIELDS(ctypes.Structure):
            _fields_ = [("keyboard", RAWKEYBOARD)]
        _fields_ = [("keyboard", RAWKEYBOARD)]
    _fields_ = [("header", RAWINPUTHEADER),
                ("data",   _DATA)]

WNDPROCTYPE = ctypes.WINFUNCTYPE(ctypes.c_int64, wt.HWND, wt.UINT,
                                  ctypes.c_uint64, ctypes.c_int64)

VK_NAMES = {
    0x08: 'Backspace', 0x09: 'Tab', 0x0D: 'Enter', 0x10: 'Shift',
    0x11: 'Ctrl', 0x12: 'Alt', 0x14: 'CapsLock', 0x1B: 'Esc',
    0x20: 'Space', 0x25: 'Left', 0x26: 'Up', 0x27: 'Right', 0x28: 'Down',
}
for c in range(0x30, 0x3A): VK_NAMES[c] = chr(c)
for c in range(0x41, 0x5B): VK_NAMES[c] = chr(c)
for i in range(1, 13): VK_NAMES[0x6F + i] = f'F{i}'

rk71_handle = None

def get_device_name(hDevice):
    size = wt.UINT(0)
    user32.GetRawInputDeviceInfoW(hDevice, 0x20000007, None, ctypes.byref(size))
    buf = ctypes.create_unicode_buffer(size.value)
    user32.GetRawInputDeviceInfoW(hDevice, 0x20000007, buf, ctypes.byref(size))
    return buf.value.upper()

def find_rk71_handle():
    count = wt.UINT(0)
    user32.GetRawInputDeviceList(None, ctypes.byref(count), ctypes.sizeof(ctypes.c_uint32) * 2)
    DevInfo = ctypes.c_uint8 * (ctypes.sizeof(ctypes.c_uint32) * 2 * count.value)
    devices = DevInfo()
    user32.GetRawInputDeviceList(ctypes.byref(devices), ctypes.byref(count),
                                 ctypes.sizeof(ctypes.c_uint32) * 2)
    # Each entry: HANDLE(4/8 bytes) + DWORD type. Use struct
    import struct
    n = count.value
    raw = bytes(devices)
    ptr_sz = ctypes.sizeof(ctypes.c_void_p)
    entry_sz = ptr_sz + 4
    for i in range(n):
        off = i * entry_sz
        h = struct.unpack_from('Q' if ptr_sz == 8 else 'I', raw, off)[0]
        try:
            name = get_device_name(h)
            if 'VID_05AC' in name and 'PID_024F' in name:
                return h, name
        except Exception:
            pass
    return None, None

def wnd_proc(hwnd, msg, wparam, lparam):
    global rk71_handle
    if msg == WM_INPUT:
        size = wt.UINT(0)
        user32.GetRawInputData(lparam, RID_INPUT, None, ctypes.byref(size), ctypes.sizeof(RAWINPUTHEADER))
        buf = ctypes.create_string_buffer(size.value)
        user32.GetRawInputData(lparam, RID_INPUT, buf, ctypes.byref(size), ctypes.sizeof(RAWINPUTHEADER))
        ri = ctypes.cast(buf, ctypes.POINTER(RAWINPUT)).contents
        if ri.header.dwType == RIM_TYPEKEYBOARD:
            if rk71_handle is None or ri.header.hDevice == rk71_handle:
                vk   = ri.data.keyboard.VKey
                flags = ri.data.keyboard.Flags
                action = "UP" if (flags & 1) else "DN"
                name = VK_NAMES.get(vk, f"0x{vk:02X}")
                src = "RK71" if (rk71_handle and ri.header.hDevice == rk71_handle) else "other"
                print(f"[{src}] {action} {name}  (VK=0x{vk:02X} flags=0x{flags:02X})")
    return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

def main():
    global rk71_handle
    rk71_handle, rk71_name = find_rk71_handle()
    if rk71_handle:
        print(f"Tracking RK71: {rk71_name[:60]}...")
    else:
        print("RK71 not found in raw input list — showing ALL keyboard events")

    # Create message-only window
    WC = type('WNDCLASSEXW', (ctypes.Structure,), {
        '_fields_': [('cbSize',wt.UINT),('style',wt.UINT),('lpfnWndProc',WNDPROCTYPE),
                     ('cbClsExtra',ctypes.c_int),('cbWndExtra',ctypes.c_int),
                     ('hInstance',wt.HINSTANCE),('hIcon',wt.HANDLE),('hCursor',wt.HANDLE),
                     ('hbrBackground',wt.HANDLE),('lpszMenuName',wt.LPCWSTR),
                     ('lpszClassName',wt.LPCWSTR),('hIconSm',wt.HANDLE)]})
    kernel32.GetModuleHandleW.restype = wt.HINSTANCE
    proc = WNDPROCTYPE(wnd_proc)
    wc = WC()
    wc.cbSize = ctypes.sizeof(WC)
    wc.lpfnWndProc = proc
    wc.hInstance = kernel32.GetModuleHandleW(None)
    wc.lpszClassName = "RawInputMonitor"
    if not user32.RegisterClassExW(ctypes.byref(wc)):
        print("RegisterClassExW failed")
        return
    user32.CreateWindowExW.restype = wt.HWND
    user32.CreateWindowExW.argtypes = [wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        wt.HWND, ctypes.c_void_p, wt.HINSTANCE, ctypes.c_void_p]
    hwnd = user32.CreateWindowExW(0, "RawInputMonitor", "RIMonitor", 0,
                                  0, 0, 0, 0, wt.HWND(-3), None, wc.hInstance, None)
    rid = RAWINPUTDEVICE()
    rid.usUsagePage = 0x01
    rid.usUsage     = 0x06
    rid.dwFlags     = 0x00000100  # RIDEV_INPUTSINK — receive input even without focus
    rid.hwndTarget  = hwnd
    if not user32.RegisterRawInputDevices(ctypes.byref(rid), 1, ctypes.sizeof(rid)):
        print("RegisterRawInputDevices failed")
        return

    print("Listening for 20 seconds (press keys on RK71)...")
    start = time.time()
    msg = wt.MSG()
    while time.time() - start < 20:
        r = user32.PeekMessageW(ctypes.byref(msg), hwnd, 0, 0, 1)
        if r > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        else:
            time.sleep(0.005)
    print("Done.")

if __name__ == '__main__':
    main()
