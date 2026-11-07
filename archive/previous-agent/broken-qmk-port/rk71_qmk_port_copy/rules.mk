# SONiX SN32F240B — 64 KB flash, ARM Cortex-M0
# RK71 RGB keyboard, firmware V1.12 reverse-engineered
MCU      = SN32F240B
BOOTLOADER = sn32-dfu

BOOTMAGIC_ENABLE  = yes    # hold Esc while plugging in to clear EEPROM
MOUSEKEY_ENABLE   = no
EXTRAKEY_ENABLE   = yes    # media / volume keys via Consumer HID
CONSOLE_ENABLE    = no
COMMAND_ENABLE    = no
NKRO_ENABLE       = no
BACKLIGHT_ENABLE  = no
AUDIO_ENABLE      = no
UNICODE_ENABLE    = no
BLUETOOTH_ENABLE  = no
RGBLIGHT_ENABLE       = no
RGB_MATRIX_ENABLE     = yes
RGB_MATRIX_CUSTOM_DRIVER = yes   # direct GPIO scan — see rk71_led.c

LTO_ENABLE = yes            # link-time optimisation to fit in 64 KB
