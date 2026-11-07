"""
Reboot-and-flash using libusb (sonixflasher's DLL).
1. Sends the SONiX reboot-to-ISP magic to VID_05AC/024F
2. Finds VID_0C45/7040 at USB level (before hid.sys, faster)
3. Flashes QMK via HID SET_REPORT control transfers
"""
import os, sys, time

# Use sonixflasher's libusb DLL
_LIBUSB_DIR = os.path.join(os.path.dirname(__file__), "sonixflasher")
os.add_dll_directory(_LIBUSB_DIR)

try:
    import usb1
except ImportError:
    # Try the bundled one
    sys.path.insert(0, r"C:\Users\<user>\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages")
    import usb1

HEX_PATH = os.path.join(os.path.dirname(__file__), "qmk_firmware", ".build", "rk_rk71_default.hex")
BIN_PATH = os.path.join(os.path.dirname(__file__), "qmk_firmware", ".build", "rk_rk71_default.bin")

NORMAL_VID, NORMAL_PID = 0x05AC, 0x024F
ISP_VID,    ISP_PID    = 0x0C45, 0x7040

# Magic reboot-to-ISP bytes (discovered via sonixflasher debug trace)
REBOOT_MAGIC = bytes([0xAA, 0x55, 0xA5, 0x5A, 0xFF, 0x00, 0x33, 0xCC]) + bytes(56)

FLASH_SIZE  = 0x10000
CHUNK_SIZE  = 48
PAGE_SIZE   = 0x200

def load_bin():
    with open(BIN_PATH, 'rb') as f:
        data = bytearray(f.read())
    assert len(data) == FLASH_SIZE
    return data

def send_control(dev, data, iface=1, report_type=0x02):
    """HID SET_REPORT control transfer (EP0). report_type: 1=input 2=output 3=feature"""
    wValue = (report_type << 8) | 0x00  # report type | report ID 0
    # bmRequestType=0x21: host->device, class, interface
    return dev.controlWrite(0x21, 0x09, wValue, iface, data, timeout=500)

def recv_control(dev, length=64, iface=1, report_type=0x01):
    """HID GET_REPORT control transfer."""
    wValue = (report_type << 8) | 0x00
    # bmRequestType=0xA1: device->host, class, interface
    return dev.controlRead(0xA1, 0x01, wValue, iface, length, timeout=500)

def isp_send(dev, cmd_bytes):
    """Send 64-byte ISP command via feature report (type=3) or output (type=2)."""
    pkt = bytes(cmd_bytes[:64]).ljust(64, b'\x00')
    for rtype in [3, 2]:  # try feature first, then output
        try:
            n = send_control(dev, pkt, iface=0, report_type=rtype)
            return n
        except usb1.USBErrorPipe:
            pass
        except Exception:
            pass
    return 0

def isp_recv(dev):
    """Read 64-byte ISP response."""
    for rtype in [1, 3]:
        try:
            return bytes(recv_control(dev, 64, iface=0, report_type=rtype))
        except Exception:
            pass
    return None

def probe(dev):
    print("  Probing ISP device...")
    # Get FW version: command 0x01 with SONiX magic
    isp_send(dev, [0x01, 0xAA, 0x55] + [0]*61)
    r = isp_recv(dev)
    if r:
        print(f"  Response: {r[:16].hex()}")
        return True
    # Try older command 0x05
    isp_send(dev, [0x05] + [0]*63)
    r = isp_recv(dev)
    if r:
        print(f"  Response (0x05): {r[:16].hex()}")
        return True
    return False

def erase_page(dev, page):
    # Enable Erase (0x24 / 0x04) then erase
    isp_send(dev, [0x24, 0xAA, 0x55] + [0]*61)
    isp_recv(dev)
    isp_send(dev, [0x04, page & 0xFF, (page>>8)&0xFF] + [0]*61)
    time.sleep(0.02)

def write_chunk(dev, chunk_num, data):
    assert len(data) == CHUNK_SIZE
    isp_send(dev, [0x06, chunk_num & 0xFF, (chunk_num>>8)&0xFF] + list(data))
    time.sleep(0.001)

def commit(dev):
    isp_send(dev, [0x09] + [0]*63)
    time.sleep(0.1)

def main():
    print("=== RK71 QMK Flasher (libusb) ===")
    firmware = load_bin()
    print(f"Firmware: {BIN_PATH} ({len(firmware)} bytes)")

    ctx = usb1.USBContext()

    # --- Step 1: Send reboot-to-ISP command to normal keyboard ---
    print(f"\nStep 1: Sending reboot-to-ISP to VID_{NORMAL_VID:04X}/PID_{NORMAL_PID:04X}...")
    normal_dev = None
    for d in ctx.getDeviceList(skip_on_error=True):
        if d.getVendorID() == NORMAL_VID and d.getProductID() == NORMAL_PID:
            try:
                normal_dev = d.open()
                break
            except Exception as e:
                print(f"  Open failed: {e}")

    if not normal_dev:
        print("  Keyboard not found in normal mode!")
        # Maybe already in ISP?
    else:
        try:
            # Try interface 1 (MI_01, the vendor collection interface)
            for iface in [1, 0]:
                try:
                    n = send_control(normal_dev, REBOOT_MAGIC, iface=iface, report_type=2)
                    print(f"  Reboot command sent on iface {iface} ({n} bytes)")
                    break
                except Exception as e:
                    print(f"  iface {iface}: {e}")
        finally:
            normal_dev.close()

    # --- Step 2: Wait for ISP device ---
    print(f"\nStep 2: Waiting for ISP device VID_{ISP_VID:04X}/PID_{ISP_PID:04X}...")
    isp_handle = None
    deadline = time.time() + 15.0
    attempts = 0
    while time.time() < deadline:
        attempts += 1
        for d in ctx.getDeviceList(skip_on_error=True):
            if d.getVendorID() == ISP_VID and d.getProductID() == ISP_PID:
                print(f"  Found ISP device! (attempt {attempts})")
                try:
                    isp_handle = d.open()
                    break
                except Exception as e:
                    print(f"  Open failed: {e}")
        if isp_handle:
            break
        time.sleep(0.005)

    if not isp_handle:
        print("  ISP device not found after 15s")
        ctx.close()
        sys.exit(1)

    # --- Step 3: Flash ---
    print("\nStep 3: Flashing QMK...")
    try:
        probe(isp_handle)

        # Determine pages to flash
        fw_start = 0
        fw_end = FLASH_SIZE
        while fw_end > 0 and firmware[fw_end-1] == 0xFF:
            fw_end -= 1
        fw_end = (fw_end + PAGE_SIZE - 1) & ~(PAGE_SIZE - 1)
        pages = fw_end // PAGE_SIZE
        print(f"  Flashing {pages} pages ({fw_end} bytes)...")

        for page in range(pages):
            sys.stdout.write(f"\r  Erasing page {page+1}/{pages}...")
            sys.stdout.flush()
            erase_page(isp_handle, page)

        print()
        chunks_per_page = PAGE_SIZE // CHUNK_SIZE
        total_chunks = pages * chunks_per_page
        for chunk in range(total_chunks):
            offset = chunk * CHUNK_SIZE
            data = firmware[offset:offset+CHUNK_SIZE]
            write_chunk(isp_handle, chunk, data)
            if chunk % 20 == 0:
                pct = (chunk+1)*100//total_chunks
                sys.stdout.write(f"\r  Writing chunk {chunk+1}/{total_chunks} ({pct}%)...")
                sys.stdout.flush()

        print()
        commit(isp_handle)
        print("  Done! Keyboard rebooting into QMK...")

    finally:
        isp_handle.close()
        ctx.close()

if __name__ == "__main__":
    main()
