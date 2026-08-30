#pragma once
#include <stddef.h>
#include <stdint.h>

/* Transport selection.

   0 = external USB-UART on GPIO17/18 (UART1)
   1 = the S3's native USB-Serial-JTAG peripheral

   Spec section 9 leaves the choice open for G3 to settle on measured latency.
   Both are implemented so the comparison is a rebuild rather than a rewrite.
   The native peripheral needs no adapter, which is why it is the default: an
   external UART is only testable when one is physically attached, and a gate
   that cannot be run is not a gate. */
#ifndef LINK_TRANSPORT
#define LINK_TRANSPORT  1
#endif

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
