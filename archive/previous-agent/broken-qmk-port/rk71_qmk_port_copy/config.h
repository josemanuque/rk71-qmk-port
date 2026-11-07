#pragma once

/* Key matrix size */
#define MATRIX_ROWS 7
#define MATRIX_COLS 16

/*
 * GPIO pin assignments — derived from SN32F240B firmware disassembly (V1.12)
 *
 * ChibiOS port mapping:  A = GPIO_P0 (0x40044000)
 *                        B = GPIO_P1 (0x40046000)
 *                        C = GPIO_P2 (0x40048000)
 *                        D = GPIO_P3 (0x4004a000)
 *
 * ROW pins (drive low, active-low scan):
 *   Rows 0-3: D3-D6 = P3.3-P3.6  — CONFIRMED from LED row-select analysis
 *   Rows 4-6: A3-A5 = P0.3-P0.5  — GUESSED (P0.3-P0.5 are GPIO outputs per GPIO map)
 *   !! If row 4-6 keys misbehave, try swapping row 4-6 among A3/A4/A5/A6
 *
 * COL pins (input, pull-up, read low when key pressed):
 *   D0-D2   = P3.0-P3.2  — CONFIRMED inputs from GPIO direction map
 *   D7-D15  = P3.7-P3.15 — CONFIRMED inputs
 *   A1,A2   = P0.1,P0.2  — CONFIRMED inputs
 *   A15     = P0.15      — CONFIRMED input
 *   C15     = P2.15      — CONFIRMED input
 *
 * Column ORDER (which pin = which physical column) is UNCONFIRMED.
 * The 16 column pins are listed in the order above; physical left→right column
 * ordering may differ.  Expect transposed keys until verified on hardware.
 * See ANALYSIS.md for full GPIO direction register analysis.
 */

/* RGB matrix — 18 sub-rows × 6 cols = 108 potential slots.
 * We expose 72 as the LED count (12 rows × 6 cols ≈ 71 keys + 1 status).
 * UNCONFIRMED: exact slot ↔ physical key mapping needs hardware testing.
 * To test: set all LEDs to red, then step through indices one-by-one to
 * identify which physical key each LED index corresponds to.
 */
#define RGB_MATRIX_LED_COUNT      72
#define RGB_MATRIX_MAXIMUM_BRIGHTNESS  255
#define RGB_MATRIX_HUE_STEP       8
#define RGB_MATRIX_SAT_STEP       8
#define RGB_MATRIX_VAL_STEP       8
#define RGB_MATRIX_SPD_STEP       8
/* Only enable effects that don't need a per-key LED map (until map is confirmed) */
#define RGB_MATRIX_DEFAULT_MODE   RGB_MATRIX_SOLID_COLOR
#define RGB_MATRIX_DEFAULT_HUE    0
#define RGB_MATRIX_DEFAULT_SAT    255
#define RGB_MATRIX_DEFAULT_VAL    128
#define RGB_MATRIX_STARTUP_MODE   RGB_MATRIX_SOLID_COLOR

/* Encoder, tap-dance, combo not needed */
#define NO_ACTION_TAPPING
#define NO_ACTION_COMBO

/* Use 8-bit layer state (up to 8 layers) */
#define LAYER_STATE_8BIT

/* Debounce: 5 ms is standard; increase if keys chatter */
#define DEBOUNCE 5

/* USB polling interval: 1 ms for minimal latency */
#define USB_POLLING_INTERVAL_MS 1
