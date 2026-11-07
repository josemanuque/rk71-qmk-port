// Copyright 2026 josemanuque
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

/*
 * LED row pins, three per LED row in R, B, G order (the order the sn32f2xx driver expects).
 * Taken from stock firmware V1.12. Its LED step routine (0x5BFA) enables these pins together
 * with the red / blue / green brightness arrays at 0x20000962 / 0x20000B5A / 0x20000A5E.
 * This is the same pin set and order as royal_kludge/rk68_rgb (same HFD board family).
 *
 * Do NOT use C2 (P2.2): it is the BOOT pin. Driving it low as an LED output can force the
 * ROM bootloader on power-up (SN32F240B datasheet, section 1.4).
 */
#define SN32F2XX_RGB_MATRIX_ROW_PINS { C4, C5, C6, C7, C8, C9, C10, C11, C12, C13, C14, B13, D3, B15, B14 }

#define RGB_MATRIX_TYPING_HEATMAP_DECREASE_DELAY_MS 50

/* Out-of-the-box lighting: solid white. Only used when the settings storage is reset
 * (first boot or an EEPROM clear); saved settings take priority. */
#define RGB_MATRIX_DEFAULT_MODE RGB_MATRIX_SOLID_COLOR
#define RGB_MATRIX_DEFAULT_HUE 0
#define RGB_MATRIX_DEFAULT_SAT 0

/*
 * Bluetooth module link (decoded from stock firmware V1.12): SPI0 slave on A2-A5, plus
 * A0 = keyboard -> module "packet ready" and A1 = module -> keyboard "module is sending".
 */
#define RK71_BT_REQ_PIN A0
#define RK71_BT_DIR_PIN A1
