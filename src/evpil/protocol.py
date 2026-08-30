"""PIL frame protocol shared by the host plant and the ESP32-S3 firmware.

The C mirror lives in firmware/main/protocol.c and is validated against the
same byte vectors. A silent encoding mismatch between the two is the hardest
class of bug to find over a serial link, so the duplication is intentional.
"""

from __future__ import annotations

import struct
from collections.abc import Sequence
from enum import IntEnum

MAGIC = 0xE71C
HEADER_SIZE = 12
CRC_SIZE = 2
CRC16_INIT = 0xFFFF

_HEADER = struct.Struct("<HBBII")


class FrameType(IntEnum):
    STATE = 1
    ACTUATION = 2
    STEP_REQ = 3


class BadFrame(Exception):
    """Raised when a received buffer is not a valid frame."""


def crc16_ccitt(data: bytes) -> int:
    """CRC-16/CCITT-FALSE: poly 0x1021, init 0xFFFF, no reflection, no final xor."""
    crc = CRC16_INIT
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def pack_frame(ftype: FrameType, seq: int, t_us: int, payload: bytes) -> bytes:
    if len(payload) > 255:
        raise ValueError(f"payload too long: {len(payload)} bytes, max 255")

    head = _HEADER.pack(MAGIC, int(ftype), len(payload), seq & 0xFFFFFFFF,
                        t_us & 0xFFFFFFFF)
    body = head + payload
    return body + struct.pack("<H", crc16_ccitt(body))


def unpack_frame(buf: bytes) -> tuple[FrameType, int, int, bytes]:
    if len(buf) < HEADER_SIZE + CRC_SIZE:
        raise BadFrame(f"frame too short: {len(buf)} bytes")

    magic, raw_type, length, seq, t_us = _HEADER.unpack_from(buf, 0)
    if magic != MAGIC:
        raise BadFrame(f"bad magic: 0x{magic:04X}")

    total = HEADER_SIZE + length + CRC_SIZE
    if len(buf) < total:
        raise BadFrame(f"frame too short: need {total}, got {len(buf)}")

    (want,) = struct.unpack_from("<H", buf, HEADER_SIZE + length)
    got = crc16_ccitt(buf[: HEADER_SIZE + length])
    if want != got:
        raise BadFrame(f"crc mismatch: sent 0x{want:04X}, computed 0x{got:04X}")

    try:
        ftype = FrameType(raw_type)
    except ValueError as exc:
        raise BadFrame(f"unknown frame type: {raw_type}") from exc

    return ftype, seq, t_us, buf[HEADER_SIZE : HEADER_SIZE + length]


def pack_state(seq: int, t_us: int, values: Sequence[float]) -> bytes:
    """values: [v_mps, a_mps2, soc_frac, i_batt_a, v_batt_v, t_ambient_c,
    grade_rad, p_aux_w]"""
    if len(values) != 8:
        raise ValueError(f"STATE needs 8 values, got {len(values)}")
    return pack_frame(FrameType.STATE, seq, t_us, struct.pack("<8f", *values))


def pack_actuation(seq: int, t_us: int, values: Sequence[float]) -> bytes:
    """values: [torque_nm, regen_blend, p_limit_w]"""
    if len(values) != 3:
        raise ValueError(f"ACTUATION needs 3 values, got {len(values)}")
    return pack_frame(FrameType.ACTUATION, seq, t_us, struct.pack("<3f", *values))


def pack_step_req(seq: int, t_us: int) -> bytes:
    return pack_frame(FrameType.STEP_REQ, seq, t_us, b"")
