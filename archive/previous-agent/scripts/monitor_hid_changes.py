"""
Monitors all changes to the RK71's HID interfaces every 50ms.
Run this, then click Flash in the EXE. It will log all changes including
any re-enumeration, new paths, or capability changes.
"""
import ctypes, ctypes.wintypes as wt, time, hid, sys

kernel32 = ctypes.windll.kernel32
hid_dll  = ctypes.windll.hid
kernel32.CreateFileW.restype = wt.HANDLE
INVALID = wt.HANDLE(-1).value

class HIDP_CAPS(ctypes.Structure):
    _fields_ = [
        ('Usage', wt.USHORT), ('UsagePage', wt.USHORT),
        ('InputReportByteLength',   wt.USHORT),
        ('OutputReportByteLength',  wt.USHORT),
        ('FeatureReportByteLength', wt.USHORT),
        ('Reserved', wt.USHORT * 17),
        ('NumberLinkCollectionNodes', wt.USHORT),
        ('NumberInputButtonCaps', wt.USHORT), ('NumberInputValueCaps', wt.USHORT),
        ('NumberInputDataIndices', wt.USHORT),
        ('NumberOutputButtonCaps', wt.USHORT), ('NumberOutputValueCaps', wt.USHORT),
        ('NumberOutputDataIndices', wt.USHORT),
        ('NumberFeatureButtonCaps', wt.USHORT), ('NumberFeatureValueCaps', wt.USHORT),
        ('NumberFeatureDataIndices', wt.USHORT),
    ]

def get_snapshot():
    """Get current state of all RK71 HID interfaces."""
    snap = {}
    for d in hid.enumerate(0x05AC, 0x024F):
        path = d['path']
        if isinstance(path, bytes): path = path.decode()
        up   = d.get('usage_page', 0)
        iface = d.get('interface_number', -1)
        key = (iface, up, path[-30:])
        # Get caps
        h = kernel32.CreateFileW(path, 0xC0000000, 3, None, 3, 0, None)
        caps_str = "no_access"
        if h != INVALID:
            preparsed = ctypes.c_void_p(0)
            if hid_dll.HidD_GetPreparsedData(h, ctypes.byref(preparsed)):
                caps = HIDP_CAPS()
                if hid_dll.HidP_GetCaps(preparsed, ctypes.byref(caps)) == 0x00110000:
                    caps_str = "in=%d out=%d feat=%d" % (
                        caps.InputReportByteLength,
                        caps.OutputReportByteLength,
                        caps.FeatureReportByteLength)
                hid_dll.HidD_FreePreparsedData(preparsed)
            kernel32.CloseHandle(h)
        snap[key] = caps_str
    return snap

print("Monitoring RK71 HID changes. Click Flash in EXE now...")
print("Will log any changes (new paths, descriptor changes, re-enumeration).")
sys.stdout.flush()

prev = get_snapshot()
print("Baseline:")
for k, v in sorted(prev.items()):
    print("  iface=%d UP=0x%04X %s" % (k[0], k[1], v))
sys.stdout.flush()

t0 = time.time()
while time.time() - t0 < 60:
    time.sleep(0.05)
    curr = get_snapshot()

    # Detect new paths
    for k in curr:
        if k not in prev:
            print("[+%ds] NEW: iface=%d UP=0x%04X caps=%s path=...%s" % (
                int(time.time()-t0), k[0], k[1], curr[k], k[2]))
            sys.stdout.flush()
    # Detect removed paths
    for k in prev:
        if k not in curr:
            print("[+%ds] GONE: iface=%d UP=0x%04X path=...%s" % (
                int(time.time()-t0), k[0], k[1], k[2]))
            sys.stdout.flush()
    # Detect capability changes
    for k in curr:
        if k in prev and curr[k] != prev[k]:
            print("[+%ds] CHANGED: iface=%d UP=0x%04X  %s -> %s" % (
                int(time.time()-t0), k[0], k[1], prev[k], curr[k]))
            sys.stdout.flush()

    prev = curr

print("Done (60s elapsed).")
