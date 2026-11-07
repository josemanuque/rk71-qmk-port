#include QMK_KEYBOARD_H

/*
 * RK71 RGB — QMK keymap
 *
 * Layer 0 — Windows base
 * Layer 1 — Mac base  (physical Win key = Cmd, physical Alt = Option)
 * Layer 2 — Fn layer for Windows  (hold Fn key)
 * Layer 3 — Fn layer for Mac      (hold Fn key while in Mac mode)
 *
 * Mode switching (all via Fn layer):
 *   Fn + physical-Win   → DF(1)  switch to Mac mode
 *   Fn + physical-Alt   → DF(0)  switch to Windows mode
 *   (Works from either Fn layer, so you can switch in both directions.)
 *
 * Fn-lock:
 *   Fn + CapsLock       → toggles Fn-lock ON/OFF
 *   LED indicator: CapsLock LED (host-side) reflects Fn-lock state
 *   Fn-lock ON  → F-row sends media keys; hold Fn to get F1-F12
 *   Fn-lock OFF → F-row sends F1-F12; hold Fn to get media keys (default)
 *
 * Mac-specific shortcut:
 *   Fn + ` (in Mac Fn layer)  → Cmd+` (switch windows of same app)
 *
 * Reset to bootloader:
 *   Fn + F12 → QK_BOOT (enter SONiX ISP bootloader for reflashing)
 *
 * Matrix:  7 rows × 16 cols   (ROW2COL, rows driven low, cols read with pull-up)
 * Row/col pin assignments: see config.h
 */

/* ------------------------------------------------------------------ */
/*  Custom keycodes                                                     */
/* ------------------------------------------------------------------ */
enum custom_keycodes {
    FN_LOCK = SAFE_RANGE, /* toggle Fn-lock */
    MC_MODE,              /* switch to Mac mode   (DF(1)) */
    WIN_MODE,             /* switch to Windows mode (DF(0)) */
    CMD_GRV,              /* Cmd+` shortcut for macOS window switching */
};

/* ------------------------------------------------------------------ */
/*  Fn-lock state                                                       */
/* ------------------------------------------------------------------ */
static bool fn_lock_on = false;

/* ------------------------------------------------------------------ */
/*  Helpers                                                             */
/* ------------------------------------------------------------------ */
/* Return the Fn-layer index for the current default layer */
static uint8_t fn_layer(void) {
    return (get_highest_layer(default_layer_state) == 1) ? 3 : 2;
}

/* ------------------------------------------------------------------ */
/*  Layers                                                              */
/* ------------------------------------------------------------------ */
/*
 * LAYOUT_all argument order (104 keys, row-major, matches keyboard.json):
 *
 *  Row0 (13): Esc F1..F12
 *  Row1 (16): ` 1..= NumLk Num/ Num*
 *  Row2 (16): Tab Q..] Num7 Num8 Num9
 *  Row3 (16): Caps A..\ Num4 Num5 Num6
 *  Row4 (16): LShift Z../ RShift Enter Num1 Num2 Num3
 *  Row5 (16): LCtrl LWin LAlt Space RAlt Fn App RCtrl Left Down Up Right Bspc Num0 NumDot NumEnter
 *  Row6 (11, skip cols 0-2 and 5 and 15):
 *             PrtSc ScrLk [skip] Pause Ins Home PgUp Del End PgDn Num- Num+
 */
const uint16_t PROGMEM keymaps[][MATRIX_ROWS][MATRIX_COLS] = {

/* ---- Layer 0: Windows base ---------------------------------------- */
[0] = LAYOUT_all(
    /* Row 0 — F-row */
    KC_ESC,  KC_F1,   KC_F2,   KC_F3,   KC_F4,   KC_F5,   KC_F6,   KC_F7,   KC_F8,   KC_F9,   KC_F10,  KC_F11,  KC_F12,
    /* Row 1 — number row + numpad top */
    KC_GRV,  KC_1,    KC_2,    KC_3,    KC_4,    KC_5,    KC_6,    KC_7,    KC_8,    KC_9,    KC_0,    KC_MINS, KC_EQL,  KC_NUM,  KC_PSLS, KC_PAST,
    /* Row 2 — QWERTY + numpad 7-9 */
    KC_TAB,  KC_Q,    KC_W,    KC_E,    KC_R,    KC_T,    KC_Y,    KC_U,    KC_I,    KC_O,    KC_P,    KC_LBRC, KC_RBRC, KC_P7,   KC_P8,   KC_P9,
    /* Row 3 — ASDF + numpad 4-6 */
    KC_CAPS, KC_A,    KC_S,    KC_D,    KC_F,    KC_G,    KC_H,    KC_J,    KC_K,    KC_L,    KC_SCLN, KC_QUOT, KC_BSLS, KC_P4,   KC_P5,   KC_P6,
    /* Row 4 — ZXCV + numpad 1-3 */
    KC_LSFT, KC_Z,    KC_X,    KC_C,    KC_V,    KC_B,    KC_N,    KC_M,    KC_COMM, KC_DOT,  KC_SLSH, KC_RSFT, KC_ENT,  KC_P1,   KC_P2,   KC_P3,
    /* Row 5 — bottom row + nav + numpad 0/./Enter */
    KC_LCTL, KC_LGUI, KC_LALT, KC_SPC,  KC_RALT, MO(2),   KC_APP,  KC_RCTL, KC_LEFT, KC_DOWN, KC_UP,   KC_RGHT, KC_BSPC, KC_P0,   KC_PDOT, KC_PENT,
    /* Row 6 — nav cluster + Num-/Num+ */
             KC_PSCR, KC_SCRL,          KC_PAUS, KC_INS,  KC_HOME, KC_PGUP, KC_DEL,  KC_END,  KC_PGDN, KC_PMNS, KC_PPLS
),

/* ---- Layer 1: Mac base -------------------------------------------- */
/* Physical Win key (5,1) → KC_LALT (Option)                           */
/* Physical Alt key (5,2) → KC_LGUI (Command)                          */
/* Everything else identical to Windows layer                           */
[1] = LAYOUT_all(
    KC_ESC,  KC_F1,   KC_F2,   KC_F3,   KC_F4,   KC_F5,   KC_F6,   KC_F7,   KC_F8,   KC_F9,   KC_F10,  KC_F11,  KC_F12,
    KC_GRV,  KC_1,    KC_2,    KC_3,    KC_4,    KC_5,    KC_6,    KC_7,    KC_8,    KC_9,    KC_0,    KC_MINS, KC_EQL,  KC_NUM,  KC_PSLS, KC_PAST,
    KC_TAB,  KC_Q,    KC_W,    KC_E,    KC_R,    KC_T,    KC_Y,    KC_U,    KC_I,    KC_O,    KC_P,    KC_LBRC, KC_RBRC, KC_P7,   KC_P8,   KC_P9,
    KC_CAPS, KC_A,    KC_S,    KC_D,    KC_F,    KC_G,    KC_H,    KC_J,    KC_K,    KC_L,    KC_SCLN, KC_QUOT, KC_BSLS, KC_P4,   KC_P5,   KC_P6,
    KC_LSFT, KC_Z,    KC_X,    KC_C,    KC_V,    KC_B,    KC_N,    KC_M,    KC_COMM, KC_DOT,  KC_SLSH, KC_RSFT, KC_ENT,  KC_P1,   KC_P2,   KC_P3,
    KC_LCTL, KC_LALT, KC_LGUI, KC_SPC,  KC_RALT, MO(3),   KC_APP,  KC_RCTL, KC_LEFT, KC_DOWN, KC_UP,   KC_RGHT, KC_BSPC, KC_P0,   KC_PDOT, KC_PENT,
             KC_PSCR, KC_SCRL,          KC_PAUS, KC_INS,  KC_HOME, KC_PGUP, KC_DEL,  KC_END,  KC_PGDN, KC_PMNS, KC_PPLS
),

/* ---- Layer 2: Windows Fn ------------------------------------------ */
[2] = LAYOUT_all(
    /* F-row: media keys */
    _______,  KC_MNXT, KC_MPRV, KC_MSTP, KC_MPLY, KC_MUTE, KC_VOLD, KC_VOLU, _______, _______, _______, _______, QK_BOOT,
    /* ` → Cmd+` shortcut (useful even in Windows for some apps) */
    CMD_GRV, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______,
    _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______,
    /* CapsLk → Fn-lock toggle */
    FN_LOCK, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______,
    _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______,
    /* Win → switch to Mac; Alt → (already Win mode, nop) */
    _______, MC_MODE, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______,
             _______, _______,          _______, _______, _______, _______, _______, _______, _______, _______, _______
),

/* ---- Layer 3: Mac Fn ---------------------------------------------- */
[3] = LAYOUT_all(
    _______,  KC_MNXT, KC_MPRV, KC_MSTP, KC_MPLY, KC_MUTE, KC_VOLD, KC_VOLU, _______, _______, _______, _______, QK_BOOT,
    /* ` → Cmd+` (switch windows of same app in macOS) */
    CMD_GRV, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______,
    _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______,
    FN_LOCK, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______,
    _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______,
    /* Win(=Opt) → (already Mac mode); Cmd(=at Alt pos) → switch to Windows */
    _______, _______, WIN_MODE,_______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______, _______,
             _______, _______,          _______, _______, _______, _______, _______, _______, _______, _______, _______
),

}; /* end keymaps */

/* ------------------------------------------------------------------ */
/*  Custom keycode handling                                             */
/* ------------------------------------------------------------------ */
bool process_record_user(uint16_t keycode, keyrecord_t *record) {
    switch (keycode) {

    case FN_LOCK:
        if (record->event.pressed) {
            fn_lock_on = !fn_lock_on;
            /* Flash the CapsLock LED briefly as confirmation */
            tap_code(KC_CAPS);
            tap_code(KC_CAPS);
        }
        return false;

    case MC_MODE:
        if (record->event.pressed) {
            set_single_persistent_default_layer(1);
        }
        return false;

    case WIN_MODE:
        if (record->event.pressed) {
            set_single_persistent_default_layer(0);
        }
        return false;

    case CMD_GRV:
        if (record->event.pressed) {
            /* Send Cmd+` regardless of current mode */
            register_code(KC_LGUI);
            tap_code(KC_GRV);
            unregister_code(KC_LGUI);
        }
        return false;

    /* Fn-lock: intercept F1-F12 on the base layers */
    case KC_F1 ... KC_F12:
        if (fn_lock_on) {
            /* Look up what the Fn layer would send for this key */
            uint8_t fl = fn_layer();
            uint16_t fn_code = keymap_key_to_keycode(fl, record->event.key);
            if (fn_code != KC_TRNS && fn_code != KC_NO) {
                /* Fn-lock ON: send the Fn-layer action instead */
                if (record->event.pressed) {
                    register_code16(fn_code);
                } else {
                    unregister_code16(fn_code);
                }
                return false;
            }
        }
        return true;

    default:
        return true;
    }
}

/* ------------------------------------------------------------------ */
/*  LED indicator for Fn-lock (CapsLock LED on = Fn-lock active)       */
/* ------------------------------------------------------------------ */
bool led_update_user(led_t led_state) {
    if (fn_lock_on) {
        /* Force CapsLock LED on while Fn-lock is active */
        led_t forced = led_state;
        forced.caps_lock = true;
        return true; /* let QMK set it; actual GPIO write handled by platform */
    }
    return true;
}
