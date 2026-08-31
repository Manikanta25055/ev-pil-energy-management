"""The DIAG frame and the jitter histogram it carries.

G3's verdict is read out of these bytes, so the encoding is exercised on the
host side rather than trusted to match the firmware by inspection.
"""

from __future__ import annotations

import pytest

from evpil.protocol import (
    DIAG_FIELDS,
    DIAG_PAYLOAD_SIZE,
    JITTER_BIN_EDGES_US,
    N_JITTER_BINS,
    BadFrame,
    FrameType,
    jitter_percentile,
    pack_diag,
    unpack_diag,
    unpack_frame,
)


def _stats(**over) -> dict:
    base = {name: 0 for name in DIAG_FIELDS}
    base.update(over)
    return base


def test_a_diag_frame_round_trips_through_the_wire_format():
    hist = list(range(N_JITTER_BINS))
    stats = _stats(loop_count=60_000, rx_timeouts=3, period_max_us=10_412)

    frame = pack_diag(7, 1234, stats, hist)
    ftype, seq, t_us, payload = unpack_frame(frame)

    assert ftype is FrameType.DIAG
    assert (seq, t_us) == (7, 1234)
    got_stats, got_hist = unpack_diag(payload)
    assert got_stats == stats
    assert list(got_hist) == hist


def test_the_payload_is_the_size_the_firmware_writes():
    # Sixteen uint32 counters plus one uint16 per bin. The firmware builds the
    # same buffer from the same field order; a mismatch here is a silent
    # misparse, which on a binary link reads as plausible numbers rather than
    # as an error.
    assert DIAG_PAYLOAD_SIZE == 16 * 4 + N_JITTER_BINS * 2
    assert len(DIAG_FIELDS) == 16


def test_a_truncated_payload_is_refused_rather_than_misread():
    with pytest.raises(BadFrame, match="expected"):
        unpack_diag(b"\x00" * (DIAG_PAYLOAD_SIZE - 1))


def test_a_histogram_of_the_wrong_width_is_refused():
    with pytest.raises(ValueError, match="13 bins"):
        pack_diag(0, 0, _stats(), [0] * (N_JITTER_BINS - 1))


def test_a_percentile_lands_on_the_upper_edge_of_its_bin():
    hist = [0] * N_JITTER_BINS
    hist[0] = 990      # <= 25 us
    hist[3] = 9        # <= 150 us
    hist[6] = 1        # <= 500 us
    assert jitter_percentile(hist, 0.50) == 25.0
    assert jitter_percentile(hist, 0.99) == 25.0
    assert jitter_percentile(hist, 0.999) == 150.0


def test_the_overflow_bin_reports_infinity_rather_than_a_number():
    # The last bin has no upper edge. Returning its lower edge would look like
    # a measurement and would understate a gate that this is used to decide.
    hist = [0] * N_JITTER_BINS
    hist[0] = 50
    hist[-1] = 50
    assert jitter_percentile(hist, 0.99) == float("inf")


def test_a_percentile_is_an_upper_bound_and_never_understates():
    # Everything in a bin is at most its upper edge, so quoting the edge is the
    # conservative direction. A gate should fail on a bound it cannot meet.
    hist = [0] * N_JITTER_BINS
    hist[2] = 100      # all samples in (50, 100] us
    assert jitter_percentile(hist, 0.99) == float(JITTER_BIN_EDGES_US[2])


def test_an_empty_histogram_is_an_error_not_a_zero():
    with pytest.raises(ValueError, match="nothing was measured"):
        jitter_percentile([0] * N_JITTER_BINS, 0.99)


def test_the_bin_edges_match_the_firmware_table():
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1]
           / "firmware" / "main" / "tasks.c").read_text()
    start = src.index("k_jitter_edges_us[JITTER_N_BINS - 1] = {")
    body = src[start:src.index("}", start)]
    numbers = [int(tok) for tok in body.split("{")[1].replace(",", " ").split()]
    # The host labels the bins; the firmware fills them. If the two tables ever
    # drift, every reported percentile is quietly mislabelled.
    assert numbers == list(JITTER_BIN_EDGES_US)
