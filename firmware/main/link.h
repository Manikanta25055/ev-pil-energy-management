#pragma once
#include <stddef.h>
#include <stdint.h>

#define LINK_UART_NUM   1
#define LINK_TX_GPIO    17
#define LINK_RX_GPIO    18
#define LINK_BAUD       921600
#define LINK_RX_BUFSZ   512

void link_init(void);

/* Reads one whole valid frame into `buf`. Returns bytes read, or a negative
   EVPIL_ERR_* code, or 0 on timeout. Resynchronises on magic. */
int link_read_frame(uint8_t *buf, size_t cap, uint32_t timeout_ms);

int link_write(const uint8_t *buf, size_t len);
