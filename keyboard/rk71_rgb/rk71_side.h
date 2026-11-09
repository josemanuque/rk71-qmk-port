// Copyright 2026 josemanuque
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

#include <stdbool.h>
#include <stdint.h>

/*
 * Side lights: 6 positions per side (1 = far end, 6 = near end), the same position lit on both
 * sides at once. Colour lines are shared, so all lit positions show the same colour.
 * Mapped with the diag keymap on the user's board (2026-11-09):
 *   colour (high = on):    D6 red, D4 green, D5 blue
 *   position (low = on):   B9 B10 B11 B12 C0 C1  = positions 1..6
 * The stock firmware turns them off before sleeping (colours low, positions high, @0x0220).
 */

/* Colours: bit 0 red, bit 1 green, bit 2 blue. */
#define SIDE_RED 1
#define SIDE_GREEN 2
#define SIDE_YELLOW 3
#define SIDE_BLUE 4
#define SIDE_MAGENTA 5
#define SIDE_CYAN 6
#define SIDE_WHITE 7

#define SIDE_ALL 0x3F /* positions mask: bit 0 = position 1 (far) … bit 5 = position 6 (near) */

void side_init(void);
void side_show(uint8_t positions, uint8_t colour); /* colour 0 or positions 0 = off */

/* Colour balance against the bluish diffuser: on-time of red, green, blue, 0..31 each. */
void side_set_tuning(uint8_t red, uint8_t green, uint8_t blue);
/* Overall brightness 0..255 (side-light brightness x keyboard brightness). */
void side_set_level(uint8_t level);

/* USB cable present (C15, high when the cable supplies power). Call vbus_task() from the main
 * loop; vbus_present() is debounced. */
void vbus_task(void);
bool vbus_present(void);
bool vbus_known(void);
