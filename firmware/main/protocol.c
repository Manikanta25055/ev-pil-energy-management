#include "protocol.h"
#include <string.h>

uint16_t evpil_crc16(const uint8_t *data, size_t len)
{
    uint16_t crc = 0xFFFFu;
    for (size_t i = 0; i < len; i++) {
        crc ^= (uint16_t) data[i] << 8;
        for (int b = 0; b < 8; b++) {
            crc = (crc & 0x8000u) ? (uint16_t) ((crc << 1) ^ 0x1021u)
                                  : (uint16_t) (crc << 1);
        }
    }
    return crc;
}

static void put_u16(uint8_t *p, uint16_t v) { p[0] = (uint8_t) v; p[1] = (uint8_t) (v >> 8); }
static void put_u32(uint8_t *p, uint32_t v)
{
    p[0] = (uint8_t) v;         p[1] = (uint8_t) (v >> 8);
    p[2] = (uint8_t) (v >> 16); p[3] = (uint8_t) (v >> 24);
}
static uint16_t get_u16(const uint8_t *p) { return (uint16_t) (p[0] | (p[1] << 8)); }
static uint32_t get_u32(const uint8_t *p)
{
    return (uint32_t) p[0] | ((uint32_t) p[1] << 8)
         | ((uint32_t) p[2] << 16) | ((uint32_t) p[3] << 24);
}

int evpil_pack(uint8_t *out, size_t out_cap, uint8_t type,
               uint32_t seq, uint32_t t_us,
               const uint8_t *payload, uint8_t len)
{
    size_t total = EVPIL_HEADER_SIZE + (size_t) len + EVPIL_CRC_SIZE;
    if (out_cap < total) return EVPIL_ERR_CAP;

    put_u16(out + 0, EVPIL_MAGIC);
    out[2] = type;
    out[3] = len;
    put_u32(out + 4, seq);
    put_u32(out + 8, t_us);
    if (len && payload) memcpy(out + EVPIL_HEADER_SIZE, payload, len);

    uint16_t crc = evpil_crc16(out, EVPIL_HEADER_SIZE + (size_t) len);
    put_u16(out + EVPIL_HEADER_SIZE + len, crc);

    return (int) total;
}

int evpil_unpack(const uint8_t *buf, size_t len, evpil_frame_t *out)
{
    if (len < EVPIL_HEADER_SIZE + EVPIL_CRC_SIZE) return EVPIL_ERR_SHORT;
    if (get_u16(buf) != EVPIL_MAGIC)              return EVPIL_ERR_MAGIC;

    uint8_t type    = buf[2];
    uint8_t paylen  = buf[3];
    size_t  total   = EVPIL_HEADER_SIZE + (size_t) paylen + EVPIL_CRC_SIZE;
    if (len < total) return EVPIL_ERR_SHORT;

    uint16_t want = get_u16(buf + EVPIL_HEADER_SIZE + paylen);
    uint16_t got  = evpil_crc16(buf, EVPIL_HEADER_SIZE + (size_t) paylen);
    if (want != got) return EVPIL_ERR_CRC;

    if (type != EVPIL_STATE && type != EVPIL_ACTUATION && type != EVPIL_STEP_REQ) {
        return EVPIL_ERR_TYPE;
    }

    out->type    = type;
    out->seq     = get_u32(buf + 4);
    out->t_us    = get_u32(buf + 8);
    out->len     = paylen;
    out->payload = buf + EVPIL_HEADER_SIZE;
    return 0;
}
