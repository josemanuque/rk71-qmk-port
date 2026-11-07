# Archive: earlier attempt (do not use)

Kept for history only. This is the work of an earlier session that left the keyboard with dead keys and LEDs.

* `HANDOVER.md`, `ANALYSIS.md`: notes from that attempt. Several facts are wrong, including the GPIO register
  offsets, the peripheral addresses, the claim that the LEDs use an IS31FL driver, and the UART Bluetooth theory.
* `broken-qmk-port/rk71_as_flashed`: the QMK port that was actually flashed. Its matrix and LED pins were guessed, so
  nothing worked. `rk71_qmk_port_copy` is a slightly different copy of the same port.
* `scripts/`: ISP-trigger, HID-intercept, and flashing experiments.

The working port is `keyboard/rk71_rgb`. Its pins were decoded from the stock firmware.
