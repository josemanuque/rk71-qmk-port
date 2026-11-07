# RK71 Bluetooth link — SN32 ↔ BT module

Reverse-engineered from the stock firmware `rk71_fw.bin` (V1.12) on 2026-11-06, using
static disassembly only. Register meanings were checked against the SN32F240B datasheet v2.4.
Nothing here has been confirmed on the live board yet. See "Not yet confirmed" at the bottom.

## Physical link

| Item | Value | Evidence |
|---|---|---|
| Bus | **SPI0**, not UART. The firmware never touches UART0/1/2 or I2C0. | Only SPI0 (0x4001C000) is referenced. |
| Role | **SN32 = SPI slave**, BT module = master (drives SCK) | init @0x68B0: CTRL0.MS = 1 |
| Format | 8-bit frames, mode 0 (CPOL=0, CPHA=0), MSB first, hardware SEL | CTRL0.DL = 7, CTRL1 = 0 |
| Pins (datasheet) | P0.2 MISO0, P0.3 MOSI0, P0.4 SCK0, P0.5 SEL0 | LQFP64 pin table |
| RX handling | IRQ 6 (SPI0), RX-FIFO-threshold interrupt | handler @0x5866 |
| **P0.0** (output) | SN32 → module "I have a packet" request. Set high to start a send, cleared when done or on timeout. | BSET/BCLR on GPIO0 bit 0 |
| **P0.1** (input) | Direction. High = module is sending to SN32; low = SN32 may send. | ISR branches on GPIO0 bit 1 |

GPIO register offsets (datasheet): DATA 0x00, MODE 0x04, BSET **0x24**, BCLR **0x28**.
(ANALYSIS.md lists BSET 0x20 / BCLR 0x24 / TOGGLE 0x28, which is wrong.)

## Send sequence (SN32 → module)

1. Proceed only if P0.1 is low and the previous send has finished (`0x200001CF` = 1).
2. Set P0.0 high.
3. Fill the TX buffer (`0x20000368`, one halfword per byte) with the header and payload, and set the length (`0x200001C3`).
4. Wait for SPI not busy, reset the SPI FIFO, preload the first byte into SPI DATA.
5. The master clocks the bytes out. The ISR feeds the next byte on each RX interrupt.
6. After the last byte, the ISR clears P0.0 and marks the send as done.
7. Timeout: a 200-tick countdown (`0x200001D0`, routine @0x5816) forces the send to finish.

## Packets SN32 → module

| Header | Payload | Meaning (inferred) | Source buffer | Builder |
|---|---|---|---|---|
| `A1` | 8 bytes | Boot keyboard report: mods, reserved, 6 keys | 0x2000015E | @0x5180 |
| `A2` | 15 bytes | NKRO key bitmap (120 bits) | 0x20000318 | @0x520E |
| `A3` | 2 bytes | Consumer usage, 16-bit (media keys) | 0x20000166 | @0x529A |
| `A4` | 1 byte | System control (power/sleep) | 0x20000169 | @0x531C |
| `A6` | 2 bytes | Control command (see below) | 0x200001C1 | several |

### `A6` control commands

| Bytes | Sent from | Likely meaning |
|---|---|---|
| `51 81` … `51 85` | 0x56CA–0x571A, and key handlers @0x2948, 0x37DA… | Select BT host/channel 1–5. The value is picked from bitmask `0x20000175` (1, 2, 4, 8, 16). |
| `51 89` | @0x04A8, @0x0646 | Sent at startup or mode change. Possibly "enter BT mode" or wake. |
| `51 70` | @0x57A2 | Unknown. Possibly start pairing or clear pairings. |
| `58 01` | @0x5638 | Unknown. Possibly sleep, power, or battery related. |

## Packets module → SN32 (parser @0x5410)

| Bytes | Effect in firmware | Likely meaning |
|---|---|---|
| `B1 xx` | Low 3 bits stored to `0x200002B0` | Host LED state (Num/Caps/Scroll Lock) |
| `B6 5A 06` | Starts timers (600 / 300 ticks), calls 0x5138 | Status event, e.g. pairing started |
| `B6 5A 07` | Sets flag `0x20000240` = 1, timer 50 | Status event, e.g. disconnected |
| `B6 5A 0A` | Clears `0x200001DC`, `0x200001E4`, `0x20000240` | Status event, e.g. connected |
| `B6 51 76` / `77` / `78` | Clear pending-command flags | Acknowledgements of `A6 51 xx` commands |

## What this means for QMK

The protocol is small, which makes a QMK Bluetooth driver realistic:
- an SPI0-slave driver with the IRQ 6 handler
- the P0.0/P0.1 handshake
- `A1`/`A3`/`A4` packets mapped to QMK's keyboard, consumer and system reports
- `B1` parsed for the Caps Lock LED
- `A6 51 8x` for host switching

## Not yet confirmed

- What `51 89`, `51 70`, `58 01` and the `B6 5A xx` events mean.
- How the module is powered or reset, and how the wired/BT slide switch (K3) is read.
- Battery reporting.
- Whether P0.15 (configured as an input) is involved.

To confirm all of this, capture P0.0–P0.5 with a cheap 8-channel logic analyzer while pairing,
typing, switching hosts and toggling Caps Lock in Bluetooth mode.
