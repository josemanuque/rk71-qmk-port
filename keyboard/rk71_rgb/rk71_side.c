// Copyright 2026 josemanuque
// SPDX-License-Identifier: GPL-2.0-or-later
#include "rk71_side.h"
#include <ch.h>
#include "gpio.h"
#include "timer.h"
#include "wait.h"

static const pin_t colour_pins[3]   = {D6, D4, D5};                /* red, green, blue */
static const pin_t position_pins[6] = {B9, B10, B11, B12, C0, C1}; /* far … near */

static uint8_t          shown_positions = 0xFF, shown_colour = 0xFF;
static volatile uint8_t schedule[8]; /* colour index (0 R, 1 G, 2 B) per time slot */
static volatile uint8_t schedule_len;
static uint8_t          slot;
static virtual_timer_t  slot_timer;

/* Red, green and blue are shown one after another, never together: the LEDs share a supply per
 * position, and with red lit (lowest forward voltage) green and blue cannot light, so "white"
 * came out red. Short slots (200 us) keep each colour returning well over 1000 times a second.
 * Colour balance: the side LEDs sit behind a bluish diffuser, so blue gets fewer slots
 * (red 3 : green 3 : blue 2 out of 8 when all three are on). */
#define SLOT_US 200
static const uint8_t weight[3] = {3, 3, 2};

static void build_schedule(uint8_t colour) {
    /* Interleave the wanted colours by weight: e.g. white = R G B R G R G B. */
    uint8_t left[3], n = 0;
    for (uint8_t c = 0; c < 3; c++) left[c] = ((colour >> c) & 1) ? weight[c] : 0;
    uint8_t tmp[8];
    while (n < 8) {
        bool any = false;
        for (uint8_t c = 0; c < 3 && n < 8; c++) {
            if (left[c]) {
                tmp[n++] = c;
                left[c]--;
                any = true;
            }
        }
        if (!any) break;
    }
    chSysLock();
    for (uint8_t i = 0; i < n; i++) schedule[i] = tmp[i];
    schedule_len = n;
    slot         = 0;
    chSysUnlock();
}

static void slot_tick(virtual_timer_t *vtp, void *p) {
    (void)vtp;
    (void)p;
    for (uint8_t i = 0; i < 3; i++) gpio_write_pin_low(colour_pins[i]);
    if (!schedule_len) return;
    if (slot >= schedule_len) slot = 0;
    uint8_t c = schedule[slot];
    slot++;
    gpio_write_pin_high(colour_pins[c]);
}

void side_init(void) {
    gpio_set_pin_output(B8); /* stock keeps B8 high; low makes Win/Alt glow faintly */
    gpio_write_pin_high(B8);
    for (uint8_t i = 0; i < 3; i++) gpio_set_pin_output(colour_pins[i]);
    for (uint8_t i = 0; i < 6; i++) gpio_set_pin_output(position_pins[i]);
    side_show(0, 0);
    chVTObjectInit(&slot_timer);
    chVTSetContinuous(&slot_timer, TIME_US2I(SLOT_US), slot_tick, NULL);
}

void side_show(uint8_t positions, uint8_t colour) {
    if (!positions || !colour) positions = colour = 0;
    if (positions == shown_positions && colour == shown_colour) return;
    shown_positions = positions;
    shown_colour    = colour;
    build_schedule(colour); /* the colour lines are driven by slot_tick() */
    for (uint8_t i = 0; i < 6; i++) gpio_write_pin(position_pins[i], !((positions >> i) & 1));
}

/* ---- cable detection --------------------------------------------------------------------------
 * C15 sees the cable's power through a resistor but has no pull-down (and the chip has none), so
 * once unplugged it only drifts low over seconds. Each sample therefore drains the pin for a few
 * microseconds, then reads it: with the cable in it is pulled straight back up. */

#define VBUS_PIN C15
#define SAMPLE_MS 20
#define STABLE_SAMPLES 3

static uint32_t last_sample;
static uint8_t  same_count;
static bool     raw_last, state, known;

void vbus_task(void) {
    if (timer_elapsed32(last_sample) < SAMPLE_MS) return;
    last_sample = timer_read32();

    gpio_set_pin_output(VBUS_PIN);
    gpio_write_pin_low(VBUS_PIN);
    wait_us(5);
    gpio_set_pin_input(VBUS_PIN);
    wait_us(30);
    bool raw = gpio_read_pin(VBUS_PIN);

    if (raw == raw_last) {
        if (same_count < STABLE_SAMPLES) same_count++;
    } else {
        same_count = 0;
        raw_last   = raw;
    }
    if (same_count >= STABLE_SAMPLES) {
        state = raw;
        known = true;
    }
}

bool vbus_present(void) {
    return state;
}

bool vbus_known(void) {
    return known;
}
