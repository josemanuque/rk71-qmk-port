/* RK71 LED position map — g_led_config
 *
 * 72 LEDs = 12 sub-scan rows × 6 GPIO columns.
 * Physical coordinates: x ∈ [0,224], y ∈ [0,64] (QMK normalised range).
 *
 * !! KEY-TO-LED MAPPING IS UNCONFIRMED !!
 * The matrix[][] table below uses NO_LED for every key position until
 * hardware testing can determine the actual slot→key correspondence.
 * To calibrate: flash this firmware, run rgb_matrix_set_color_all(0,0,0),
 * then light one LED index at a time and note which physical key it is.
 *
 * LED index assignment: row-major order over 12 LED rows × 6 LED cols.
 *   index = sub_scan_row * 6 + col
 * Physical position: evenly spaced grid spread across the keyboard area.
 */

#include "quantum.h"

#ifdef RGB_MATRIX_ENABLE

/* Convenience: 16 × NO_LED for one full key-matrix row */
#define NL NO_LED
#define ROW_NL { NL,NL,NL,NL,NL,NL,NL,NL,NL,NL,NL,NL,NL,NL,NL,NL }

/* Evenly-spaced LED x positions across the keyboard width (0-224).
 * col 0 = leftmost, col 5 = rightmost of each sub-scan row.
 */
#define LX0   0
#define LX1  45
#define LX2  90
#define LX3 135
#define LX4 180
#define LX5 224

/* 12 LED rows at equal y steps across 0-63 */
#define LY0   0
#define LY1   6
#define LY2  12
#define LY3  18
#define LY4  24
#define LY5  30
#define LY6  36
#define LY7  42
#define LY8  48
#define LY9  53
#define LY10 59
#define LY11 63

/* Helper: one LED row (6 entries at a given y) */
#define LED_ROW(y) {LX0,(y)},{LX1,(y)},{LX2,(y)},{LX3,(y)},{LX4,(y)},{LX5,(y)}

led_config_t g_led_config = {
    /* Key matrix row→col → LED index (all NO_LED until mapping is confirmed) */
    {
        ROW_NL,  /* key row 0 */
        ROW_NL,  /* key row 1 */
        ROW_NL,  /* key row 2 */
        ROW_NL,  /* key row 3 */
        ROW_NL,  /* key row 4 */
        ROW_NL,  /* key row 5 */
        ROW_NL,  /* key row 6 */
    },

    /* LED physical positions — 72 entries */
    {
        LED_ROW(LY0),
        LED_ROW(LY1),
        LED_ROW(LY2),
        LED_ROW(LY3),
        LED_ROW(LY4),
        LED_ROW(LY5),
        LED_ROW(LY6),
        LED_ROW(LY7),
        LED_ROW(LY8),
        LED_ROW(LY9),
        LED_ROW(LY10),
        LED_ROW(LY11),
    },

    /* LED flags — all keys (backlight), not underglow */
    {
        LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT,
        LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT,  /* row 0 */
        LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT,
        LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT,  /* row 1 */
        LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT,
        LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT,  /* row 2 */
        LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT,
        LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT,  /* row 3 */
        LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT,
        LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT,  /* row 4 */
        LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT,
        LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT,  /* row 5 */
        LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT,
        LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT,  /* row 6 */
        LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT,
        LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT,  /* row 7 */
        LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT,
        LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT,  /* row 8 */
        LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT,
        LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT,  /* row 9 */
        LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT,
        LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT,  /* row 10 */
        LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT,
        LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT,  /* row 11 */
    },
};

#undef NL
#undef ROW_NL
#undef LX0
#undef LX1
#undef LX2
#undef LX3
#undef LX4
#undef LX5
#undef LY0
#undef LY1
#undef LY2
#undef LY3
#undef LY4
#undef LY5
#undef LY6
#undef LY7
#undef LY8
#undef LY9
#undef LY10
#undef LY11
#undef LED_ROW

#endif /* RGB_MATRIX_ENABLE */
