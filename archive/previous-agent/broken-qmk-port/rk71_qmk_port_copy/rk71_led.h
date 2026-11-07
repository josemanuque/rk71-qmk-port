#pragma once

/* Number of sub-scan rows (slot[18] cycles 0-17 in original firmware).
 * 18 rows × 6 cols = 108 potential LED positions.
 * For the RK71 (71 keys + status LEDs), only a subset is populated.
 * UNCONFIRMED — may need adjustment after hardware testing.
 */
#define RK71_SUB_ROWS  18

void rk71_led_init(void);
void rk71_led_flush(void);
void rk71_led_set_color(int index, uint8_t r, uint8_t g, uint8_t b);
void rk71_led_set_color_all(uint8_t r, uint8_t g, uint8_t b);
