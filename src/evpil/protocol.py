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
    DIAG = 4


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


# Absolute deviation of the realised control period from its nominal value, in
# microseconds. Fixed edges rather than a mean and a standard deviation because
# G3 is stated as a p99 and a percentile needs a distribution. The MCU owns the
# histogram: it is the clock master (spec 4.5), and timing measured on a macOS
# host would carry the host's own scheduling noise (risk R5).
JITTER_BIN_EDGES_US: tuple[int, ...] = (
    25, 50, 100, 150, 200, 300, 500, 750, 1000, 1500, 2000, 5000,
)
N_JITTER_BINS = len(JITTER_BIN_EDGES_US) + 1

_DIAG = struct.Struct(f"<9I{N_JITTER_BINS}H")

DIAG_FIELDS: tuple[str, ...] = (
    "loop_count", "rx_timeouts", "rx_bad", "infer_deadline_misses",
    "ctrl_wcet_us", "infer_wcet_us", "rtt_max_us",
    "period_min_us", "period_max_us",
)

DIAG_PAYLOAD_SIZE = _DIAG.size


def pack_diag(seq: int, t_us: int, stats: dict, hist: Sequence[int]) -> bytes:
    """Encode the MCU's diagnostic counters and jitter histogram.

    Present on the host side so the same byte layout is exercised by the tests
    that check the decoder, rather than only by the firmware that produces it.
    """
    if len(hist) != N_JITTER_BINS:
        raise ValueError(f"histogram needs {N_JITTER_BINS} bins, got {len(hist)}")
    values = [int(stats[name]) for name in DIAG_FIELDS]
    return pack_frame(FrameType.DIAG, seq, t_us,
                      _DIAG.pack(*values, *(int(h) for h in hist)))


def unpack_diag(payload: bytes) -> tuple[dict, tuple[int, ...]]:
    """Decode a DIAG payload into its counters and its jitter histogram."""
    if len(payload) != DIAG_PAYLOAD_SIZE:
        raise BadFrame(
            f"DIAG payload is {len(payload)} bytes, expected {DIAG_PAYLOAD_SIZE}"
        )
    fields = _DIAG.unpack(payload)
    stats = dict(zip(DIAG_FIELDS, fields[: len(DIAG_FIELDS)]))
    return stats, tuple(fields[len(DIAG_FIELDS):])


def jitter_percentile(hist: Sequence[int], q: float) -> float:
    """Upper bound on the q-th percentile of absolute period deviation, in us.

    A histogram gives a bound, not a value: the answer is the upper edge of the
    bin the percentile falls in. Reporting the upper edge is the conservative
    direction, which is the right one for a gate. The overflow bin has no upper
    edge, so it returns infinity rather than a number that looks measured.
    """
    if len(hist) != N_JITTER_BINS:
        raise ValueError(f"histogram needs {N_JITTER_BINS} bins, got {len(hist)}")
    if not 0.0 < q < 1.0:
        raise ValueError(f"q must be in (0, 1), got {q}")

    total = sum(hist)
    if total == 0:
        raise ValueError("empty histogram: nothing was measured")

    target = q * total
    running = 0
    for k, count in enumerate(hist):
        running += count
        if running >= target:
            return float(JITTER_BIN_EDGES_US[k]) if k < len(JITTER_BIN_EDGES_US) \
                else float("inf")
    return float("inf")
