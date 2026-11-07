#pragma once

/* Enable GPIO (PAL) and USB — disable everything else to save flash */
#define HAL_USE_PAL             TRUE
#define HAL_USE_USB             TRUE

#define HAL_USE_ADC             FALSE
#define HAL_USE_CAN             FALSE
#define HAL_USE_DAC             FALSE
#define HAL_USE_EXT             FALSE
#define HAL_USE_GPT             FALSE
#define HAL_USE_I2C             FALSE
#define HAL_USE_I2S             FALSE
#define HAL_USE_ICU             FALSE
#define HAL_USE_MAC             FALSE
#define HAL_USE_MMC_SPI         FALSE
#define HAL_USE_PWM             FALSE
#define HAL_USE_RTC             FALSE
#define HAL_USE_SDC             FALSE
#define HAL_USE_SERIAL          FALSE
#define HAL_USE_SERIAL_USB      FALSE
#define HAL_USE_SPI             FALSE
#define HAL_USE_ST              TRUE   /* SysTick — required for QMK timers */
#define HAL_USE_UART            FALSE
#define HAL_USE_WDG             FALSE

#include_next <halconf.h>
