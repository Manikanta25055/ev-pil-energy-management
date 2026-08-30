#pragma once
#include <stddef.h>
#include <stdint.h>

#define EVPIL_MAGIC        0xE71Cu
#define EVPIL_HEADER_SIZE  12
#define EVPIL_CRC_SIZE     2
#define EVPIL_MAX_PAYLOAD  255

#define EVPIL_STATE      1
#define EVPIL_ACTUATION  2
#define EVPIL_STEP_REQ   3

#define EVPIL_ERR_SHORT  (-1)
#define EVPIL_ERR_MAGIC  (-2)
#define EVPIL_ERR_CRC    (-3)
#define EVPIL_ERR_TYPE   (-4)
#define EVPIL_ERR_CAP    (-5)

typedef struct {
    uint8_t        type;
    uint32_t       seq;
    uint32_t       t_us;
    uint8_t        len;
    const uint8_t *payload;   /* points into the caller's buffer, not copied */
} evpil_frame_t;

uint16_t evpil_crc16(const uint8_t *data, size_t len);

int evpil_pack(uint8_t *out, size_t out_cap, uint8_t type,
               uint32_t seq, uint32_t t_us,
               const uint8_t *payload, uint8_t len);

int evpil_unpack(const uint8_t *buf, size_t len, evpil_frame_t *out);
