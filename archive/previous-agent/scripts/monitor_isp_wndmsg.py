"""
ISP Monitor using Windows RegisterDeviceNotification.
Fires immediately when ANY USB device connects/disconnects at the kernel level,
before any driver loads. Catches VID_0C45 even if HidUsb fails to start.
Also tries SetupDi with DIGCF_ALLCLASSES to find devices with driver problems.
"""
import ctypes, ctypes.wintypes, time, sys, threading, hid

kernel32 = ctypes.windll.kernel32
user32 = ctypes.windll.user32
setupapi = ctypes.windll.setupapi

# GUIDs
class GUID(ctypes.Structure):
    _fields_ = [("Data1", ctypes.c_ulong), ("Data2", ctypes.c_ushort),
                ("Data3", ctypes.c_ushort), ("Data4", ctypes.c_uint8 * 8)]

GUID_DEVINTERFACE_USB_DEVICE = GUID(0xA5DCBF10, 0x6530, 0x11D2,
    (ctypes.c_uint8*8)(0x90, 0x1F, 0x00, 0xC0, 0x4F, 0xB9, 0x51, 0xED))
GUID_DEVINTERFACE_HID = GUID(0x4D1E55B2, 0xF16F, 0x11CF,
    (ctypes.c_uint8*8)(0x88, 0xCB, 0x00, 0x11, 0x11, 0x00, 0x00, 0x30))

# DEV_BROADCAST_DEVICEINTERFACE
class DEV_BROADCAST_DEVICEINTERFACE(ctypes.Structure):
    _fields_ = [
        ("dbcc_size", ctypes.c_ulong),
        ("dbcc_devicetype", ctypes.c_ulong),
        ("dbcc_reserved", ctypes.c_ulong),
        ("dbcc_classguid", GUID),
        ("dbcc_name", ctypes.c_wchar * 256),
    ]

DBT_DEVICEARRIVAL = 0x8000
DBT_DEVICEREMOVECOMPLETE = 0x8004
DBT_DEVTYP_DEVICEINTERFACE = 0x00000005
WM_DEVICECHANGE = 0x0219
DEVICE_NOTIFY_WINDOW_HANDLE = 0x00000000

T0 = time.time()
def stamp(): return f"t+{time.time()-T0:.3f}s"

events = []
kb_seen = {"normal": True, "isp": False}

def check_setupdi_all():
    """Use SetupDi to find ANY device matching VID_0C45, even with driver problems."""
    DIGCF_ALLCLASSES = 0x00000004
    DIGCF_PRESENT = 0x00000002

    hdevinfo = setupapi.SetupDiGetClassDevsW(None, None, None, DIGCF_ALLCLASSES | DIGCF_PRESENT)
    if not hdevinfo or hdevinfo == ctypes.c_void_p(-1).value:
        return []

    class SP_DEVINFO_DATA(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_ulong), ("ClassGuid", GUID),
                    ("DevInst", ctypes.c_ulong), ("Reserved", ctypes.c_ulong*2)]

    results = []
    devinfo = SP_DEVINFO_DATA()
    devinfo.cbSize = ctypes.sizeof(SP_DEVINFO_DATA)
    idx = 0
    while setupapi.SetupDiEnumDeviceInfo(hdevinfo, idx, ctypes.byref(devinfo)):
        # Get instance ID
        iid_buf = (ctypes.c_wchar * 512)()
        if setupapi.SetupDiGetDeviceInstanceIdW(hdevinfo, ctypes.byref(devinfo), iid_buf, 512, None):
            iid = iid_buf.value
            if "0C45" in iid.upper() or "7040" in iid.upper():
                results.append(iid)
        idx += 1
    setupapi.SetupDiDestroyDeviceInfoList(hdevinfo)
    return results

# Window procedure
WNDPROCTYPE = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.wintypes.HWND,
                                   ctypes.c_uint, ctypes.c_uint64, ctypes.c_int64)

def wnd_proc(hwnd, msg, wparam, lparam):
    if msg == WM_DEVICECHANGE and lparam:
        try:
            hdr_type = ctypes.c_ulong.from_address(lparam + 4).value
            if hdr_type == DBT_DEVTYP_DEVICEINTERFACE:
                info = DEV_BROADCAST_DEVICEINTERFACE.from_address(lparam)
                name = info.dbcc_name
                action = "ARRIVED" if wparam == DBT_DEVICEARRIVAL else \
                         "REMOVED" if wparam == DBT_DEVICEREMOVECOMPLETE else f"0x{wparam:X}"
                ts = stamp()
                print(f"[{ts}] USB/HID {action}: {name}", flush=True)
                if "0C45" in name.upper():
                    print(f"  *** VID_0C45 detected via window message! ***", flush=True)
                    found = check_setupdi_all()
                    for f in found:
                        print(f"  SetupDi found: {f}", flush=True)
                events.append((ts, action, name))
        except Exception as e:
            pass
    return user32.DefWindowProcW(hwnd, msg, ctypes.c_uint64(wparam), ctypes.c_int64(lparam))

def run_window():
    wc = ctypes.create_unicode_buffer("ISP_Monitor_Class")
    wndclass = ctypes.create_string_buffer(80)

    # WNDCLASSEXW
    class WNDCLASSEXW(ctypes.Structure):
        _fields_ = [
            ("cbSize", ctypes.c_uint), ("style", ctypes.c_uint),
            ("lpfnWndProc", WNDPROCTYPE), ("cbClsExtra", ctypes.c_int),
            ("cbWndExtra", ctypes.c_int), ("hInstance", ctypes.wintypes.HANDLE),
            ("hIcon", ctypes.wintypes.HANDLE), ("hCursor", ctypes.wintypes.HANDLE),
            ("hbrBackground", ctypes.wintypes.HANDLE),
            ("lpszMenuName", ctypes.c_wchar_p), ("lpszClassName", ctypes.c_wchar_p),
            ("hIconSm", ctypes.wintypes.HANDLE),
        ]

    wnd_proc_cb = WNDPROCTYPE(wnd_proc)

    hInst = kernel32.GetModuleHandleW(None)
    wcex = WNDCLASSEXW()
    wcex.cbSize = ctypes.sizeof(WNDCLASSEXW)
    wcex.lpfnWndProc = wnd_proc_cb
    wcex.hInstance = hInst
    wcex.lpszClassName = "ISP_Monitor_Class"

    atom = user32.RegisterClassExW(ctypes.byref(wcex))
    if not atom:
        print(f"RegisterClassEx failed: {ctypes.GetLastError()}")
        return

    hwnd = user32.CreateWindowExW(0, "ISP_Monitor_Class", "ISP Monitor",
                                   0, 0, 0, 0, 0, None, None, hInst, None)
    if not hwnd:
        print(f"CreateWindow failed: {ctypes.GetLastError()}")
        return

    # Register for USB device notifications
    nb_usb = DEV_BROADCAST_DEVICEINTERFACE()
    nb_usb.dbcc_size = ctypes.sizeof(DEV_BROADCAST_DEVICEINTERFACE)
    nb_usb.dbcc_devicetype = DBT_DEVTYP_DEVICEINTERFACE
    nb_usb.dbcc_classguid = GUID_DEVINTERFACE_USB_DEVICE
    hnotify_usb = user32.RegisterDeviceNotificationW(hwnd, ctypes.byref(nb_usb),
                                                      DEVICE_NOTIFY_WINDOW_HANDLE)

    # Register for HID device notifications
    nb_hid = DEV_BROADCAST_DEVICEINTERFACE()
    nb_hid.dbcc_size = ctypes.sizeof(DEV_BROADCAST_DEVICEINTERFACE)
    nb_hid.dbcc_devicetype = DBT_DEVTYP_DEVICEINTERFACE
    nb_hid.dbcc_classguid = GUID_DEVINTERFACE_HID
    hnotify_hid = user32.RegisterDeviceNotificationW(hwnd, ctypes.byref(nb_hid),
                                                      DEVICE_NOTIFY_WINDOW_HANDLE)

    print(f"Window created. USB notify handle: {hnotify_usb}  HID notify handle: {hnotify_hid}")

    # Message loop
    class MSG(ctypes.Structure):
        _fields_ = [("hwnd", ctypes.wintypes.HWND), ("message", ctypes.c_uint),
                    ("wParam", ctypes.wintypes.WPARAM), ("lParam", ctypes.wintypes.LPARAM),
                    ("time", ctypes.c_ulong), ("pt", ctypes.wintypes.POINT)]

    msg = MSG()
    deadline = time.time() + 120
    while time.time() < deadline:
        while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        time.sleep(0.001)

    if hnotify_usb: user32.UnregisterDeviceNotification(hnotify_usb)
    if hnotify_hid: user32.UnregisterDeviceNotification(hnotify_hid)
    user32.DestroyWindow(hwnd)

# Also run a parallel polling thread for extra coverage
def poll_thread():
    last_normal = True
    while time.time() - T0 < 120:
        devs = hid.enumerate()
        normal = any(d['vendor_id'] == 0x05AC and d['product_id'] == 0x024F for d in devs)
        isp = any(d['vendor_id'] == 0x0C45 for d in devs)

        if last_normal and not normal:
            ts = stamp()
            print(f"[{ts}] [HID POLL] KEYBOARD DISCONNECTED")
            # Check SetupDi for any VID_0C45 devices (including problem devices)
            found = check_setupdi_all()
            if found:
                print(f"  SetupDi found VID_0C45: {found}")
        if not last_normal and normal:
            print(f"[{stamp()}] [HID POLL] Keyboard reconnected")
        if isp:
            print(f"[{stamp()}] [HID POLL] VID_0C45 in hid.enumerate()!")

        last_normal = normal
        time.sleep(0.002)

print("=== ISP Monitor (Window Messages + Polling) ===")
print("Run the EXE Flash → Fn+P while this runs.")
print(f"Monitoring for 120s...\n")

# Run polling in background thread
t = threading.Thread(target=poll_thread, daemon=True)
t.start()

# Run window message loop in main thread
run_window()

print(f"\nDone. Total window events: {len(events)}")
for ev in events:
    print(f"  {ev}")
