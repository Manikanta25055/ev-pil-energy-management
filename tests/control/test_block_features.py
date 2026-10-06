import numpy as np
import pytest

from evpil.control.block_features import (
    BLOCK_STEPS, FEATURE_NAMES, FEATURE_SCALE, WINDOW_BLOCKS, BlockFeatures,
    FeatureWindow,
)

IDX = {name: i for i, name in enumerate(FEATURE_NAMES)}


def feed(acc, n, **kw):
    """Push n identical samples; return the blocks that came out."""
    base = dict(v_meas_mps=10.0, a_meas_mps2=0.0, torque_nm=50.0,
                i_batt_a=20.0, v_ref_mps=10.0, a_ref_mps2=0.0)
    base.update(kw)
    out = [acc.push(**base) for _ in range(n)]
    return [b for b in out if b is not None]


def test_a_block_comes_out_every_tenth_sample_and_not_before():
    acc = BlockFeatures()
    assert feed(acc, BLOCK_STEPS - 1) == []
    assert len(feed(acc, 1)) == 1
    assert len(feed(acc, 3 * BLOCK_STEPS)) == 3


def test_a_steady_signal_has_its_means_and_no_spread():
    (b,) = feed(BlockFeatures(), BLOCK_STEPS)
    raw = b * FEATURE_SCALE
    assert raw[IDX["v_mean"]] == pytest.approx(10.0)
    assert raw[IDX["tq_mean"]] == pytest.approx(50.0)
    assert raw[IDX["i_mean"]] == pytest.approx(20.0)
    assert raw[IDX["v_ref"]] == pytest.approx(10.0)
    for name in ("dv_std", "a_std", "i_std", "tq_flips"):
        assert raw[IDX[name]] == 0.0


def test_speed_jitter_shows_up_as_the_spread_of_the_differences():
    # Speed alternating by +-d from one sample to the next: every 10 ms
    # difference is +-2d, alternating, so their standard deviation is 2d.
    acc, d = BlockFeatures(), 0.05
    feed(acc, BLOCK_STEPS)                      # settle the carried sample
    blocks = []
    for k in range(2 * BLOCK_STEPS):
        blocks += feed(acc, 1, v_meas_mps=10.0 + (d if k % 2 else -d))
    raw = blocks[-1] * FEATURE_SCALE
    assert raw[IDX["dv_std"]] == pytest.approx(2 * d, rel=1e-4)
    assert raw[IDX["v_mean"]] == pytest.approx(10.0, abs=1e-5)


def test_a_large_offset_does_not_swamp_a_small_spread():
    # The reason the sums are taken about the block's first sample. Summing
    # squares of 300 A in single precision loses a 0.1 A ripple entirely.
    acc = BlockFeatures()
    blocks = []
    for k in range(BLOCK_STEPS):
        blocks += feed(acc, 1, i_batt_a=300.0 + (0.1 if k % 2 else -0.1))
    raw = blocks[-1] * FEATURE_SCALE
    assert raw[IDX["i_std"]] == pytest.approx(0.1, rel=1e-3)


def test_torque_sign_changes_are_counted_across_the_block_boundary():
    acc = BlockFeatures()
    feed(acc, BLOCK_STEPS, torque_nm=5.0)
    blocks = []
    for k in range(BLOCK_STEPS):
        blocks += feed(acc, 1, torque_nm=-5.0 if k % 2 == 0 else 5.0)
    raw = blocks[-1] * FEATURE_SCALE
    # Ten samples, each of the opposite sign to the one before it, the first
    # of them against the last sample of the previous block.
    assert raw[IDX["tq_flips"]] == BLOCK_STEPS


def test_zero_torque_is_not_a_sign_change():
    acc = BlockFeatures()
    blocks = []
    for tq in [5.0, 0.0, 5.0, 0.0, -5.0, 0.0, 0.0, 5.0, 5.0, 5.0]:
        blocks += feed(acc, 1, torque_nm=tq)
    assert (blocks[-1] * FEATURE_SCALE)[IDX["tq_flips"]] == 0.0


def test_the_window_is_oldest_first_and_zero_padded_until_full():
    w = FeatureWindow()
    for k in range(3):
        w.push(np.full(len(FEATURE_NAMES), float(k + 1), dtype=np.float32))
    a = w.as_array()
    assert a.shape == (WINDOW_BLOCKS, len(FEATURE_NAMES))
    assert not w.full
    assert np.all(a[:-3] == 0.0)
    assert [a[-3, 0], a[-2, 0], a[-1, 0]] == [1.0, 2.0, 3.0]


def test_a_full_window_drops_its_oldest_block():
    w = FeatureWindow()
    for k in range(WINDOW_BLOCKS + 5):
        w.push(np.full(len(FEATURE_NAMES), float(k), dtype=np.float32))
    a = w.as_array()
    assert w.full
    assert a[0, 0] == 5.0 and a[-1, 0] == WINDOW_BLOCKS + 4
