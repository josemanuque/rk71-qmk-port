# Bluetooth through the on-board ITON module. rk71_bt.c is a small SPI0-slave driver that
# works the way the stock firmware does (no pin-change interrupts, which would cost 512 bytes
# of RAM this 8 KB chip does not have); rk71_rgb.c holds the modes, keys and status lights.
BLUETOOTH_ENABLE = yes
BLUETOOTH_DRIVER = custom
SRC += rk71_bt.c
