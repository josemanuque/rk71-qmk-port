// Copyright 2026 josemanuque
// SPDX-License-Identifier: GPL-2.0-or-later
//
// SPI0-slave link to the ITON Bluetooth module, done the way stock firmware V1.12 does it
// (init @0x68B0, send @0x5620, interrupt handler @0x5866, parser @0x5410):
//   - the module is the SPI master and drives the clock; the keyboard only answers
//   - to send, the keyboard preloads the first byte and raises A0; the module clocks the packet
//     out, and each received (dummy) byte is the cue to load the next one; A0 drops at the end
//   - while the module raises A1 it is sending to the keyboard; those bytes are collected and
//     parsed in the main loop
#include "rk71_bt.h"
#include <string.h>
#include <hal.h>
#include "gpio.h"
#include "timer.h"
#include "config.h"

#define SEND_TIMEOUT_MS 20

/* SPI0 register bits (SN32F240B datasheet, section 10.7). */
#define CTRL0_SPIEN (1u << 0)
#define CTRL0_SLAVE (1u << 3)
#define CTRL0_FRESET (3u << 6)
#define CTRL0_8BIT (7u << 8)
#define STAT_RX_EMPTY (1u << 2)
#define STAT_BUSY (1u << 4)
#define RXFIFOTH_FLAG (1u << 2) /* same bit in IE, RIS and IC */
#define AHBCLKEN_SPI0 (1u << 12)

static uint8_t           tx_buf[16];
static volatile uint8_t  tx_len, tx_idx;
static volatile bool     tx_busy;
static uint32_t          tx_started;
static volatile uint8_t  rx_buf[8];
static volatile uint8_t  rx_len;

static void fifo_reset(void) {
    SN_SPI0->CTRL0 |= CTRL0_FRESET;
    while ((SN_SPI0->CTRL0 & CTRL0_FRESET) == CTRL0_FRESET) {
        /* cleared by hardware within a few cycles */
    }
}

void rk71_bt_init(void) {
    gpio_set_pin_output(RK71_BT_REQ_PIN);
    gpio_write_pin_low(RK71_BT_REQ_PIN);
    gpio_set_pin_input_high(RK71_BT_DIR_PIN);

    SN_SYS1->AHBCLKEN |= AHBCLKEN_SPI0;
    /* 8-bit, slave, mode 0, MSB first, hardware chip-select (SELDIS = 0), FIFO thresholds 0. */
    SN_SPI0->CTRL0  = CTRL0_8BIT | CTRL0_SLAVE;
    SN_SPI0->CTRL1  = 0;
    SN_SPI0->CLKDIV = 2;
    fifo_reset();
    SN_SPI0->IC = 0xF;
    SN_SPI0->IE = RXFIFOTH_FLAG;
    nvicClearPending(SN32_SPI0_NUMBER);
    nvicEnableVector(SN32_SPI0_NUMBER, 3);
    SN_SPI0->CTRL0 |= CTRL0_SPIEN;
}

OSAL_IRQ_HANDLER(SN32_SPI0_HANDLER) {
    OSAL_IRQ_PROLOGUE();
    while (!(SN_SPI0->STAT & STAT_RX_EMPTY)) {
        uint8_t byte = SN_SPI0->DATA;
        if (gpio_read_pin(RK71_BT_DIR_PIN)) {
            /* module -> keyboard */
            if (rx_len < sizeof(rx_buf)) rx_buf[rx_len++] = byte;
        } else if (tx_busy) {
            /* keyboard -> module: one byte went out, load the next or finish */
            if (tx_idx < tx_len) {
                SN_SPI0->DATA = tx_buf[tx_idx++];
            } else {
                gpio_write_pin_low(RK71_BT_REQ_PIN);
                tx_busy = false;
            }
        }
    }
    SN_SPI0->IC = RXFIFOTH_FLAG;
    OSAL_IRQ_EPILOGUE();
}

bool rk71_bt_send(const uint8_t *data, uint8_t len) {
    if (len == 0 || len > sizeof(tx_buf)) return false;

    /* Wait for the previous packet, and never start while the module is talking. */
    uint32_t wait_start = timer_read32();
    while (tx_busy || gpio_read_pin(RK71_BT_DIR_PIN)) {
        if (tx_busy && TIMER_DIFF_32(timer_read32(), tx_started) > SEND_TIMEOUT_MS) {
            /* Module not clocking (switched off or stuck): drop the old packet and reset. */
            chSysLock();
            tx_busy = false;
            gpio_write_pin_low(RK71_BT_REQ_PIN);
            fifo_reset();
            chSysUnlock();
            return false;
        }
        if (!tx_busy && timer_elapsed32(wait_start) > SEND_TIMEOUT_MS) return false;
    }

    uint32_t t = timer_read32();
    while (SN_SPI0->STAT & STAT_BUSY) {
        if (timer_elapsed32(t) > SEND_TIMEOUT_MS) return false;
    }

    chSysLock();
    memcpy(tx_buf, data, len);
    tx_len  = len;
    tx_idx  = 1;
    tx_busy = true;
    fifo_reset();
    SN_SPI0->DATA = tx_buf[0];
    gpio_write_pin_high(RK71_BT_REQ_PIN); /* "packet ready": the module starts clocking */
    chSysUnlock();
    tx_started = timer_read32();
    return true;
}

void rk71_bt_task(void) {
    uint8_t packet[sizeof(rx_buf)];
    uint8_t n = 0;

    chSysLock();
    uint8_t have = rx_len;
    /* Complete packets: B1 xx (2 bytes) and B6 xx yy (3 bytes), as in the stock parser. */
    if ((have >= 2 && rx_buf[0] == 0xB1) || (have >= 3 && rx_buf[0] == 0xB6)) {
        n = rx_buf[0] == 0xB1 ? 2 : 3;
        for (uint8_t i = 0; i < n; i++) packet[i] = rx_buf[i];
        rx_len = 0;
    } else if (have && (rx_buf[0] != 0xB1 && rx_buf[0] != 0xB6)) {
        rx_len = 0; /* unknown packet: drop */
    } else if (have && !gpio_read_pin(RK71_BT_DIR_PIN)) {
        rx_len = 0; /* module finished sending but the packet is incomplete: drop */
    }
    chSysUnlock();

    if (n) rk71_bt_received(packet, n);
}
