// Copyright 2026 josemanuque
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

#include "quantum.h"

/*
 * Bluetooth keycodes (keyboard level, QK_KB_0…). The same keys as the stock firmware:
 *   BT_HST1…BT_HST5  Fn+Q/W/E/R/T  tap: Bluetooth, device 1–5.  hold 3 s: pair a new device in that slot
 *   BT_MODE          Fn+P          tap: switch wired <-> Bluetooth.  hold 3 s: pair the current slot
 *   BT_CLR           Fn+Backspace  hold 3 s: forget every paired device
 *   BT_BATT          Fn+Space      show the battery level on the side lights
 */
enum rk71_keycodes {
    BT_HST1 = QK_KB_0,
    BT_HST2,
    BT_HST3,
    BT_HST4,
    BT_HST5,
    BT_MODE,
    BT_CLR,
    BT_BATT,
};

/* Keyboard lighting is on and the computer is awake (used for the side lights). */
bool rk71_rgb_lighting_on(void);
