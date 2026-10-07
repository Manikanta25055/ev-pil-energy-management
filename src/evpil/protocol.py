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


# Extended in week 7. The reference speed and its derivative are sent by the
# host because the plant owns the road and the driver; the controller owns
# only how it follows them. Mirrored by STATE_PAYLOAD_BYTES in
# firmware/main/tasks.h, and the firmware rejects any other length outright
# rather than reading a short frame as a long one.
# Week 10: `t_batt_c` joins the state frame, because the deployed SAC actor
# observes pack temperature and the frame did not carry it. Nothing on the
# microcontroller can derive it -- it is a plant state the host owns -- so
# without it the policy would have to be fed a substitute, which is how a
# controller ends up running on an input nobody trained it on.
STATE_FIELDS: tuple[str, ...] = (
    "v_mps", "a_mps2", "soc_frac", "i_batt_a", "v_batt_v", "t_ambient_c",
    "grade_rad", "p_aux_w", "v_ref_mps", "a_ref_mps2", "t_batt_c",
)
# Also week 7: the auxiliary derate joins the actuation frame, so that the
# third dimension of the energy-management action reaches the plant instead of
# being applied only in the host-side simulation.
ACTUATION_FIELDS: tuple[str, ...] = (
    "torque_nm", "regen_blend", "p_limit_w", "aux_derate",
)

STATE_PAYLOAD_SIZE = 4 * len(STATE_FIELDS)
ACTUATION_PAYLOAD_SIZE = 4 * len(ACTUATION_FIELDS)


def pack_state(seq: int, t_us: int, values: Sequence[float]) -> bytes:
    """values in STATE_FIELDS order."""
    if len(values) != len(STATE_FIELDS):
        raise ValueError(
            f"STATE needs {len(STATE_FIELDS)} values, got {len(values)}")
    return pack_frame(FrameType.STATE, seq, t_us,
                      struct.pack(f"<{len(STATE_FIELDS)}f", *values))


def pack_actuation(seq: int, t_us: int, values: Sequence[float]) -> bytes:
    """values in ACTUATION_FIELDS order."""
    if len(values) != len(ACTUATION_FIELDS):
        raise ValueError(
            f"ACTUATION needs {len(ACTUATION_FIELDS)} values, got {len(values)}")
    return pack_frame(FrameType.ACTUATION, seq, t_us,
                      struct.pack(f"<{len(ACTUATION_FIELDS)}f", *values))


def unpack_state(payload: bytes) -> dict:
    if len(payload) != STATE_PAYLOAD_SIZE:
        raise BadFrame(
            f"STATE payload is {len(payload)} bytes, expected {STATE_PAYLOAD_SIZE}")
    return dict(zip(STATE_FIELDS,
                    struct.unpack(f"<{len(STATE_FIELDS)}f", payload)))


def unpack_actuation(payload: bytes) -> dict:
    if len(payload) != ACTUATION_PAYLOAD_SIZE:
        raise BadFrame(
            f"ACTUATION payload is {len(payload)} bytes, expected "
            f"{ACTUATION_PAYLOAD_SIZE}")
    return dict(zip(ACTUATION_FIELDS,
                    struct.unpack(f"<{len(ACTUATION_FIELDS)}f", payload)))


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

DIAG_FIELDS: tuple[str, ...] = (
    "loop_count", "rx_timeouts", "rx_bad", "infer_deadline_misses",
    "ctrl_wcet_us", "infer_wcet_us", "rtt_max_us",
    "period_min_us", "period_max_us",
    # Pipelined mode only: loops that acted on a state older than one step,
    # and the longest unbroken run of them. This is the degradation claim C5
    # is about, so it is counted rather than assumed to be small.
    "stale_steps", "stale_worst",
    # Week 7. These five separate three failures the earlier counters pooled.
    # `ctrl_late` is the loop missing its own deadline; `stale_steps` is the
    # host answering late. The open G3 question is whether the gate's
    # dropped-frame criterion should distinguish them, and it cannot be
    # answered without measuring them apart.
    "ctrl_late", "ctrl_fallback_steps", "limp_steps", "ems_fallback_steps",
    # esp_reset_reason() at startup. A watchdog reset can only be reported
    # after the reset, by the firmware that replaced the one that hung.
    "boot_reason",
    # Week 10, when the SAC actor was actually deployed. `actor_steps` counts
    # the outer steps the policy answered, against `ems_fallback_steps` for the
    # ones the rules had to cover, so the PIL campaign can say how much of a
    # run the learned controller was actually driving. `actor_wcet_us` is its
    # worst inference on silicon, which is the deployment cost that has to ship
    # next to any energy number it produces.
    "actor_steps", "actor_wcet_us",
    # Week 10's PIL campaign, 2026-09-21. The learned controller came out 8%
    # ahead of the rule manager on energy, and the explanation that fits every
    # number is that it applies a discharge power ceiling the rule manager
    # effectively does not: its peak current is lower in every setting, and
    # battery loss goes as the square of current. That explanation was an
    # inference, because the ceiling itself was never recorded -- only the
    # current downstream of it. These three make it observable.
    #
    # Watts, as integers, because DIAG carries uint32 and a watt is already
    # finer than the quantity is known. `p_limit_max_w` is the one that tests
    # the claim directly: a manager that never limits should report a ceiling
    # pinned at its maximum for the whole run.
    "p_limit_min_w", "p_limit_mean_w", "p_limit_max_w",
    # Speed-loop robustness arms, 2026-10-07. Which speed estimator the image
    # was built with (firmware SPEED_KALMAN: 0 none, 3 the two-state Kalman
    # estimate, 4 that plus the sensor-fault detector), because the arm is a
    # compile-time choice and a campaign cell has to be able to prove which
    # one it ran. Then what the detector did: control steps spent with the
    # flag up, and how many times it went up. On a healthy sensor both should
    # stay at zero, and that is a false-alarm measurement on real silicon.
    "speed_est_mode", "sensor_flag_steps", "sensor_alarms",
    # The most recent alarm, so that one can be explained afterwards: which
    # of the detector's tests raised it (1 gross, 2 frozen, 3 mean), the
    # control loop it was raised on, the speed reading at that moment and the
    # size of the mean gap, both in mm/s.
    "sensor_alarm_test", "sensor_alarm_loop", "sensor_alarm_v_mmps",
    "sensor_alarm_gap_mmps",
)

_DIAG = struct.Struct(f"<{len(DIAG_FIELDS)}I{N_JITTER_BINS}H")

# esp_reset_reason() values that matter here (esp_system.h). Anything else is
# reported by number rather than guessed at.
RESET_REASONS: dict[int, str] = {
    0: "unknown", 1: "power-on", 2: "external pin", 3: "software",
    4: "panic", 5: "interrupt watchdog", 6: "task watchdog", 7: "other watchdog",
    8: "deep sleep", 9: "brownout", 10: "SDIO", 11: "USB peripheral",
    12: "JTAG", 13: "efuse error", 14: "power glitch", 15: "CPU lockup",
}

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
