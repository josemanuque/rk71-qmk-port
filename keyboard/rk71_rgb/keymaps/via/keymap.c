// Copyright 2026 josemanuque
// SPDX-License-Identifier: GPL-2.0-or-later
#include QMK_KEYBOARD_H

/*
 * Layers (5 in total, the most that fits the 1 KB of storage alongside VIA macros):
 *   WIN_BASE / MAC_BASE  default layers, switched with Fn+Win / Fn+Alt and remembered
 *   FROW                 F-row lock: 1…= send F1…F12. Toggled with Fn+Ctrl and remembered
 *   FN                   held with Fn
 *   FMEDIA               turns on automatically while FROW and FN are both active: Fn+F-key = media
 */
enum layers { WIN_BASE, MAC_BASE, FROW, FN, FMEDIA };

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
 * Esc is QK_GESC (Grave Escape): Esc / Shift+Esc → ~ / Cmd(Win)+Esc → Cmd(Win)+`
 */
const uint16_t PROGMEM keymaps[][MATRIX_ROWS][MATRIX_COLS] = {
    [WIN_BASE] = LAYOUT(
        QK_GESC, KC_1,    KC_2,    KC_3,    KC_4,    KC_5,    KC_6,    KC_7,    KC_8,    KC_9,    KC_0,    KC_MINS, KC_EQL,  KC_BSPC,          KC_INS,  KC_HOME,
        KC_TAB,  KC_Q,    KC_W,    KC_E,    KC_R,    KC_T,    KC_Y,    KC_U,    KC_I,    KC_O,    KC_P,    KC_LBRC, KC_RBRC, KC_BSLS,          KC_DEL,  KC_END,
        KC_CAPS, KC_A,    KC_S,    KC_D,    KC_F,    KC_G,    KC_H,    KC_J,    KC_K,    KC_L,    KC_SCLN, KC_QUOT,          KC_ENT,           KC_PAUS, KC_PGUP,
        KC_LSFT,          KC_Z,    KC_X,    KC_C,    KC_V,    KC_B,    KC_N,    KC_M,    KC_COMM, KC_DOT,  KC_SLSH,          KC_RSFT,          KC_UP,   KC_PGDN,
        KC_LCTL, KC_LGUI, KC_LALT,                            KC_SPC,                    KC_RALT, MO(FN),  KC_RCTL,          KC_LEFT,          KC_DOWN, KC_RGHT
    ),
    /* Mac: the key next to Space is Cmd, the next one out is Option. */
    [MAC_BASE] = LAYOUT(
        QK_GESC, KC_1,    KC_2,    KC_3,    KC_4,    KC_5,    KC_6,    KC_7,    KC_8,    KC_9,    KC_0,    KC_MINS, KC_EQL,  KC_BSPC,          KC_INS,  KC_HOME,
        KC_TAB,  KC_Q,    KC_W,    KC_E,    KC_R,    KC_T,    KC_Y,    KC_U,    KC_I,    KC_O,    KC_P,    KC_LBRC, KC_RBRC, KC_BSLS,          KC_DEL,  KC_END,
        KC_CAPS, KC_A,    KC_S,    KC_D,    KC_F,    KC_G,    KC_H,    KC_J,    KC_K,    KC_L,    KC_SCLN, KC_QUOT,          KC_ENT,           KC_PAUS, KC_PGUP,
        KC_LSFT,          KC_Z,    KC_X,    KC_C,    KC_V,    KC_B,    KC_N,    KC_M,    KC_COMM, KC_DOT,  KC_SLSH,          KC_RSFT,          KC_UP,   KC_PGDN,
        KC_LCTL, KC_LALT, KC_LGUI,                            KC_SPC,                    KC_RGUI, MO(FN),  KC_RALT,          KC_LEFT,          KC_DOWN, KC_RGHT
    ),
    /* F-row lock: the number row becomes F1…F12 (Fn+Ctrl toggles it). */
    [FROW] = LAYOUT(
        _______, KC_F1,   KC_F2,   KC_F3,   KC_F4,   KC_F5,   KC_F6,   KC_F7,   KC_F8,   KC_F9,   KC_F10,  KC_F11,  KC_F12,  _______,          _______, _______,
        _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______,          _______, _______,
        _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______,          _______,          _______, _______,
        _______,          _______, _______, _______, _______, _______, _______, _______, _______, _______, _______,          _______,          _______, _______,
        _______, _______, _______,                            _______,                   _______, _______, _______,          _______,          _______, _______
    ),
    /*
     * Fn layer
     * Fn + 1…=          → F1…F12        Fn + Esc   → `
     * Fn + Ctrl         → toggle F-row lock (Fn key glows orange while it is on)
     * Fn + Ins / Home   → PrtSc / Prev track
     * Fn + Del / End    → Play-Pause / Next track
     * Fn + PgUp / PgDn  → Volume up / down          Fn + M → Mute
     * Fn + Enter        → RGB on/off    Fn + \ → next RGB effect   Fn + H → hue
     * Fn + ↑ / ↓        → RGB brighter / dimmer
     * Fn + ← / →        → RGB effect slower / faster
     * Fn + Win          → Mac mode      Fn + Alt → Windows mode    (remembered)
     * Fn + Pause        → bootloader (for reflashing)
 * Bluetooth (same keys as the stock firmware):
 * Fn + Q/W/E/R/T    → Bluetooth device 1–5;  hold 3 s → pair a new device in that slot
 * Fn + P            → switch wired / Bluetooth;  hold 3 s → pair the current slot
 * Fn + Backspace    → hold 3 s → forget all paired devices
     * (Win/Alt here are the physical keys, so these combos work the same in both modes.)
     */
    [FN] = LAYOUT(
        KC_GRV,  KC_F1,   KC_F2,   KC_F3,   KC_F4,   KC_F5,   KC_F6,   KC_F7,   KC_F8,   KC_F9,   KC_F10,  KC_F11,  KC_F12,  BT_CLR,           KC_PSCR, KC_MPRV,
        _______, BT_HST1, BT_HST2, BT_HST3, BT_HST4, BT_HST5, _______, _______, _______, _______, BT_MODE, _______, _______, RM_NEXT,          KC_MPLY, KC_MNXT,
        _______, _______, _______, _______, _______, _______, RM_HUEU, _______, _______, _______, _______, _______,          RM_TOGG,          QK_BOOT, KC_VOLU,
        _______,          _______, _______, _______, _______, _______, _______, KC_MUTE, _______, _______, _______,          _______,          RM_VALU, KC_VOLD,
        TG(FROW), PDF(MAC_BASE), PDF(WIN_BASE),               _______,                   _______, _______, TG(FROW),         RM_SPDD,          RM_VALD, RM_SPDU
    ),
    /*
     * Media on the F-row, active only while the F-row lock is on and Fn is held.
     * F1/F2 screen brightness, F4 prev, F5 play/pause, F6 next, F7 mute, F8/F9 volume.
     */
    [FMEDIA] = LAYOUT(
        _______, KC_BRID, KC_BRIU, _______, KC_MPRV, KC_MPLY, KC_MNXT, KC_MUTE, KC_VOLD, KC_VOLU, _______, _______, _______, _______,          _______, _______,
        _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______,          _______, _______,
        _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______,          _______,          _______, _______,
        _______,          _______, _______, _______, _______, _______, _______, _______, _______, _______, _______,          _______,          _______, _______,
        _______, _______, _______,                            _______,                   _______, _______, _______,          _______,          _______, _______
    ),
};

/* The F-row lock is kept in the user EEPROM slot so it survives unplugging. */
typedef union {
    uint32_t raw;
    struct {
        bool frow_lock : 1;
    };
} user_config_t;

static user_config_t user_config;

void keyboard_post_init_user(void) {
    user_config.raw = eeconfig_read_user();
    if (user_config.frow_lock) {
        layer_on(FROW);
    }
}

void eeconfig_init_user(void) {
    user_config.raw = 0;
    eeconfig_update_user(user_config.raw);
}

layer_state_t layer_state_set_user(layer_state_t state) {
    /* Save the F-row lock whenever it changes (this only happens on Fn+Ctrl, so flash wear is negligible). */
    bool frow = layer_state_cmp(state, FROW);
    if (frow != user_config.frow_lock) {
        user_config.frow_lock = frow;
        eeconfig_update_user(user_config.raw);
    }
    /* FMEDIA = FROW and FN both active. */
    return update_tri_layer_state(state, FROW, FN, FMEDIA);
}

static void light_key(uint8_t row, uint8_t col, uint8_t r, uint8_t g, uint8_t b, uint8_t led_min, uint8_t led_max) {
    uint8_t led = g_led_config.matrix_co[row][col];
    if (led != NO_LED && led >= led_min && led < led_max) {
        rgb_matrix_set_color(led, r, g, b);
    }
}

bool rgb_matrix_indicators_advanced_user(uint8_t led_min, uint8_t led_max) {
    if (host_keyboard_led_state().caps_lock) {
        light_key(2, 0, RGB_RED, led_min, led_max); /* Caps key (red: visible on white lighting too) */
    }
    if (layer_state_is(FROW)) {
        light_key(4, 11, RGB_ORANGE, led_min, led_max); /* Fn key */
    }
    return true; /* let the keyboard draw the Bluetooth status on top */
}
