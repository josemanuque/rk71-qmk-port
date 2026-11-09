// Copyright 2026 josemanuque
// SPDX-License-Identifier: GPL-2.0-or-later
//
// RK71 keyboard-level features. rk71_bt.c moves bytes to the Bluetooth module and rk71_side.c
// drives the side lights and reads the USB cable pin; this file adds:
//   - wired / Bluetooth mode: unplugged = Bluetooth; plugged = wired unless Fn+P chose Bluetooth
//   - the device slot (1-5) and the stock Fn+Q/W/E/R/T, Fn+P, Fn+Backspace controls (tap / 3 s hold)
//   - side lights: follow the keyboard colour, a fixed colour, or off (set in VIA), plus status:
//     pairing, connecting, mode changes, battery level (Fn+Space), low battery
//   - lighting off after 5 minutes idle on battery
//
// Commands (A6 xx yy) and events (B6 xx yy) were decoded from stock firmware V1.12. They match
// QMK's iton_bt.h: 51 81..85 select device, 51 89 pair, 51 70 forget all, 51 61 battery level,
// 58 01 wired mode; events 51 76/77/78/79 connected/pairing/disconnected/connecting,
// 5A 04/02/01 battery high/medium/low, 5A 06/07/0A battery low/shutdown/ok.
#include "rk71_rgb.h"
#include <string.h>
#include "rk71_bt.h"
#include "rk71_side.h"
#include "bluetooth.h"
#include "connection.h"
#ifdef VIA_ENABLE
#    include "via.h"
#endif

#define BT_CMD_BT 0x51
#define BT_CMD_USB 0x58
#define BT_SELECT_HOST(n) (0x80 + (n)) /* 51 81 ... 51 85 */
#define BT_PAIR 0x89
#define BT_FORGET_ALL 0x70
#define BT_QUERY_BATTERY 0x61
#define BT_USB_MODE 0x01

#define HOLD_MS 3000               /* hold time for pair / forget, as in the stock firmware */
#define BOOT_SETTLE_MS 1000        /* let the module boot before the first command */
#define BLINK_TIMEOUT_MS 60000     /* stop the pairing/connecting blink after this long */
#define BATTERY_IDLE_RGB_MS 300000 /* on Bluetooth, lighting off after 5 minutes without typing */
#define LEDS_STABLE_MS 200         /* right after connecting, a wrong lock-LED value can arrive */
#define FLASH_MS 1500              /* mode-change flash */
#define BATTERY_SHOW_MS 3000       /* Fn+Space battery bar */
#define BATTERY_WAIT_MS 1500       /* no answer from the module after this long: show "unknown" */

/* ---- saved settings ---------------------------------------------------------------------- */
/* All-zero is the default: wired, slot 1, side lights follow the keyboard, status shown. */

enum { SIDE_FOLLOW, SIDE_FIXED, SIDE_OFF };

typedef union {
    uint32_t raw;
    struct {
        bool    bt_mode : 1;     /* when plugged in: 0 = wired, 1 = Bluetooth */
        uint8_t host : 3;        /* 0..4 -> device 1..5 */
        uint8_t side_mode : 2;   /* SIDE_FOLLOW / SIDE_FIXED / SIDE_OFF */
        uint8_t side_colour : 3; /* index into side_colours[] */
        bool    side_no_status : 1;
        uint8_t side_balance : 2; /* stored as (level + 3) % 4 so all-zero = level 1 "warm" */
    };
} kb_config_t;

static kb_config_t kb_config;

/* VIA dropdown order: White, Red, Yellow, Green, Cyan, Blue, Magenta */
static const uint8_t side_colours[] = {SIDE_WHITE, SIDE_RED, SIDE_YELLOW, SIDE_GREEN, SIDE_CYAN, SIDE_BLUE, SIDE_MAGENTA};

void eeconfig_init_kb(void) {
    kb_config.raw = 0;
    eeconfig_update_kb(kb_config.raw);
    eeconfig_init_user();
}

/* ---- link state ---------------------------------------------------------------------------- */

typedef enum { LINK_IDLE, LINK_CONNECTING, LINK_PAIRING, LINK_CONNECTED } link_state_t;

static link_state_t link_state;
static uint32_t     link_since;
static bool         link_connected;
static bool         battery_low;
static bool         battery_shutdown;
static uint8_t      battery_level; /* 0 unknown, 1 low, 2 medium, 3 high */
static uint8_t      host_leds;     /* lock LEDs (Num/Caps/Scroll) as the Bluetooth host reports them */
static uint8_t      pending_leds;  /* newest report, applied once stable for LEDS_STABLE_MS */
static uint32_t     pending_since;

static void set_link(link_state_t s) {
    link_state     = s;
    link_since     = timer_read32();
    link_connected = s == LINK_CONNECTED;
}

void rk71_bt_received(const uint8_t *p, uint8_t len) {
    if (p[0] == 0xB1) {
        pending_leds  = p[1] & 0x07;
        pending_since = timer_read32();
    } else if (p[0] == 0xB6 && p[1] == 0x51) {
        switch (p[2]) {
            case 0x76: set_link(LINK_CONNECTED); break;
            case 0x77: set_link(LINK_PAIRING); break;
            case 0x78: set_link(LINK_IDLE); break;
            case 0x79: set_link(LINK_CONNECTING); break;
        }
    } else if (p[0] == 0xB6 && p[1] == 0x5A) {
        switch (p[2]) {
            case 0x04: battery_level = 3; break;
            case 0x02: battery_level = 2; break;
            case 0x01: battery_level = 1; break;
            case 0x06: battery_low = true; break;
            case 0x07: battery_shutdown = true; break;
            case 0x0A: battery_low = battery_shutdown = false; break;
        }
    }
}

static void bt_command(uint8_t group, uint8_t param) {
    uint8_t pkt[3] = {0xA6, group, param};
    rk71_bt_send(pkt, sizeof(pkt));
}

/* ---- QMK Bluetooth driver hooks (BLUETOOTH_DRIVER = custom) -------------------------------- */

void bluetooth_init(void) {
    rk71_bt_init();
}

void bluetooth_task(void) {
    rk71_bt_task();
}

bool bluetooth_is_connected(void) {
    return link_connected;
}

uint8_t bluetooth_keyboard_leds(void) {
    return host_leds;
}

void bluetooth_send_keyboard(report_keyboard_t *report) {
    /* A1 + modifiers, reserved, 6 keys (boot keyboard report). */
    uint8_t pkt[9] = {0xA1, report->mods, 0};
    memcpy(&pkt[3], report->keys, 6);
    rk71_bt_send(pkt, sizeof(pkt));
}

void bluetooth_send_consumer(uint16_t usage) {
    uint8_t pkt[3] = {0xA3, usage >> 8, usage & 0xFF}; /* byte order as in QMK's iton_bt */
    rk71_bt_send(pkt, sizeof(pkt));
}

/* ---- mode handling -------------------------------------------------------------------------- */

static uint32_t boot_time;
static int8_t   applied_mode = -1; /* -1 = nothing sent to the module yet; 0 wired; 1 Bluetooth */
static uint32_t mode_flash_at;     /* when the mode last changed (side lights / P key flash) */
static bool     mode_flash;
static uint32_t forget_flash_at;
static bool     forget_flash;
static uint32_t battery_asked_at;
static bool     battery_showing;
static bool     show_link; /* connect/pair progress: only after a key press, not for automatic reconnects */

static bool want_bt(void) {
    return !vbus_present() || kb_config.bt_mode; /* no cable: Bluetooth is the only option */
}

static void connect_host(void) {
    bt_command(BT_CMD_BT, BT_SELECT_HOST(kb_config.host + 1));
    set_link(LINK_CONNECTING);
}

static void apply_mode(void) {
    bool bt = want_bt();
    if (applied_mode == (int8_t)bt) return;
    bool first   = applied_mode < 0;
    applied_mode = bt;
    if (bt) {
        host_leds = pending_leds = 0; /* no stale Caps Lock state from an earlier session */
        connection_set_host_noeeprom(CONNECTION_HOST_BLUETOOTH);
        connect_host();
    } else {
        connection_set_host_noeeprom(CONNECTION_HOST_USB);
        bt_command(BT_CMD_USB, BT_USB_MODE);
        set_link(LINK_IDLE);
    }
    if (!first) {
        mode_flash    = true;
        mode_flash_at = timer_read32();
    }
}

static void save_config(void) {
    eeconfig_update_kb(kb_config.raw);
}

static void select_host(uint8_t host, bool pair) {
    kb_config.host    = host;
    kb_config.bt_mode = true; /* choosing a device also means Bluetooth when plugged in */
    save_config();
    if (applied_mode != 1) {
        apply_mode(); /* switches to Bluetooth and connects to the new slot */
    } else {
        connect_host();
    }
    if (pair) {
        bt_command(BT_CMD_BT, BT_PAIR);
        set_link(LINK_PAIRING);
    }
}

/* ---- keys: tap vs 3-second hold ------------------------------------------------------------- */

static uint16_t held_key;
static uint32_t held_since;
static bool     hold_done;

static void key_tap(uint16_t kc) {
    switch (kc) {
        case BT_HST1 ... BT_HST5:
            show_link = true;
            select_host(kc - BT_HST1, false);
            break;
        case BT_MODE:
            if (vbus_present()) { /* unplugged it is always Bluetooth */
                kb_config.bt_mode = !kb_config.bt_mode;
                save_config();
                apply_mode();
                show_link = applied_mode == 1;
            }
            mode_flash    = true;
            mode_flash_at = timer_read32();
            break;
    }
}

static void key_hold(uint16_t kc) {
    switch (kc) {
        case BT_HST1 ... BT_HST5:
            show_link = true;
            select_host(kc - BT_HST1, true);
            break;
        case BT_MODE:
            show_link = true;
            select_host(kb_config.host, true);
            break;
        case BT_CLR:
            bt_command(BT_CMD_BT, BT_FORGET_ALL);
            set_link(LINK_IDLE);
            forget_flash    = true;
            forget_flash_at = timer_read32();
            break;
    }
}

bool process_record_kb(uint16_t keycode, keyrecord_t *record) {
    if (!process_record_user(keycode, record)) return false;
    if (keycode == BT_BATT) {
        if (record->event.pressed) {
            battery_level    = 0;
            battery_showing  = true;
            battery_asked_at = timer_read32();
            bt_command(BT_CMD_BT, BT_QUERY_BATTERY);
        }
        return false;
    }
    if (keycode >= BT_HST1 && keycode <= BT_CLR) {
        if (record->event.pressed) {
            held_key   = keycode;
            held_since = timer_read32();
            hold_done  = false;
        } else if (held_key == keycode) {
            if (!hold_done) key_tap(keycode);
            held_key = 0;
        }
        return false;
    }
    return true;
}

/* ---- side lights ---------------------------------------------------------------------------- */

static bool lighting_visible(void) {
    return rk71_rgb_lighting_on() && rgb_matrix_get_val() > 0;
}

/* Nearest of the 7 side-light colours to the keyboard's colour. */
static uint8_t follow_colour(void) {
    if (rgb_matrix_get_sat() < 80) return SIDE_WHITE;
    static const uint8_t by_hue[] = {SIDE_RED, SIDE_YELLOW, SIDE_GREEN, SIDE_CYAN, SIDE_BLUE, SIDE_MAGENTA};
    uint8_t              h        = rgb_matrix_get_hue();
    return by_hue[((uint16_t)h * 6 + 128) / 256 % 6];
}

static bool blink(uint32_t now, uint16_t period) {
    return (now / period) % 2;
}

/* Status takes over the side lights while something is happening. Returns false when idle. */
static bool side_status(uint32_t now, uint8_t *pos, uint8_t *col) {
    if (forget_flash) {
        *pos = SIDE_ALL;
        *col = blink(now, 150) ? SIDE_RED : 0;
        return true;
    }
    if (battery_showing) {
        if (battery_level) {
            static const uint8_t bars[] = {0, 0x20, 0x38, 0x3F}; /* 1 / 3 / 6 lights from the near end */
            static const uint8_t cols[] = {0, SIDE_RED, SIDE_YELLOW, SIDE_GREEN};
            *pos = bars[battery_level];
            *col = cols[battery_level];
        } else if (TIMER_DIFF_32(now, battery_asked_at) > BATTERY_WAIT_MS) {
            *pos = 0x20; /* no answer (slide switch off?): nearest light blinks red */
            *col = blink(now, 150) ? SIDE_RED : 0;
        } else {
            *pos = *col = 0;
        }
        return true;
    }
    if (show_link && applied_mode == 1) {
        *pos = SIDE_ALL;
        switch (link_state) {
            case LINK_PAIRING: *col = blink(now, 200) ? SIDE_BLUE : 0; return true;
            case LINK_CONNECTED: *col = SIDE_BLUE; return true;
            default: *col = blink(now, 500) ? SIDE_BLUE : 0; return true; /* connecting */
        }
    }
    if (mode_flash) {
        *pos = SIDE_ALL;
        *col = applied_mode == 1 ? SIDE_BLUE : SIDE_GREEN;
        return true;
    }
    if (battery_low) {
        *pos = 0x20; /* nearest light blinks red */
        *col = blink(now, 1000) ? SIDE_RED : 0;
        return true;
    }
    return false;
}

static void side_update(uint32_t now) {
    uint8_t pos = 0, col = 0;
    if (kb_config.side_no_status || !side_status(now, &pos, &col)) {
        if (kb_config.side_mode != SIDE_OFF && lighting_visible()) {
            pos = SIDE_ALL;
            col = kb_config.side_mode == SIDE_FIXED ? side_colours[kb_config.side_colour % 7] : follow_colour();
        }
    }
    side_show(pos, col);
}

/* ---- startup and background work ------------------------------------------------------------ */

void keyboard_pre_init_kb(void) {
    /* A6/A7 go to the Bluetooth module; the stock firmware keeps both as outputs, low. */
    gpio_set_pin_output(A6);
    gpio_write_pin_low(A6);
    gpio_set_pin_output(A7);
    gpio_write_pin_low(A7);
    side_init();
    keyboard_pre_init_user();
}

void keyboard_post_init_kb(void) {
    kb_config.raw = eeconfig_read_kb();
    if (kb_config.host > 4) kb_config.host = 0;
    if (kb_config.side_mode > SIDE_OFF) kb_config.side_mode = SIDE_FOLLOW;
    side_set_balance((kb_config.side_balance + 1) % 4);
    boot_time = timer_read32();
    keyboard_post_init_user();
}

static bool rgb_off_for_idle;

bool rk71_rgb_lighting_on(void) {
    return rgb_matrix_is_enabled() && !rgb_matrix_get_suspend_state();
}

void housekeeping_task_kb(void) {
    uint32_t now = timer_read32();

    vbus_task();

    if (pending_leds != host_leds && TIMER_DIFF_32(now, pending_since) >= LEDS_STABLE_MS) host_leds = pending_leds;

    if ((link_state == LINK_CONNECTING || link_state == LINK_PAIRING) && TIMER_DIFF_32(now, link_since) > BLINK_TIMEOUT_MS) {
        link_state = LINK_IDLE;
    }
    /* Progress display ends 1 s after connecting, or when the attempt times out. */
    if (show_link && ((link_state == LINK_CONNECTED && TIMER_DIFF_32(now, link_since) > 1000) || TIMER_DIFF_32(now, link_since) > BLINK_TIMEOUT_MS || applied_mode != 1)) {
        show_link = false;
    }
    if (mode_flash && TIMER_DIFF_32(now, mode_flash_at) > FLASH_MS) mode_flash = false;
    if (forget_flash && TIMER_DIFF_32(now, forget_flash_at) > 2000) forget_flash = false;
    if (battery_showing && TIMER_DIFF_32(now, battery_asked_at) > BATTERY_SHOW_MS) battery_showing = false;

    if (held_key && !hold_done && TIMER_DIFF_32(now, held_since) >= HOLD_MS) {
        hold_done = true;
        key_hold(held_key);
    }

    if (vbus_known() && TIMER_DIFF_32(now, boot_time) > BOOT_SETTLE_MS) apply_mode();

    /* Battery saving: on Bluetooth without a cable, lighting off after a while without typing,
     * and at once when the module reports a flat battery. */
    bool idle = applied_mode == 1 && !vbus_present() && (last_input_activity_elapsed() > BATTERY_IDLE_RGB_MS || battery_shutdown);
    if (idle && !rgb_off_for_idle && rgb_matrix_is_enabled()) {
        rgb_matrix_disable_noeeprom();
        rgb_off_for_idle = true;
    } else if (!idle && rgb_off_for_idle) {
        rgb_matrix_enable_noeeprom();
        rgb_off_for_idle = false;
    }

    side_update(now);

    housekeeping_task_user();
}

void suspend_power_down_kb(void) {
    side_show(0, 0); /* computer asleep: side lights off, as the stock firmware does */
    suspend_power_down_user();
}

/* ---- per-key RGB status (used when side-light status is turned off in VIA) ------------------- */

static void light(uint8_t row, uint8_t col, uint8_t r, uint8_t g, uint8_t b, uint8_t led_min, uint8_t led_max) {
    uint8_t led = g_led_config.matrix_co[row][col];
    if (led != NO_LED && led >= led_min && led < led_max) rgb_matrix_set_color(led, r, g, b);
}

bool rgb_matrix_indicators_advanced_kb(uint8_t led_min, uint8_t led_max) {
    if (!rgb_matrix_indicators_advanced_user(led_min, led_max)) return false;

    uint32_t now      = timer_read32();
    uint8_t  host_col = 1 + kb_config.host; /* Q W E R T = row 1, columns 1..5 */
    bool     bt       = applied_mode == 1;

    if (kb_config.side_no_status) {
        if (bt && show_link) {
            switch (link_state) {
                case LINK_PAIRING:
                    if (blink(now, 200)) light(1, host_col, RGB_BLUE, led_min, led_max);
                    break;
                case LINK_CONNECTED:
                    light(1, host_col, RGB_BLUE, led_min, led_max);
                    break;
                default:
                    if (blink(now, 500)) light(1, host_col, RGB_BLUE, led_min, led_max);
                    break;
            }
        }
        if (mode_flash && blink(now, 250)) {
            if (bt) {
                light(1, 10, RGB_BLUE, led_min, led_max);
            } else {
                light(1, 10, RGB_GREEN, led_min, led_max);
            }
        }
        if (forget_flash) light(0, 13, RGB_RED, led_min, led_max);
        if (battery_low && blink(now, 1000)) light(4, 6, RGB_RED, led_min, led_max);
    }

    /* While Fn is held: P shows the mode (green wired, blue Bluetooth), the slot key is blue. */
    if (IS_LAYER_ON(3) /* FN */) {
        if (bt) {
            light(1, 10, RGB_BLUE, led_min, led_max);
            light(1, host_col, RGB_BLUE, led_min, led_max);
        } else {
            light(1, 10, RGB_GREEN, led_min, led_max);
        }
    }
    return true;
}

/* ---- VIA: "Side lights" settings page --------------------------------------------------------- */
#ifdef VIA_ENABLE
enum { ID_SIDE_MODE = 1, ID_SIDE_COLOUR, ID_SIDE_STATUS, ID_SIDE_BALANCE };

void via_custom_value_command_kb(uint8_t *data, uint8_t length) {
    /* data = [ command_id, channel_id, value_id, value_data ] */
    uint8_t *command_id = &data[0];
    uint8_t  channel_id = data[1];
    uint8_t  value_id   = data[2];
    uint8_t *value      = &data[3];

    if (channel_id != id_custom_channel) {
        *command_id = id_unhandled;
        return;
    }
    switch (*command_id) {
        case id_custom_set_value:
            switch (value_id) {
                case ID_SIDE_MODE: kb_config.side_mode = value[0] > SIDE_OFF ? SIDE_FOLLOW : value[0]; break;
                case ID_SIDE_COLOUR: kb_config.side_colour = value[0] % 7; break;
                case ID_SIDE_STATUS: kb_config.side_no_status = !value[0]; break;
                case ID_SIDE_BALANCE:
                    kb_config.side_balance = (value[0] + 3) % 4;
                    side_set_balance(value[0] % 4);
                    break;
                default: *command_id = id_unhandled; break;
            }
            break;
        case id_custom_get_value:
            switch (value_id) {
                case ID_SIDE_MODE: value[0] = kb_config.side_mode; break;
                case ID_SIDE_COLOUR: value[0] = kb_config.side_colour; break;
                case ID_SIDE_STATUS: value[0] = !kb_config.side_no_status; break;
                case ID_SIDE_BALANCE: value[0] = (kb_config.side_balance + 1) % 4; break;
                default: *command_id = id_unhandled; break;
            }
            break;
        case id_custom_save:
            save_config();
            break;
        default:
            *command_id = id_unhandled;
            break;
    }
}
#endif
