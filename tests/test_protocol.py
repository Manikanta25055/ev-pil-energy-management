import struct
import pytest
from evpil.protocol import (
    STATE_FIELDS,
    BadFrame, FrameType, crc16_ccitt, pack_actuation, pack_frame,
    pack_state, unpack_frame,
)

# Derived, not written down: adding a state field must not break tests
# that are about framing rather than about the field list.
N_STATE = len(STATE_FIELDS)


def test_crc16_known_vector():
    # CRC-16/CCITT-FALSE of b"123456789" is 0x29B1 (standard check value).
    assert crc16_ccitt(b"123456789") == 0x29B1


def test_crc16_empty():
    assert crc16_ccitt(b"") == 0xFFFF


def test_pack_frame_layout():
    frame = pack_frame(FrameType.STEP_REQ, seq=7, t_us=123456, payload=b"")
    assert len(frame) == 14
    assert struct.unpack_from("<H", frame, 0)[0] == 0xE71C
    assert frame[2] == 3
    assert frame[3] == 0
    assert struct.unpack_from("<I", frame, 4)[0] == 7
    assert struct.unpack_from("<I", frame, 8)[0] == 123456


def test_roundtrip_state():
    values = [12.5, 0.75, 0.62, -18.0, 352.25, 21.0, 0.035, 480.0,
              13.0, 0.5, 24.5][:N_STATE]
    assert len(values) == N_STATE, "extend the vector for the new field"
    frame = pack_state(seq=99, t_us=1_000_000, values=values)
    assert len(frame) == 14 + 4 * N_STATE

    ftype, seq, t_us, payload = unpack_frame(frame)
    assert ftype is FrameType.STATE
    assert seq == 99
    assert t_us == 1_000_000

    got = list(struct.unpack(f"<{N_STATE}f", payload))
    assert got == pytest.approx(values, rel=1e-6)


def test_roundtrip_actuation():
    values = [145.0, 0.4, 30000.0, 0.15]
    frame = pack_actuation(seq=1, t_us=5, values=values)
    assert len(frame) == 30

    ftype, seq, t_us, payload = unpack_frame(frame)
    assert ftype is FrameType.ACTUATION
    assert list(struct.unpack("<4f", payload)) == pytest.approx(values, rel=1e-6)


def test_corrupt_payload_rejected():
    frame = bytearray(pack_state(1, 1, [0.0] * N_STATE))
    frame[20] ^= 0xFF
    with pytest.raises(BadFrame, match="crc"):
        unpack_frame(bytes(frame))


def test_bad_magic_rejected():
    frame = bytearray(pack_state(1, 1, [0.0] * N_STATE))
    frame[0] ^= 0xFF
    with pytest.raises(BadFrame, match="magic"):
        unpack_frame(bytes(frame))


def test_truncated_frame_rejected():
    frame = pack_state(1, 1, [0.0] * N_STATE)
    with pytest.raises(BadFrame, match="short"):
        unpack_frame(frame[:10])


def test_wrong_state_payload_length():
    with pytest.raises(ValueError, match=f"{N_STATE} values"):
        pack_state(1, 1, [0.0] * (N_STATE - 1))


def test_shared_vector_for_c_parity():
    """This exact frame is asserted byte-for-byte in firmware/host_test/test_protocol.c."""
    frame = pack_actuation(seq=0x01020304, t_us=0x0A0B0C0D,
                           values=[1.0, 0.5, 0.25, 0.125])
    assert frame.hex() == (
        "1ce7"      # magic 0xE71C, little-endian
        "02"        # type ACTUATION
        "10"        # payload length 16
        "04030201"  # seq  0x01020304
        "0d0c0b0a"  # t_us 0x0A0B0C0D
        "0000803f"  # 1.0f
        "0000003f"  # 0.5f
        "0000803e"  # 0.25f
        "0000003e"  # 0.125f
        "9060"      # crc 0x6090
    )