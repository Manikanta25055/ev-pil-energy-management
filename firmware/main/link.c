#include "link.h"
#include "protocol.h"
#include "driver/uart.h"
#include "driver/gpio.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <string.h>

void link_init(void)
{
    const uart_config_t cfg = {
        .baud_rate  = LINK_BAUD,
        .data_bits  = UART_DATA_8_BITS,
        .parity     = UART_PARITY_DISABLE,
        .stop_bits  = UART_STOP_BITS_1,
        .flow_ctrl  = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_DEFAULT,
    };
    ESP_ERROR_CHECK(uart_driver_install(LINK_UART_NUM, LINK_RX_BUFSZ * 2, 0, 0, NULL, 0));
    ESP_ERROR_CHECK(uart_param_config(LINK_UART_NUM, &cfg));
    ESP_ERROR_CHECK(uart_set_pin(LINK_UART_NUM, LINK_TX_GPIO, LINK_RX_GPIO,
                                 UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE));
}

int link_read_frame(uint8_t *buf, size_t cap, uint32_t timeout_ms)
{
    int64_t deadline = esp_timer_get_time() + (int64_t) timeout_ms * 1000;
    size_t have = 0;

    while (esp_timer_get_time() < deadline) {
        /* Fill the header first so the payload length is known. */
        while (have < EVPIL_HEADER_SIZE) {
            int n = uart_read_bytes(LINK_UART_NUM, buf + have,
                                    EVPIL_HEADER_SIZE - have, pdMS_TO_TICKS(1));
            if (n <= 0) {
                if (esp_timer_get_time() >= deadline) return 0;
                continue;
            }
            have += (size_t) n;
        }

        /* Resynchronise: slide until the buffer starts with magic. */
        if (buf[0] != 0x1C || buf[1] != 0xE7) {
            memmove(buf, buf + 1, have - 1);
            have -= 1;
            continue;
        }

        size_t total = EVPIL_HEADER_SIZE + buf[3] + EVPIL_CRC_SIZE;
        if (total > cap) { have = 0; continue; }

        while (have < total) {
            int n = uart_read_bytes(LINK_UART_NUM, buf + have, total - have,
                                    pdMS_TO_TICKS(1));
            if (n <= 0) {
                if (esp_timer_get_time() >= deadline) return 0;
                continue;
            }
            have += (size_t) n;
        }

        evpil_frame_t f;
        int rc = evpil_unpack(buf, total, &f);
        if (rc == 0) return (int) total;

        memmove(buf, buf + 2, have - 2);   /* drop this magic, rescan */
        have -= 2;
    }
    return 0;
}

int link_write(const uint8_t *buf, size_t len)
{
    return uart_write_bytes(LINK_UART_NUM, (const char *) buf, len);
}
