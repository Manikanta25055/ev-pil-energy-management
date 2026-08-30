#include "link.h"
#include "protocol.h"
#include "driver/gpio.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <string.h>

#if LINK_TRANSPORT == 1
#include "driver/usb_serial_jtag.h"
#else
#include "driver/uart.h"
#endif

/* Both transports are wrapped to the same two primitives, `link_rx_bytes` and
   `link_write`, so the framing logic below is written once and the choice of
   transport cannot change how a frame is assembled. */

#if LINK_TRANSPORT == 1

void link_init(void)
{
    usb_serial_jtag_driver_config_t cfg =
        USB_SERIAL_JTAG_DRIVER_CONFIG_DEFAULT();
    cfg.rx_buffer_size = LINK_RX_BUFSZ * 2;
    cfg.tx_buffer_size = LINK_RX_BUFSZ * 2;
    ESP_ERROR_CHECK(usb_serial_jtag_driver_install(&cfg));
}

static int link_rx_bytes(uint8_t *dst, size_t want, uint32_t wait_ms)
{
    return usb_serial_jtag_read_bytes(dst, want, pdMS_TO_TICKS(wait_ms));
}

int link_write(const uint8_t *buf, size_t len)
{
    int n = usb_serial_jtag_write_bytes(buf, len, pdMS_TO_TICKS(2));
    return n;
}

#else

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

static int link_rx_bytes(uint8_t *dst, size_t want, uint32_t wait_ms)
{
    return uart_read_bytes(LINK_UART_NUM, dst, want, pdMS_TO_TICKS(wait_ms));
}

int link_write(const uint8_t *buf, size_t len)
{
    return uart_write_bytes(LINK_UART_NUM, (const char *) buf, len);
}

#endif

int link_read_frame(uint8_t *buf, size_t cap, uint32_t timeout_ms)
{
    int64_t deadline = esp_timer_get_time() + (int64_t) timeout_ms * 1000;
    size_t have = 0;

    while (esp_timer_get_time() < deadline) {
        /* Fill the header first so the payload length is known. */
        while (have < EVPIL_HEADER_SIZE) {
            int n = link_rx_bytes(buf + have, EVPIL_HEADER_SIZE - have, 1);
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
            int n = link_rx_bytes(buf + have, total - have, 1);
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
