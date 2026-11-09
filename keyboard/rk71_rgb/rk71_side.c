// Copyright 2026 josemanuque
// SPDX-License-Identifier: GPL-2.0-or-later
#include "rk71_side.h"
#include "gpio.h"
#include "timer.h"
#include "wait.h"

static const pin_t colour_pins[3]   = {D6, D4, D5};                /* red, green, blue */
static const pin_t position_pins[6] = {B9, B10, B11, B12, C0, C1}; /* far … near */

static uint8_t shown_positions = 0xFF, shown_colour = 0xFF;

void side_init(void) {
    gpio_set_pin_output(B8); /* stock keeps B8 high; low makes Win/Alt glow faintly */
    gpio_write_pin_high(B8);
    for (uint8_t i = 0; i < 3; i++) gpio_set_pin_output(colour_pins[i]);
    for (uint8_t i = 0; i < 6; i++) gpio_set_pin_output(position_pins[i]);
    side_show(0, 0);
}

void side_show(uint8_t positions, uint8_t colour) {
    if (!positions || !colour) positions = colour = 0;
    if (positions == shown_positions && colour == shown_colour) return;
    shown_positions = positions;
    shown_colour    = colour;
    for (uint8_t i = 0; i < 3; i++) gpio_write_pin(colour_pins[i], (colour >> i) & 1);
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
