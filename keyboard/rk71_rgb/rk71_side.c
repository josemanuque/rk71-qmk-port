// Copyright 2026 josemanuque
// SPDX-License-Identifier: GPL-2.0-or-later
#include "rk71_side.h"
#include <ch.h>
#include "gpio.h"
#include "timer.h"
#include "wait.h"

static const pin_t colour_pins[3]   = {D6, D4, D5};                /* red, green, blue */
static const pin_t position_pins[6] = {B9, B10, B11, B12, C0, C1}; /* far … near */

static uint8_t shown_positions = 0xFF, shown_colour = 0xFF;

/*
 * Red, green and blue are lit one after another, never together: the LEDs share a supply per
 * position, and with red lit (lowest forward voltage) green and blue cannot light ("white" came
 * out red). Each 1.2 ms frame is: red on for t[0], green for t[1], blue for t[2], then off for
 * the rest. The on-times set both the colour balance (the side LEDs sit behind a bluish diffuser)
 * and the brightness. 1.2 ms frames = each colour repeats 833 times a second.
 */
#define FRAME_TICKS TIME_US2I(1200)
#define MAX_TICKS (FRAME_TICKS / 3) /* one colour at full balance and brightness */
#define MIN_TICKS 3                 /* shorter phases are skipped (timer overhead) */

static volatile uint16_t      on_ticks[4]; /* red, green, blue, off (ticks, < 65536) */
static uint8_t                phase;
static virtual_timer_t        frame_timer;
static uint8_t                balance[3] = {31, 31, 31}; /* 0..31 per colour */
static uint8_t                level      = 255;          /* brightness 0..255 */

static void phase_tick(virtual_timer_t *vtp, void *p) {
    (void)p;
    for (uint8_t i = 0; i < 3; i++) gpio_write_pin_low(colour_pins[i]);
    sysinterval_t d = 0;
    for (uint8_t n = 0; n < 4; n++) {
        phase = (phase + 1) % 4;
        d     = on_ticks[phase];
        if (d >= MIN_TICKS) break;
    }
    if (d < MIN_TICKS) d = FRAME_TICKS; /* everything off */
    if (phase < 3 && on_ticks[phase] >= MIN_TICKS) gpio_write_pin_high(colour_pins[phase]);
    chVTSetI(vtp, d, phase_tick, NULL);
}

static void recompute(void) {
    sysinterval_t t[4], used = 0;
    for (uint8_t c = 0; c < 3; c++) {
        t[c] = 0;
        if ((shown_colour >> c) & 1 && shown_colour != 0xFF) {
            t[c] = (sysinterval_t)((uint32_t)MAX_TICKS * balance[c] * level / (31u * 255u));
        }
        used += t[c];
    }
    t[3] = FRAME_TICKS - used;
    chSysLock();
    for (uint8_t i = 0; i < 4; i++) on_ticks[i] = t[i];
    chSysUnlock();
}

void side_init(void) {
    gpio_set_pin_output(B8); /* stock keeps B8 high; low makes Win/Alt glow faintly */
    gpio_write_pin_high(B8);
    for (uint8_t i = 0; i < 3; i++) gpio_set_pin_output(colour_pins[i]);
    for (uint8_t i = 0; i < 6; i++) gpio_set_pin_output(position_pins[i]);
    side_show(0, 0);
    chVTObjectInit(&frame_timer);
    chVTSet(&frame_timer, FRAME_TICKS, phase_tick, NULL);
}

void side_set_tuning(uint8_t red, uint8_t green, uint8_t blue) {
    balance[0] = red & 31;
    balance[1] = green & 31;
    balance[2] = blue & 31;
    recompute();
}

void side_set_level(uint8_t new_level) {
    if (new_level == level) return;
    level = new_level;
    recompute();
}

void side_show(uint8_t positions, uint8_t colour) {
    if (!positions || !colour) positions = colour = 0;
    if (positions == shown_positions && colour == shown_colour) return;
    shown_positions = positions;
    shown_colour    = colour;
    recompute(); /* the colour lines are driven by phase_tick() */
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
