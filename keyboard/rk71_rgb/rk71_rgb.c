// Copyright 2026 josemanuque
// SPDX-License-Identifier: GPL-2.0-or-later
//
// Bluetooth for the RK71 (ITON module on SPI0). rk71_bt.c moves bytes; this file adds:
//   - wired / Bluetooth mode and the selected device slot (1-5), saved in the keyboard EEPROM slot
//   - the stock Fn+Q/W/E/R/T, Fn+P and Fn+Backspace controls (tap and 3-second hold)
//   - RGB status: pairing/connecting blink, low battery, idle lighting-off on battery
//
// Commands (A6 xx yy) and events (B6 xx yy) were decoded from stock firmware V1.12. They match
// QMK's iton_bt.h: 51 81..85 select device, 51 89 pair, 51 70 forget all, 58 01 wired mode;
// events 51 76/77/78/79 connected/pairing/disconnected/connecting, 5A 06/07/0A battery.
#include "rk71_rgb.h"
#include <string.h>
#include "rk71_bt.h"
#include "bluetooth.h"
#include "connection.h"
#include "usb_util.h"

#define BT_CMD_BT 0x51
#define BT_CMD_USB 0x58
#define BT_SELECT_HOST(n) (0x80 + (n)) /* 51 81 ... 51 85 */
#define BT_PAIR 0x89
#define BT_FORGET_ALL 0x70
#define BT_USB_MODE 0x01

#define HOLD_MS 3000               /* hold time for pair / forget, as in the stock firmware */
#define BOOT_SETTLE_MS 1000        /* let the module boot before the first command */
#define USB_FALLBACK_MS 5000       /* wired mode but no computer after this long: use Bluetooth */
#define BLINK_TIMEOUT_MS 60000     /* stop the pairing/connecting blink after this long */
#define BATTERY_IDLE_RGB_MS 300000 /* on Bluetooth, lighting off after 5 minutes without typing */

/* ---- saved settings ---------------------------------------------------------------------- */

typedef union {
    uint32_t raw;
    struct {
        bool    bt_mode : 1; /* 0 = wired, 1 = Bluetooth */
        uint8_t host : 3;    /* 0..4 -> device 1..5 */
    };
} kb_config_t;

static kb_config_t kb_config;

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
static uint8_t      host_leds;

static void set_link(link_state_t s) {
    link_state     = s;
    link_since     = timer_read32();
    link_connected = s == LINK_CONNECTED;
}

void rk71_bt_received(const uint8_t *p, uint8_t len) {
    if (p[0] == 0xB1) {
        host_leds = p[1] & 0x07;
    } else if (p[0] == 0xB6 && p[1] == 0x51) {
        switch (p[2]) {
            case 0x76: set_link(LINK_CONNECTED); break;
            case 0x77: set_link(LINK_PAIRING); break;
            case 0x78: set_link(LINK_IDLE); break;
            case 0x79: set_link(LINK_CONNECTING); break;
        }
    } else if (p[0] == 0xB6 && p[1] == 0x5A) {
        switch (p[2]) {
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
static bool     session_bt;        /* Bluetooth chosen automatically (no computer on USB at boot) */
static bool     usb_fallback_done;
static int8_t   applied_mode = -1; /* -1 = nothing sent to the module yet */
static uint32_t mode_flash_until;   /* P flashes after Fn+P: green = now wired, blue = now Bluetooth */
static uint32_t forget_flash_until; /* Backspace flashes red after forgetting all devices */
static bool     show_link;          /* show connect/pair progress: only after a key press, never for
                                       automatic reconnects (power-on, wake-up) */

static bool want_bt(void) {
    return kb_config.bt_mode || session_bt;
}

static void connect_host(void) {
    bt_command(BT_CMD_BT, BT_SELECT_HOST(kb_config.host + 1));
    set_link(LINK_CONNECTING);
}

static void apply_mode(void) {
    bool bt = want_bt();
    if (applied_mode == (int8_t)bt) return;
    applied_mode = bt;
    if (bt) {
        connection_set_host_noeeprom(CONNECTION_HOST_BLUETOOTH);
        connect_host();
    } else {
        connection_set_host_noeeprom(CONNECTION_HOST_USB);
        bt_command(BT_CMD_USB, BT_USB_MODE);
        set_link(LINK_IDLE);
    }
}

static void save_mode(bool bt) {
    session_bt        = false;
    kb_config.bt_mode = bt;
    eeconfig_update_kb(kb_config.raw);
}

static void select_host(uint8_t host, bool pair) {
    kb_config.host = host;
    save_mode(true);
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
            save_mode(!want_bt());
            apply_mode();
            show_link        = applied_mode == 1;
            mode_flash_until = timer_read32() + 2000;
            break;
    }
}

static void key_hold(uint16_t kc) {
    if (kc != BT_CLR) show_link = true;
    switch (kc) {
        case BT_HST1 ... BT_HST5:
            select_host(kc - BT_HST1, true);
            break;
        case BT_MODE:
            select_host(kb_config.host, true);
            break;
        case BT_CLR:
            bt_command(BT_CMD_BT, BT_FORGET_ALL);
            set_link(LINK_IDLE);
            forget_flash_until = timer_read32() + 2000;
            break;
    }
}

bool process_record_kb(uint16_t keycode, keyrecord_t *record) {
    if (!process_record_user(keycode, record)) return false;
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

/* ---- startup and background work ------------------------------------------------------------ */

void keyboard_pre_init_kb(void) {
    /* A6/A7 go to the Bluetooth module; the stock firmware keeps both as outputs, low. */
    gpio_set_pin_output(A6);
    gpio_write_pin_low(A6);
    gpio_set_pin_output(A7);
    gpio_write_pin_low(A7);
    keyboard_pre_init_user();
}

void keyboard_post_init_kb(void) {
    kb_config.raw = eeconfig_read_kb();
    if (kb_config.host > 4) kb_config.host = 0;
    boot_time = timer_read32();
    keyboard_post_init_user();
}

static bool rgb_off_for_idle;

void housekeeping_task_kb(void) {
    uint32_t now = timer_read32();

    if ((link_state == LINK_CONNECTING || link_state == LINK_PAIRING) && TIMER_DIFF_32(now, link_since) > BLINK_TIMEOUT_MS) {
        link_state = LINK_IDLE;
    }
    /* Progress lights end 1 s after connecting, or when the attempt fails or times out. */
    if (show_link && ((link_state == LINK_CONNECTED && TIMER_DIFF_32(now, link_since) > 1000) || TIMER_DIFF_32(now, link_since) > BLINK_TIMEOUT_MS || applied_mode != 1)) {
        show_link = false;
    }

    if (held_key && !hold_done && TIMER_DIFF_32(now, held_since) >= HOLD_MS) {
        hold_done = true;
        key_hold(held_key);
    }

    /* Wired mode, but no computer answered on USB: we are on battery, so use Bluetooth.
     * Plugging into a computer later brings it back to wired. */
    if (!usb_fallback_done && TIMER_DIFF_32(now, boot_time) > USB_FALLBACK_MS) {
        usb_fallback_done = true;
        if (!kb_config.bt_mode && !usb_connected_state()) session_bt = true;
    }
    if (session_bt && usb_connected_state()) session_bt = false;

    if (TIMER_DIFF_32(now, boot_time) > BOOT_SETTLE_MS) apply_mode();

    /* Battery saving: on Bluetooth, lighting off after a while without typing, and at once
     * when the module reports a flat battery. */
    bool idle = applied_mode == 1 && (last_input_activity_elapsed() > BATTERY_IDLE_RGB_MS || battery_shutdown);
    if (idle && !rgb_off_for_idle && rgb_matrix_is_enabled()) {
        rgb_matrix_disable_noeeprom();
        rgb_off_for_idle = true;
    } else if (!idle && rgb_off_for_idle) {
        rgb_matrix_enable_noeeprom();
        rgb_off_for_idle = false;
    }

    housekeeping_task_user();
}

/* ---- RGB status ---------------------------------------------------------------------------- */

static void light(uint8_t row, uint8_t col, uint8_t r, uint8_t g, uint8_t b, uint8_t led_min, uint8_t led_max) {
    uint8_t led = g_led_config.matrix_co[row][col];
    if (led != NO_LED && led >= led_min && led < led_max) rgb_matrix_set_color(led, r, g, b);
}

bool rgb_matrix_indicators_advanced_kb(uint8_t led_min, uint8_t led_max) {
    if (!rgb_matrix_indicators_advanced_user(led_min, led_max)) return false;

    uint32_t now      = timer_read32();
    uint8_t  host_col = 1 + kb_config.host; /* Q W E R T = row 1, columns 1..5 */
    bool     bt       = applied_mode == 1;

    /* Connect / pair progress on the slot key (Q..T), only after Fn+Q..T or Fn+P. */
    if (bt && show_link) {
        switch (link_state) {
            case LINK_PAIRING: /* fast blink */
                if ((now / 200) % 2) light(1, host_col, RGB_BLUE, led_min, led_max);
                break;
            case LINK_IDLE: /* e.g. the old device just disconnected: still connecting */
            case LINK_CONNECTING: /* slow blink */
                if ((now / 500) % 2) light(1, host_col, RGB_BLUE, led_min, led_max);
                break;
            case LINK_CONNECTED: /* solid for 1 s: connected */
                light(1, host_col, RGB_BLUE, led_min, led_max);
                break;
            default:
                break;
        }
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
    if (TIMER_DIFF_32(mode_flash_until, now) < 2000 && (now / 250) % 2) {
        if (bt) {
            light(1, 10, RGB_BLUE, led_min, led_max);
        } else {
            light(1, 10, RGB_GREEN, led_min, led_max);
        }
    }
    if (TIMER_DIFF_32(forget_flash_until, now) < 2000) light(0, 13, RGB_RED, led_min, led_max);

    /* Low battery: Space blinks red. */
    if (battery_low && (now / 1000) % 2) light(4, 6, RGB_RED, led_min, led_max);

    return true;
}
