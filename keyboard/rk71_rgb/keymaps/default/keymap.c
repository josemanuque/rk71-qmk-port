// Copyright 2026 josemanuque
// SPDX-License-Identifier: GPL-2.0-or-later
#include QMK_KEYBOARD_H

enum layers { WIN_BASE, MAC_BASE, WIN_FN, MAC_FN };

/*
 * Base layer (Windows)
 * ┌───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───────┬───┬───┐
 * │Esc│ 1 │ 2 │ 3 │ 4 │ 5 │ 6 │ 7 │ 8 │ 9 │ 0 │ - │ = │ Bksp  │Ins│Hom│
 * ├───┴─┬─┴─┬─┴─┬─┴─┬─┴─┬─┴─┬─┴─┬─┴─┬─┴─┬─┴─┬─┴─┬─┴─┬─┴─┬─────┼───┼───┤
 * │ Tab │ Q │ W │ E │ R │ T │ Y │ U │ I │ O │ P │ [ │ ] │  \  │Del│End│
 * ├─────┴┬──┴┬──┴┬──┴┬──┴┬──┴┬──┴┬──┴┬──┴┬──┴┬──┴┬──┴┬──┴─────┼───┼───┤
 * │ Caps │ A │ S │ D │ F │ G │ H │ J │ K │ L │ ; │ ' │  Enter │Pse│PgU│
 * ├──────┴─┬─┴─┬─┴─┬─┴─┬─┴─┬─┴─┬─┴─┬─┴─┬─┴─┬─┴─┬─┴─┬─┴────────┼───┼───┤
 * │ Shift  │ Z │ X │ C │ V │ B │ N │ M │ , │ . │ / │  Shift   │ ↑ │PgD│
 * ├────┬───┴┬──┴─┬─┴───┴───┴───┴───┴───┴───┴┬──┴─┬─┴──┬────┬──┼───┼───┤
 * │Ctrl│Win │Alt │         Space            │Alt │ Fn │Ctrl│ ←│ ↓ │ → │
 * └────┴────┴────┴──────────────────────────┴────┴────┴────┴──┴───┴───┘
 * Esc is QK_GESC (Grave Escape):
 *   Esc on its own → Esc
 *   Shift+Esc      → ~
 *   Cmd/Win+Esc    → Cmd/Win+`   (macOS "next window of this app")
 */
const uint16_t PROGMEM keymaps[][MATRIX_ROWS][MATRIX_COLS] = {
    [WIN_BASE] = LAYOUT(
        QK_GESC, KC_1,    KC_2,    KC_3,    KC_4,    KC_5,    KC_6,    KC_7,    KC_8,    KC_9,    KC_0,    KC_MINS, KC_EQL,  KC_BSPC,          KC_INS,  KC_HOME,
        KC_TAB,  KC_Q,    KC_W,    KC_E,    KC_R,    KC_T,    KC_Y,    KC_U,    KC_I,    KC_O,    KC_P,    KC_LBRC, KC_RBRC, KC_BSLS,          KC_DEL,  KC_END,
        KC_CAPS, KC_A,    KC_S,    KC_D,    KC_F,    KC_G,    KC_H,    KC_J,    KC_K,    KC_L,    KC_SCLN, KC_QUOT,          KC_ENT,           KC_PAUS, KC_PGUP,
        KC_LSFT,          KC_Z,    KC_X,    KC_C,    KC_V,    KC_B,    KC_N,    KC_M,    KC_COMM, KC_DOT,  KC_SLSH,          KC_RSFT,          KC_UP,   KC_PGDN,
        KC_LCTL, KC_LGUI, KC_LALT,                            KC_SPC,                    KC_RALT, MO(WIN_FN), KC_RCTL,   KC_LEFT,          KC_DOWN, KC_RGHT
    ),
    /* Mac: the key next to Space is Cmd, the next one out is Option. */
    [MAC_BASE] = LAYOUT(
        QK_GESC, KC_1,    KC_2,    KC_3,    KC_4,    KC_5,    KC_6,    KC_7,    KC_8,    KC_9,    KC_0,    KC_MINS, KC_EQL,  KC_BSPC,          KC_INS,  KC_HOME,
        KC_TAB,  KC_Q,    KC_W,    KC_E,    KC_R,    KC_T,    KC_Y,    KC_U,    KC_I,    KC_O,    KC_P,    KC_LBRC, KC_RBRC, KC_BSLS,          KC_DEL,  KC_END,
        KC_CAPS, KC_A,    KC_S,    KC_D,    KC_F,    KC_G,    KC_H,    KC_J,    KC_K,    KC_L,    KC_SCLN, KC_QUOT,          KC_ENT,           KC_PAUS, KC_PGUP,
        KC_LSFT,          KC_Z,    KC_X,    KC_C,    KC_V,    KC_B,    KC_N,    KC_M,    KC_COMM, KC_DOT,  KC_SLSH,          KC_RSFT,          KC_UP,   KC_PGDN,
        KC_LCTL, KC_LALT, KC_LGUI,                            KC_SPC,                    KC_RGUI, MO(MAC_FN), KC_RALT,   KC_LEFT,          KC_DOWN, KC_RGHT
    ),
    /*
     * Fn layer
     * Fn + 1…=          → F1…F12        Fn + Esc   → `
     * Fn + Ins / Home   → PrtSc / Prev track
     * Fn + Del / End    → Play-Pause / Next track
     * Fn + PgUp / PgDn  → Volume up / down          Fn + M → Mute
     * Fn + Enter        → RGB on/off    Fn + \ → next RGB effect   Fn + H → hue
     * Fn + ↑ / ↓        → RGB brighter / dimmer
     * Fn + ← / →        → RGB effect slower / faster
     * Fn + Win          → Mac mode      Fn + Alt → Windows mode    (saved across power cycles)
     * Fn + Pause        → bootloader (for reflashing)
     */
    [WIN_FN] = LAYOUT(
        KC_GRV,  KC_F1,   KC_F2,   KC_F3,   KC_F4,   KC_F5,   KC_F6,   KC_F7,   KC_F8,   KC_F9,   KC_F10,  KC_F11,  KC_F12,  _______,          KC_PSCR, KC_MPRV,
        _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, RM_NEXT,          KC_MPLY, KC_MNXT,
        _______, _______, _______, _______, _______, _______, RM_HUEU, _______, _______, _______, _______, _______,          RM_TOGG,          QK_BOOT, KC_VOLU,
        _______,          _______, _______, _______, _______, _______, _______, KC_MUTE, _______, _______, _______,          _______,          RM_VALU, KC_VOLD,
        _______, PDF(MAC_BASE), PDF(WIN_BASE),                _______,                   _______, _______, _______,          RM_SPDD,          RM_VALD, RM_SPDU
    ),
    [MAC_FN] = LAYOUT(
        KC_GRV,  KC_F1,   KC_F2,   KC_F3,   KC_F4,   KC_F5,   KC_F6,   KC_F7,   KC_F8,   KC_F9,   KC_F10,  KC_F11,  KC_F12,  _______,          KC_PSCR, KC_MPRV,
        _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, RM_NEXT,          KC_MPLY, KC_MNXT,
        _______, _______, _______, _______, _______, _______, RM_HUEU, _______, _______, _______, _______, _______,          RM_TOGG,          QK_BOOT, KC_VOLU,
        _______,          _______, _______, _______, _______, _______, _______, KC_MUTE, _______, _______, _______,          _______,          RM_VALU, KC_VOLD,
        _______, PDF(MAC_BASE), PDF(WIN_BASE),                _______,                   _______, _______, _______,          RM_SPDD,          RM_VALD, RM_SPDU
    ),
};

/* Caps Lock indicator: light the Caps key white while Caps Lock is on. */
bool rgb_matrix_indicators_advanced_user(uint8_t led_min, uint8_t led_max) {
    if (host_keyboard_led_state().caps_lock) {
        uint8_t led = g_led_config.matrix_co[2][0];
        if (led != NO_LED && led >= led_min && led < led_max) {
            rgb_matrix_set_color(led, RGB_WHITE);
        }
    }
    return false;
}
