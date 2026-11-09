// Copyright 2026 josemanuque
// SPDX-License-Identifier: GPL-2.0-or-later
//
// DIAGNOSTIC keymap: find out what drives the red battery LED (LDV1) and whether the charger
// status reaches the MCU. Not for daily use; flash the via keymap back afterwards.
//
// All per-key RGB is blanked except:
//   Number row 1..8   = live level of an unknown INPUT pin (green = high, red = low):
//                       1:C15 2:D0 3:D1 4:D2 5:D12 6:D13 7:D14 8:D15
//   Q W E R T Y U I O P [  = unknown OUTPUT pins (blue = driven high, yellow = driven low):
//                       Q:B8 W:B9 E:B10 R:B11 T:B12 Y:C0 U:C1 I:C3 O:D4 P:D5 [:D6
//   Fn + that key toggles the pin. At boot they are set the way the stock firmware sets them
//   (B8-B11 high, everything else low).
// Typing works normally; Fn + Pause enters the bootloader for reflashing.
#include QMK_KEYBOARD_H

static const pin_t inputs[]  = {C15, D0, D1, D2, D12, D13, D14, D15};
static const pin_t outputs[] = {B8, B9, B10, B11, B12, C0, C1, C3, D4, D5, D6};
static bool        out_high[] = {1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0};

#define N_IN (sizeof(inputs) / sizeof(inputs[0]))
#define N_OUT (sizeof(outputs) / sizeof(outputs[0]))

enum { DG_T0 = SAFE_RANGE }; /* DG_T0 + i toggles outputs[i] */

const uint16_t PROGMEM keymaps[][MATRIX_ROWS][MATRIX_COLS] = {
    [0] = LAYOUT(
        KC_ESC,  KC_1,    KC_2,    KC_3,    KC_4,    KC_5,    KC_6,    KC_7,    KC_8,    KC_9,    KC_0,    KC_MINS, KC_EQL,  KC_BSPC,          KC_INS,  KC_HOME,
        KC_TAB,  KC_Q,    KC_W,    KC_E,    KC_R,    KC_T,    KC_Y,    KC_U,    KC_I,    KC_O,    KC_P,    KC_LBRC, KC_RBRC, KC_BSLS,          KC_DEL,  KC_END,
        KC_CAPS, KC_A,    KC_S,    KC_D,    KC_F,    KC_G,    KC_H,    KC_J,    KC_K,    KC_L,    KC_SCLN, KC_QUOT,          KC_ENT,           KC_PAUS, KC_PGUP,
        KC_LSFT,          KC_Z,    KC_X,    KC_C,    KC_V,    KC_B,    KC_N,    KC_M,    KC_COMM, KC_DOT,  KC_SLSH,          KC_RSFT,          KC_UP,   KC_PGDN,
        KC_LCTL, KC_LGUI, KC_LALT,                            KC_SPC,                    KC_RALT, MO(1),   KC_RCTL,          KC_LEFT,          KC_DOWN, KC_RGHT
    ),
    [1] = LAYOUT(
        _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______,          _______, _______,
        _______, DG_T0+0, DG_T0+1, DG_T0+2, DG_T0+3, DG_T0+4, DG_T0+5, DG_T0+6, DG_T0+7, DG_T0+8, DG_T0+9, DG_T0+10,_______, _______,          _______, _______,
        _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______,          _______,          QK_BOOT, _______,
        _______,          _______, _______, _______, _______, _______, _______, _______, _______, _______, _______,          _______,          _______, _______,
        _______, _______, _______,                            _______,                   _______, _______, _______,          _______,          _______, _______
    ),
};

static void drive(uint8_t i) {
    gpio_set_pin_output(outputs[i]);
    gpio_write_pin(outputs[i], out_high[i]);
}

void keyboard_post_init_user(void) {
    for (uint8_t i = 0; i < N_IN; i++) gpio_set_pin_input(inputs[i]); /* no pull: read the real level */
    for (uint8_t i = 0; i < N_OUT; i++) drive(i);
}

bool process_record_user(uint16_t keycode, keyrecord_t *record) {
    if (keycode >= DG_T0 && keycode < DG_T0 + N_OUT) {
        if (record->event.pressed) {
            uint8_t i   = keycode - DG_T0;
            out_high[i] = !out_high[i];
            drive(i);
        }
        return false;
    }
    return true;
}

static void set_key(uint8_t row, uint8_t col, uint8_t r, uint8_t g, uint8_t b, uint8_t led_min, uint8_t led_max) {
    uint8_t led = g_led_config.matrix_co[row][col];
    if (led != NO_LED && led >= led_min && led < led_max) rgb_matrix_set_color(led, r, g, b);
}

bool rgb_matrix_indicators_advanced_user(uint8_t led_min, uint8_t led_max) {
    for (uint8_t i = led_min; i < led_max; i++) rgb_matrix_set_color(i, 0, 0, 0);
    for (uint8_t i = 0; i < N_IN; i++) {
        if (gpio_read_pin(inputs[i])) {
            set_key(0, 1 + i, 0, 255, 0, led_min, led_max);
        } else {
            set_key(0, 1 + i, 255, 0, 0, led_min, led_max);
        }
    }
    for (uint8_t i = 0; i < N_OUT; i++) {
        if (out_high[i]) {
            set_key(1, 1 + i, 0, 0, 255, led_min, led_max);
        } else {
            set_key(1, 1 + i, 255, 160, 0, led_min, led_max);
        }
    }
    return true;
}
