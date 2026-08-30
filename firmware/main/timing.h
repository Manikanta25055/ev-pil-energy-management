#pragma once
#include <stdint.h>
#include "soc/gpio_struct.h"

#define TIMING_CH_CTRL   4    /* GPIO4  -> AD3 DIO0 */
#define TIMING_CH_INFER  5    /* GPIO5  -> AD3 DIO1 */
#define TIMING_CH_COMM   6    /* GPIO6  -> AD3 DIO2 */

void timing_init(void);

/* Single-register writes: a few cycles, so the pin edge tracks the task
   boundary closely enough not to bias the measurement. */
#define TIMING_MARK_HIGH(ch)  do { GPIO.out_w1ts = (1u << (ch)); } while (0)
#define TIMING_MARK_LOW(ch)   do { GPIO.out_w1tc = (1u << (ch)); } while (0)
