/* RK71 direct-GPIO RGB matrix driver — SN32F240B
 *
 * Reverse-engineered from firmware V1.12 at 0x5f7c-0x63c0.
 *
 * LED column GPIO (output, drive HIGH to illuminate):
 *   col 0 = P1.9  (ChibiOS B9)
 *   col 1 = P1.10 (ChibiOS B10)
 *   col 2 = P1.11 (ChibiOS B11)
 *   col 3 = P1.12 (ChibiOS B12)
 *   col 4 = P2.0  (ChibiOS C0)
 *   col 5 = P2.1  (ChibiOS C1)
 *
 * LED row GPIO (P3.4/5/6, ChibiOS D4/D5/D6):
 *   State0 (Red):   BCLR P3.6, TOG P3.4, TOG P3.5
 *   State1 (Green): TOG  P3.6, BCLR P3.4, TOG P3.5
 *   State2 (Blue):  TOG  P3.6, TOG  P3.4, BCLR P3.5
 *
 * PWM: 63 levels (0-62).  Sub-scan: 18 passes (slot[18] at 0x2000026e).
 *
 * Slot→LED mapping (18 slots per sub-scan pass):
 *   slot[0..5]   = Red   brightness for cols 0-5 of current row
 *   slot[6..11]  = Green brightness for cols 0-5 of current row
 *   slot[12..17] = Blue  brightness for cols 0-5 of current row
 *
 * The firmware updates the 18 slots from the full per-key RGB table before
 * each sub-scan pass.  This driver maintains a full RK71_LED_ROWS×6×3 table
 * in RAM and iterates through sub-scan rows.
 *
 * NOTE: exact slot[N] ↔ physical key mapping is UNCONFIRMED — verify on
 * hardware by lighting one LED at a time and noting which key it is.
 */

#include "quantum.h"
#include "rk71_led.h"
#include <string.h>

/* ------------------------------------------------------------------ */
/* SN32F240B GPIO register layout                                      */
/* P0=0x40044000  P1=0x40046000  P2=0x40048000  P3=0x4004a000         */
/* Each port: DATA+0x00, MODE+0x04, BSET+0x20, BCLR+0x24, TOG+0x28   */
/* ------------------------------------------------------------------ */
typedef volatile struct {
    uint32_t DATA;      /* 0x00 — read/write pin state  */
    uint32_t MODE;      /* 0x04 — 1=output, 0=input     */
    uint32_t _pad[6];
    uint32_t BSET;      /* 0x20 — write 1 to force HIGH */
    uint32_t BCLR;      /* 0x24 — write 1 to force LOW  */
    uint32_t TOG;       /* 0x28 — write 1 to toggle     */
} sn32_gpio_t;

#define SN32_P1  ((sn32_gpio_t *)0x40046000u)
#define SN32_P2  ((sn32_gpio_t *)0x40048000u)
#define SN32_P3  ((sn32_gpio_t *)0x4004a000u)

/* Column bit masks */
#define COL_P1_0   (1u << 9)   /* P1.9  */
#define COL_P1_1   (1u << 10)  /* P1.10 */
#define COL_P1_2   (1u << 11)  /* P1.11 */
#define COL_P1_3   (1u << 12)  /* P1.12 */
#define COL_P1_ALL (COL_P1_0 | COL_P1_1 | COL_P1_2 | COL_P1_3)

#define COL_P2_4   (1u << 0)   /* P2.0  */
#define COL_P2_5   (1u << 1)   /* P2.1  */
#define COL_P2_ALL (COL_P2_4 | COL_P2_5)

/* Row bit masks (P3) */
#define ROW_P3_4   (1u << 4)
#define ROW_P3_5   (1u << 5)
#define ROW_P3_6   (1u << 6)
#define ROW_P3_ALL (ROW_P3_4 | ROW_P3_5 | ROW_P3_6)

static const uint32_t p1_col_mask[4] = { COL_P1_0, COL_P1_1, COL_P1_2, COL_P1_3 };
static const uint32_t p2_col_mask[2] = { COL_P2_4, COL_P2_5 };

/* ------------------------------------------------------------------ */
/* Brightness table: [sub_row][col][rgb]                               */
/* sub_row cycles 0..RK71_SUB_ROWS-1 driven by sub_scan counter.      */
/* Values 0-63 (6-bit PWM matching firmware range).                   */
/* ------------------------------------------------------------------ */
#define RK71_LED_COLS    6
static uint8_t led_buf[RK71_SUB_ROWS][RK71_LED_COLS][3];  /* R=0,G=1,B=2 */

static uint8_t  pwm_counter  = 0;   /* 0-62 */
static uint8_t  sub_scan_row = 0;   /* 0..RK71_SUB_ROWS-1 */

/* ------------------------------------------------------------------ */
/* Drive 6 column channels for the given 6-element brightness array.  */
/* Columns start LOW (cleared before this call).                       */
/* Firmware uses TOG (0→1) for ON, BCLR (stays 0) for OFF.            */
/* ------------------------------------------------------------------ */
static inline void drive_cols(const uint8_t bright[6]) {
    uint32_t p1_on = 0, p1_off = 0;
    uint32_t p2_on = 0, p2_off = 0;

    for (int c = 0; c < 4; c++) {
        if (bright[c] > pwm_counter) p1_on  |= p1_col_mask[c];
        else                         p1_off |= p1_col_mask[c];
    }
    for (int c = 0; c < 2; c++) {
        if (bright[4 + c] > pwm_counter) p2_on  |= p2_col_mask[c];
        else                             p2_off |= p2_col_mask[c];
    }

    /* Columns were pre-cleared; TOG 0→1 turns them ON */
    if (p1_on)  SN32_P1->TOG  = p1_on;
    if (p1_off) SN32_P1->BCLR = p1_off;  /* redundant but matches firmware */
    if (p2_on)  SN32_P2->TOG  = p2_on;
    if (p2_off) SN32_P2->BCLR = p2_off;
}

/* ------------------------------------------------------------------ */
/* Driver API                                                          */
/* ------------------------------------------------------------------ */

void rk71_led_init(void) {
    /* Configure LED column pins as push-pull outputs, initially LOW */
    SN32_P1->MODE |= COL_P1_ALL;
    SN32_P1->BCLR  = COL_P1_ALL;

    SN32_P2->MODE |= COL_P2_ALL;
    SN32_P2->BCLR  = COL_P2_ALL;

    /* Configure LED row pins as push-pull outputs, initially LOW */
    SN32_P3->MODE |= ROW_P3_ALL;
    SN32_P3->BCLR  = ROW_P3_ALL;

    memset(led_buf, 0, sizeof(led_buf));
    pwm_counter  = 0;
    sub_scan_row = 0;
}

/* Called by QMK's RGB matrix task after set_color() calls.           */
/* One call = one complete R/G/B scan for the CURRENT sub-scan row.   */
/* Caller must call this frequently enough (~1 kHz) for smooth PWM.  */
void rk71_led_flush(void) {
    /* ---- Clear all column outputs before each state pass ---- */
    SN32_P1->BCLR = COL_P1_ALL;
    SN32_P2->BCLR = COL_P2_ALL;

    /* ---- State 0 (Red): BCLR P3.6, TOG P3.4, TOG P3.5 ---- */
    SN32_P3->BCLR = ROW_P3_6;
    SN32_P3->TOG  = ROW_P3_4;
    SN32_P3->TOG  = ROW_P3_5;
    {
        uint8_t bright[6];
        for (int c = 0; c < 6; c++) bright[c] = led_buf[sub_scan_row][c][0]; /* R */
        drive_cols(bright);
    }

    /* ---- Clear columns ---- */
    SN32_P1->BCLR = COL_P1_ALL;
    SN32_P2->BCLR = COL_P2_ALL;

    /* ---- State 1 (Green): TOG P3.6, BCLR P3.4, TOG P3.5 ---- */
    SN32_P3->TOG  = ROW_P3_6;
    SN32_P3->BCLR = ROW_P3_4;
    SN32_P3->TOG  = ROW_P3_5;
    {
        uint8_t bright[6];
        for (int c = 0; c < 6; c++) bright[c] = led_buf[sub_scan_row][c][1]; /* G */
        drive_cols(bright);
    }

    /* ---- Clear columns ---- */
    SN32_P1->BCLR = COL_P1_ALL;
    SN32_P2->BCLR = COL_P2_ALL;

    /* ---- State 2 (Blue): TOG P3.6, TOG P3.4, BCLR P3.5 ---- */
    SN32_P3->TOG  = ROW_P3_6;
    SN32_P3->TOG  = ROW_P3_4;
    SN32_P3->BCLR = ROW_P3_5;
    {
        uint8_t bright[6];
        for (int c = 0; c < 6; c++) bright[c] = led_buf[sub_scan_row][c][2]; /* B */
        drive_cols(bright);
    }

    /* ---- Advance PWM counter (0-62) ---- */
    if (++pwm_counter >= 63) {
        pwm_counter = 0;
        /* Advance sub-scan row every full PWM frame */
        if (++sub_scan_row >= RK71_SUB_ROWS) sub_scan_row = 0;
    }
}

/* index: QMK LED index (0-based).
 * Maps to led_buf[row][col] via RK71_LED_COLS = 6.
 * UNCONFIRMED: exact physical key ↔ index mapping needs hardware test.
 */
void rk71_led_set_color(int index, uint8_t r, uint8_t g, uint8_t b) {
    if ((unsigned)index >= RGB_MATRIX_LED_COUNT) return;
    int row = index / RK71_LED_COLS;
    int col = index % RK71_LED_COLS;
    if (row >= RK71_SUB_ROWS) return;
    /* Scale 8-bit (0-255) → 6-bit (0-62) for the 63-level PWM */
    led_buf[row][col][0] = (uint8_t)((r * 62u) / 255u);
    led_buf[row][col][1] = (uint8_t)((g * 62u) / 255u);
    led_buf[row][col][2] = (uint8_t)((b * 62u) / 255u);
}

void rk71_led_set_color_all(uint8_t r, uint8_t g, uint8_t b) {
    for (int i = 0; i < RGB_MATRIX_LED_COUNT; i++) {
        rk71_led_set_color(i, r, g, b);
    }
}

const rgb_matrix_driver_t rgb_matrix_driver = {
    .init          = rk71_led_init,
    .flush         = rk71_led_flush,
    .set_color     = rk71_led_set_color,
    .set_color_all = rk71_led_set_color_all,
};
