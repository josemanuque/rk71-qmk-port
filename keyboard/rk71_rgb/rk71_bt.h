// Copyright 2026 josemanuque
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

#include <stdbool.h>
#include <stdint.h>

/*
 * Low-level link to the RK71's ITON Bluetooth module (SPI0, keyboard = slave).
 *
 * Packets keyboard -> module: A1 boot keyboard report (8), A2 NKRO bitmap (15), A3 consumer (2),
 * A6 command (2). Packets module -> keyboard: B1 host LEDs (1), B6 event (2).
 */

void rk71_bt_init(void);

/* Queue one packet. Returns false (packet dropped) if the module did not take the previous
 * packet within a few milliseconds, e.g. because it is switched off. Never blocks for long. */
bool rk71_bt_send(const uint8_t *data, uint8_t len);

/* Call from the main loop: hands complete incoming packets to rk71_bt_received(). */
void rk71_bt_task(void);

/* Implemented by the keyboard code. */
void rk71_bt_received(const uint8_t *packet, uint8_t len);
