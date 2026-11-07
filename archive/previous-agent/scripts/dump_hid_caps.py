"""
Dump full HID capabilities for ALL collections of VID_05AC PID_024F.
Looking for any collection with output or feature reports that could carry firmware data.
Also dumps raw HID descriptor bytes.
"""
import ctypes, ctypes.wintypes, hid, sys

kernel32 = ctypes.windll.kernel32
kernel32.CreateFileW.restype = ctypes.wintypes.HANDLE
kernel32.CreateFileW.argtypes = [
    ctypes.wintypes.LPCWSTR, ctypes.wintypes.DWORD, ctypes.wintypes.DWORD,
    ctypes.c_void_p, ctypes.wintypes.DWORD, ctypes.wintypes.DWORD,
    ctypes.wintypes.HANDLE,
]

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 3
INVALID_HANDLE = ctypes.wintypes.HANDLE(-1).value

hid_dll = ctypes.windll.hid

class HIDP_CAPS(ctypes.Structure):
    _fields_ = [
        ("Usage", ctypes.c_uint16),
        ("UsagePage", ctypes.c_uint16),
        ("InputReportByteLength", ctypes.c_uint16),
        ("OutputReportByteLength", ctypes.c_uint16),
        ("FeatureReportByteLength", ctypes.c_uint16),
        ("Reserved", ctypes.c_uint16 * 17),
        ("NumberLinkCollectionNodes", ctypes.c_uint16),
        ("NumberInputButtonCaps", ctypes.c_uint16),
        ("NumberInputValueCaps", ctypes.c_uint16),
        ("NumberInputDataIndices", ctypes.c_uint16),
        ("NumberOutputButtonCaps", ctypes.c_uint16),
        ("NumberOutputValueCaps", ctypes.c_uint16),
        ("NumberOutputDataIndices", ctypes.c_uint16),
        ("NumberFeatureButtonCaps", ctypes.c_uint16),
        ("NumberFeatureValueCaps", ctypes.c_uint16),
        ("NumberFeatureDataIndices", ctypes.c_uint16),
    ]

class HIDD_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("Size", ctypes.c_ulong),
        ("VendorID", ctypes.c_uint16),
        ("ProductID", ctypes.c_uint16),
        ("VersionNumber", ctypes.c_uint16),
    ]

devs = hid.enumerate()
kb_devs = [d for d in devs if d['vendor_id'] == 0x05AC and d['product_id'] == 0x024F]
print(f"Found {len(kb_devs)} VID_05AC PID_024F interfaces\n")

for i, d in enumerate(kb_devs):
    path = d['path']
    if isinstance(path, bytes):
        path = path.decode('utf-8', errors='replace')
    print(f"[{i+1}] Path: {path}")
    print(f"     Usage: 0x{d['usage']:04X}  UsagePage: 0x{d['usage_page']:04X}")
    print(f"     Product: {d.get('product_string', '?')}")
    print(f"     Interface: {d.get('interface_number', -1)}")

    # Try opening
    h = kernel32.CreateFileW(path, GENERIC_READ | GENERIC_WRITE,
                              FILE_SHARE_READ | FILE_SHARE_WRITE,
                              None, OPEN_EXISTING, 0, None)
    err = ctypes.GetLastError()
    if h == INVALID_HANDLE:
        # Try read-only
        h = kernel32.CreateFileW(path, GENERIC_READ,
                                  FILE_SHARE_READ | FILE_SHARE_WRITE,
                                  None, OPEN_EXISTING, 0, None)
        err = ctypes.GetLastError()
        if h == INVALID_HANDLE:
            print(f"     [OPEN FAILED] err={err}")
            print()
            continue
        else:
            print(f"     Opened READ-ONLY")
    else:
        print(f"     Opened READ+WRITE")

    # Get HID capabilities
    preparsed = ctypes.c_void_p()
    if hid_dll.HidD_GetPreparsedData(h, ctypes.byref(preparsed)):
        caps = HIDP_CAPS()
        status = hid_dll.HidP_GetCaps(preparsed, ctypes.byref(caps))
        if status == 0x00110000:  # HIDP_STATUS_SUCCESS
            print(f"     UsagePage=0x{caps.UsagePage:04X}  Usage=0x{caps.Usage:04X}")
            print(f"     InputReport={caps.InputReportByteLength}  OutputReport={caps.OutputReportByteLength}  FeatureReport={caps.FeatureReportByteLength}")
            print(f"     InputButtons={caps.NumberInputButtonCaps}  InputValues={caps.NumberInputValueCaps}")
            print(f"     OutputButtons={caps.NumberOutputButtonCaps}  OutputValues={caps.NumberOutputValueCaps}")
            print(f"     FeatureButtons={caps.NumberFeatureButtonCaps}  FeatureValues={caps.NumberFeatureValueCaps}")
            if caps.OutputReportByteLength > 0:
                print(f"     *** HAS OUTPUT REPORTS! ***")
            if caps.FeatureReportByteLength > 0:
                print(f"     *** HAS FEATURE REPORTS! ***")
        hid_dll.HidD_FreePreparsedData(preparsed)

    # Get raw HID descriptor
    class HID_DESCRIPTOR(ctypes.Structure):
        _fields_ = [
            ("bLength", ctypes.c_uint8),
            ("bDescriptorType", ctypes.c_uint8),
            ("bcdHID", ctypes.c_uint16),
            ("bCountryCode", ctypes.c_uint8),
            ("bNumDescriptors", ctypes.c_uint8),
            ("bReportDescriptorType", ctypes.c_uint8),
            ("wReportDescriptorLength", ctypes.c_uint16),
        ]

    # Try HidD_GetPhysicalDescriptor to get raw report descriptor
    # Actually use IoControl to get raw HID report descriptor
    buf_size = 4096
    buf = (ctypes.c_uint8 * buf_size)()
    bytes_returned = ctypes.wintypes.DWORD(0)
    # IOCTL_HID_GET_REPORT_DESCRIPTOR = 0x000b0113
    IOCTL_HID_GET_REPORT_DESCRIPTOR = 0x000b0113
    ok = kernel32.DeviceIoControl(
        h, IOCTL_HID_GET_REPORT_DESCRIPTOR,
        None, 0,
        buf, buf_size,
        ctypes.byref(bytes_returned),
        None
    )
    if ok and bytes_returned.value > 0:
        desc_bytes = bytes(buf[:bytes_returned.value])
        print(f"     Raw HID descriptor ({bytes_returned.value} bytes): {desc_bytes.hex()}")
    else:
        err2 = ctypes.GetLastError()
        print(f"     Raw descriptor IOCTL failed: err={err2}")

    # Try sending a feature report (even if caps says 0, some devices still respond)
    for report_id in [0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0xB2]:
        buf = (ctypes.c_uint8 * 65)(report_id, *([0]*64))
        ok = hid_dll.HidD_GetFeature(h, buf, 65)
        if ok:
            resp = bytes(buf[:32])
            print(f"     GetFeature(id=0x{report_id:02X}) SUCCESS: {resp.hex()}")
        else:
            err3 = ctypes.GetLastError()
            if err3 not in (1, 87, 6):  # skip "incorrect func", "invalid param", "invalid handle"
                print(f"     GetFeature(id=0x{report_id:02X}) err={err3}")

    kernel32.CloseHandle(h)
    print()
