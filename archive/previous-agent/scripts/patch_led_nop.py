"""
Binary-patch rk_rk71_default.bin to NOP out rk71_led_flush and rk71_led_init.

Both functions conflict with the key matrix by toggling P3.4/5/6
(D4/D5/D6) for LED row control. These are the SAME pins used as
key matrix row strobes. Patching them to return immediately stops
the GPIO interference, allowing the key matrix to work.

Patch: replace first 2 bytes of each function with BX LR (0x70 0x47).
Addresses from rk_rk71_default.map:
  rk71_led_flush  @ 0x0618 (size 0xF0)
  rk71_led_init   @ 0x1A78 (size 0x58)
"""
import shutil, sys

BIN_IN  = r"C:\Users\<user>\Documents\rk71_mod\qmk_firmware\.build\rk_rk71_default.bin"
BIN_OUT = r"C:\Users\<user>\Documents\rk71_mod\qmk_firmware\.build\rk_rk71_noled.bin"
HEX_OUT = r"C:\Users\<user>\Documents\rk71_mod\qmk_firmware\.build\rk_rk71_noled.hex"

BX_LR = bytes([0x70, 0x47])  # ARM Thumb2: BX LR

PATCHES = [
    (0x0618, "rk71_led_flush"),
    (0x1A78, "rk71_led_init"),
]

with open(BIN_IN, 'rb') as f:
    data = bytearray(f.read())

print(f"Binary: {len(data)} bytes")

for offset, name in PATCHES:
    orig = bytes(data[offset:offset+2])
    data[offset:offset+2] = BX_LR
    print(f"Patched {name} @ 0x{offset:04X}: {orig.hex()} → {BX_LR.hex()}")

with open(BIN_OUT, 'wb') as f:
    f.write(data)
print(f"\nWrote patched binary: {BIN_OUT}")

# Convert .bin to Intel HEX for flash_qmk.py
def bin_to_hex(bin_data, out_path, base_addr=0):
    with open(out_path, 'w') as f:
        offset = 0
        while offset < len(bin_data):
            chunk = bin_data[offset:offset+16]
            byte_count = len(chunk)
            addr = base_addr + offset
            rec_type = 0x00
            checksum = (-(byte_count + ((addr >> 8) & 0xFF) + (addr & 0xFF) + rec_type + sum(chunk))) & 0xFF
            f.write(f":{byte_count:02X}{addr:04X}{rec_type:02X}{''.join(f'{b:02X}' for b in chunk)}{checksum:02X}\n")
            offset += 16
        f.write(":00000001FF\n")

bin_to_hex(data, HEX_OUT)
print(f"Wrote patched HEX:    {HEX_OUT}")
print()
print("Next steps:")
print("  1. Run OEM EXE, click Flash, wait for P key to light up")
print("  2. Run intercept_final.ps1 (kills EXE, starts flash_qmk.py)")
print("  3. Press Fn+P → ISP mode → flash_qmk.py flashes the patched firmware")
print()
print("After this flash: keys will work, LEDs will be dark until LED driver is fixed.")
