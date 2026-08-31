#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "protocol.h"

static int failures = 0;

#define CHECK(cond, msg) do {                                  \
    if (!(cond)) { printf("FAIL: %s\n", msg); failures++; }    \
    else        { printf("ok:   %s\n", msg); }                 \
} while (0)

static void test_crc_known_vector(void)
{
    const uint8_t v[] = "123456789";
    CHECK(evpil_crc16(v, 9) == 0x29B1, "crc16 check value 0x29B1");
    CHECK(evpil_crc16(NULL, 0) == 0xFFFF, "crc16 of empty is 0xFFFF");
}

static void test_parity_with_python(void)
{
    /* Byte-for-byte identical to tests/test_protocol.py
       ::test_shared_vector_for_c_parity */
    float vals[4] = {1.0f, 0.5f, 0.25f, 0.125f};
    uint8_t payload[16];
    memcpy(payload, vals, 16);

    uint8_t frame[64];
    int n = evpil_pack(frame, sizeof frame, EVPIL_ACTUATION,
                       0x01020304u, 0x0A0B0C0Du, payload, 16);
    CHECK(n == 30, "actuation frame is 30 bytes");

    static const uint8_t expect[] = {
        0x1C, 0xE7,             /* magic  */
        0x02,                   /* type   */
        0x10,                   /* len 16 */
        0x04, 0x03, 0x02, 0x01, /* seq    */
        0x0D, 0x0C, 0x0B, 0x0A, /* t_us   */
        0x00, 0x00, 0x80, 0x3F, /* 1.0f   */
        0x00, 0x00, 0x00, 0x3F, /* 0.5f   */
        0x00, 0x00, 0x80, 0x3E, /* 0.25f  */
        0x00, 0x00, 0x00, 0x3E, /* 0.125f */
        0x90, 0x60,             /* crc 0x6090 */
    };
    CHECK(memcmp(frame, expect, 30) == 0, "frame bytes match Python exactly");
}

static void test_roundtrip(void)
{
    uint8_t payload[12] = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12};
    uint8_t frame[64];
    int n = evpil_pack(frame, sizeof frame, EVPIL_ACTUATION, 42, 99, payload, 12);
    CHECK(n > 0, "pack succeeds");

    evpil_frame_t f;
    CHECK(evpil_unpack(frame, (size_t) n, &f) == 0, "unpack succeeds");
    CHECK(f.type == EVPIL_ACTUATION, "type preserved");
    CHECK(f.seq == 42, "seq preserved");
    CHECK(f.t_us == 99, "t_us preserved");
    CHECK(f.len == 12, "len preserved");
    CHECK(memcmp(f.payload, payload, 12) == 0, "payload preserved");
}

static void test_rejects_corruption(void)
{
    uint8_t payload[12] = {0};
    uint8_t frame[64];
    int n = evpil_pack(frame, sizeof frame, EVPIL_ACTUATION, 1, 1, payload, 12);

    frame[15] ^= 0xFF;
    evpil_frame_t f;
    CHECK(evpil_unpack(frame, (size_t) n, &f) == EVPIL_ERR_CRC, "corrupt payload -> ERR_CRC");

    frame[15] ^= 0xFF;
    frame[0] ^= 0xFF;
    CHECK(evpil_unpack(frame, (size_t) n, &f) == EVPIL_ERR_MAGIC, "bad magic -> ERR_MAGIC");

    frame[0] ^= 0xFF;
    CHECK(evpil_unpack(frame, 8, &f) == EVPIL_ERR_SHORT, "truncated -> ERR_SHORT");
}

int main(void)
{
    test_crc_known_vector();
    test_parity_with_python();
    test_roundtrip();
    test_rejects_corruption();

    printf("\n%s (%d failures)\n", failures ? "FAILED" : "PASSED", failures);
    return failures != 0;
}
