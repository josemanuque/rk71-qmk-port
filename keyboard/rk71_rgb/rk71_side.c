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
static volatile uint8_t want_colour;
static uint8_t          phase;
static virtual_timer_t  phase_timer;

/* Red, green and blue are shown one after another, never together: the LEDs share a supply per
 * position, and with red lit (lowest forward voltage) green and blue cannot light, so "white"
 * came out red. 0.6 ms per colour = a full cycle above 500 Hz, which the eye sees as one colour. */
#define PHASE_US 600

static void phase_tick(virtual_timer_t *vtp, void *p) {
    (void)vtp;
    (void)p;
    uint8_t colour = want_colour;
    for (uint8_t i = 0; i < 3; i++) gpio_write_pin_low(colour_pins[i]);
    /* skip colours that are not wanted, so a single colour stays fully lit */
    for (uint8_t n = 0; n < 3; n++) {
        phase = (phase + 1) % 3;
        if ((colour >> phase) & 1) {
            gpio_write_pin_high(colour_pins[phase]);
            break;
        }
    }
}

void side_init(void) {
    gpio_set_pin_output(B8); /* stock keeps B8 high; low makes Win/Alt glow faintly */
    gpio_write_pin_high(B8);
    for (uint8_t i = 0; i < 3; i++) gpio_set_pin_output(colour_pins[i]);
    for (uint8_t i = 0; i < 6; i++) gpio_set_pin_output(position_pins[i]);
    side_show(0, 0);
    chVTObjectInit(&phase_timer);
    chVTSetContinuous(&phase_timer, TIME_US2I(PHASE_US), phase_tick, NULL);
}

void side_show(uint8_t positions, uint8_t colour) {
    if (!positions || !colour) positions = colour = 0;
    if (positions == shown_positions && colour == shown_colour) return;
    shown_positions = positions;
    shown_colour    = colour;
    want_colour = colour; /* the colour lines are driven by phase_tick() */
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
