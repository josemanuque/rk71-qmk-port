#!/usr/bin/env python3
"""
RK71 QMK firmware flasher — SONiX SN32F240B ISP HID protocol.

Usage:
  python flash_qmk.py [--hex path/to/firmware.hex] [--dry-run]

The keyboard must already be in ISP mode (hold Esc, plug USB).
"""
import sys, os, time, argparse

try:
    import hid
except ImportError:
    print("ERROR: hidapi not installed. Run: pip install hidapi")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Known VID/PID combinations for SONiX SN32F240B hardware ISP
# ---------------------------------------------------------------------------
ISP_CANDIDATES = [
    (0x0C45, 0x8006, "SONiX ISP (observed on RK71)"),
    (0x0C45, 0x7040, "SONiX SN32F240B hardware ISP (QMK standard)"),
    (0x0C45, 0x7900, "SONiX SN32F240 hardware ISP"),
    (0x0C45, 0x7010, "SONiX SN32F260 hardware ISP"),
]

FLASH_BASE   = 0x00000000   # SN32F240B flash start address
FLASH_SIZE   = 0x00010000   # 64 KB flash
PAGE_SIZE    = 0x200        # 512 bytes per flash page (confirmed from fw)
CHUNK_SIZE   = 48           # bytes per HID write chunk (must fit in 64-byte report)

DEFAULT_HEX = os.path.join(os.path.dirname(__file__),
                           "qmk_firmware", ".build", "rk_rk71_default.hex")

# ---------------------------------------------------------------------------
# Intel HEX parser
# ---------------------------------------------------------------------------
def load_hex(path):
    """Return a 64KB bytearray filled with 0xFF, with firmware loaded in."""
    data = bytearray(b'\xFF' * FLASH_SIZE)
    base_addr = 0
    with open(path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line.startswith(':'):
                continue
            rec = bytes.fromhex(line[1:])
            byte_count = rec[0]
            addr       = (rec[1] << 8) | rec[2]
            rec_type   = rec[3]
            payload    = rec[4:4+byte_count]
            checksum   = rec[4+byte_count]
            if rec_type == 0x00:   # Data
                abs_addr = base_addr + addr
                for i, b in enumerate(payload):
                    if abs_addr + i < FLASH_SIZE:
                        data[abs_addr + i] = b
            elif rec_type == 0x02:  # Extended segment address
                base_addr = ((payload[0] << 8) | payload[1]) << 4
            elif rec_type == 0x04:  # Extended linear address
                base_addr = ((payload[0] << 8) | payload[1]) << 16
            elif rec_type == 0x01:  # EOF
                break
    return data

def firmware_range(data):
    """Return (start, end) of non-0xFF bytes in data."""
    start = 0
    end = len(data)
    while start < end and data[start] == 0xFF:
        start += 1
    while end > start and data[end-1] == 0xFF:
        end -= 1
    return start, end

# ---------------------------------------------------------------------------
# SONiX ISP HID protocol
# ---------------------------------------------------------------------------
def find_isp_device(timeout_s=30.0):
    deadline = time.time() + timeout_s
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        devs = hid.enumerate()
        for vid, pid, label in ISP_CANDIDATES:
            for d in devs:
                if d['vendor_id'] == vid and d['product_id'] == pid:
                    print(f"  Found: {label}  VID=0x{vid:04X} PID=0x{pid:04X} (attempt {attempt})")
                    print(f"  Path: {d['path']}")
                    return d['path'], vid, pid
        time.sleep(0.05)
    return None, None, None

def _send(dev, data):
    """Send a 64-byte HID report (prepend 0x00 as report ID)."""
    pkt = bytes([0x00]) + bytes(data[:64]) + bytes(max(0, 64-len(data)))
    dev.write(pkt[:65])

def _recv(dev, timeout_ms=1000):
    return dev.read(64, timeout_ms)

def probe_device(dev):
    """Try to identify the protocol version."""
    print("  Probing device protocol...")
    # Try SONiX standard probe: command 0x05 (get version)
    _send(dev, [0x05] + [0x00]*63)
    r = _recv(dev, 500)
    if r:
        print(f"  Response to 0x05 probe: {bytes(r).hex()[:32]}...")
        return 'sonix_v1'
    # Try alternative probe
    _send(dev, [0xAA, 0x55, 0xBE, 0xEF] + [0x00]*60)
    r = _recv(dev, 500)
    if r:
        print(f"  Response to AA55BEEF probe: {bytes(r).hex()[:32]}...")
        return 'sonix_aa55'
    return 'unknown'

def erase_page_v1(dev, page_num):
    """Erase one 512-byte page. Command byte 0x07."""
    _send(dev, [0x07, page_num & 0xFF, (page_num >> 8) & 0xFF] + [0x00]*61)
    time.sleep(0.05)

def write_chunk_v1(dev, chunk_num, data):
    """Write 48-byte chunk. Command byte 0x06."""
    assert len(data) == CHUNK_SIZE
    _send(dev, [0x06, chunk_num & 0xFF, (chunk_num >> 8) & 0xFF] + list(data))
    time.sleep(0.001)

def commit_v1(dev):
    """Commit/finish write. Command byte 0x09."""
    _send(dev, [0x09] + [0x00]*63)
    time.sleep(0.1)

def flash_firmware_v1(dev, firmware, dry_run=False):
    """Flash firmware using the standard SONiX ISP HID protocol (v1 / 0x05-0x09 commands)."""
    start, end = firmware_range(firmware)
    # Round to page boundaries
    page_start = (start // PAGE_SIZE)
    page_end   = ((end + PAGE_SIZE - 1) // PAGE_SIZE)
    n_pages = page_end - page_start

    print(f"\n  Firmware: bytes 0x{start:04X}–0x{end:04X} ({end-start} bytes)")
    print(f"  Pages to flash: {page_start}–{page_end-1} ({n_pages} pages × {PAGE_SIZE} B)")

    if dry_run:
        print("  [DRY RUN] Skipping actual erase/write")
        return True

    # Step 1: Erase pages
    print(f"\n  Erasing {n_pages} pages...")
    for pg in range(page_start, page_end):
        erase_page_v1(dev, pg)
        sys.stdout.write(f"\r  Erased page {pg-page_start+1}/{n_pages}")
        sys.stdout.flush()
    print()

    # Step 2: Write 48-byte chunks
    total_chunks = (n_pages * PAGE_SIZE + CHUNK_SIZE - 1) // CHUNK_SIZE
    print(f"\n  Writing {total_chunks} chunks ({CHUNK_SIZE} bytes each)...")
    write_start = page_start * PAGE_SIZE
    write_end   = page_end   * PAGE_SIZE
    chunk_num = 0
    for offset in range(write_start, write_end, CHUNK_SIZE):
        chunk = bytes(firmware[offset:offset+CHUNK_SIZE])
        if len(chunk) < CHUNK_SIZE:
            chunk = chunk + b'\xFF' * (CHUNK_SIZE - len(chunk))
        write_chunk_v1(dev, chunk_num, chunk)
        chunk_num += 1
        sys.stdout.write(f"\r  Written chunk {chunk_num}/{total_chunks}")
        sys.stdout.flush()
    print()

    # Step 3: Commit
    print("  Committing...")
    commit_v1(dev)

    print("  Done! Keyboard should reset and run QMK firmware.")
    return True

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    p = argparse.ArgumentParser(description='Flash QMK firmware to RK71 via SONiX ISP')
    p.add_argument('--hex', default=DEFAULT_HEX,
                   help='Path to firmware .hex file (default: .build/rk_rk71_default.hex)')
    p.add_argument('--dry-run', action='store_true',
                   help='Detect device and parse firmware but do not write')
    p.add_argument('--list', action='store_true',
                   help='List all connected HID devices and exit')
    args = p.parse_args()

    if args.list:
        print("Connected HID devices:")
        for d in hid.enumerate():
            print(f"  VID=0x{d['vendor_id']:04X} PID=0x{d['product_id']:04X}  "
                  f"iface={d['interface_number']}  {d['product_string']!r}")
        return

    # --- Load firmware ---
    if not os.path.exists(args.hex):
        print(f"ERROR: Firmware file not found: {args.hex}")
        print(f"Looked for: {os.path.abspath(args.hex)}")
        sys.exit(1)

    print(f"Loading firmware: {args.hex}")
    firmware = load_hex(args.hex)
    start, end = firmware_range(firmware)
    print(f"  Firmware occupies 0x{start:04X}–0x{end:04X} ({end-start} bytes of {FLASH_SIZE} flash)")

    # --- Find ISP device ---
    print("\nSearching for keyboard in ISP mode...")
    print("(If not found: hold Esc, unplug keyboard, plug back in, then re-run this script)")
    path, vid, pid = find_isp_device()
    if path is None:
        print("\nNo ISP device found. All connected HID devices:")
        for d in hid.enumerate():
            print(f"  VID=0x{d['vendor_id']:04X} PID=0x{d['product_id']:04X}  "
                  f"iface={d['interface_number']}  {d['product_string']!r}")
        sys.exit(1)

    # --- Open and probe ---
    dev = hid.device()
    dev.open_path(path)
    protocol = probe_device(dev)
    print(f"  Protocol detected: {protocol}")

    if args.dry_run:
        print("\n[DRY RUN] Device found, firmware loaded. Would flash now.")
        dev.close()
        return

    # --- Flash ---
    print(f"\nFlashing firmware...")
    if protocol in ('sonix_v1', 'unknown'):
        ok = flash_firmware_v1(dev, firmware, dry_run=args.dry_run)
    else:
        print(f"WARNING: Unknown protocol '{protocol}', attempting v1 anyway")
        ok = flash_firmware_v1(dev, firmware, dry_run=args.dry_run)

    dev.close()

    if ok:
        print("\nFlash complete!")
        print("The keyboard should restart and appear as 'RK71' running QMK.")
        print("If the keyboard doesn't respond, try unplugging and replugging.")
    else:
        print("\nFlash FAILED. Check the output above for errors.")
        sys.exit(1)

if __name__ == '__main__':
    main()
