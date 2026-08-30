#include "timing.h"
#include "driver/gpio.h"

void timing_init(void)
{
    const uint64_t mask = (1ULL << TIMING_CH_CTRL)
                        | (1ULL << TIMING_CH_INFER)
                        | (1ULL << TIMING_CH_COMM);

    gpio_config_t cfg = {
        .pin_bit_mask = mask,
        .mode         = GPIO_MODE_OUTPUT,
        .pull_up_en   = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type    = GPIO_INTR_DISABLE,
    };
    ESP_ERROR_CHECK(gpio_config(&cfg));

    GPIO.out_w1tc = (uint32_t) mask;
}
