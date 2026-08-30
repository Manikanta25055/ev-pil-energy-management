from __future__ import annotations

import numpy as np
import pytest

from evpil.forecast.baselines import drift, persistence
from evpil.forecast.windows import FEATURE_COLUMNS

I = FEATURE_COLUMNS.index("i_batt_a")
V = FEATURE_COLUMNS.index("v_batt_v")


def _window(power_series: list[float], voltage: float = 400.0) -> np.ndarray:
    X = np.zeros((1, len(power_series), len(FEATURE_COLUMNS)), dtype=np.float32)
    X[0, :, V] = voltage
    X[0, :, I] = np.array(power_series) / voltage
    return X


def test_persistence_holds_the_last_observed_power_flat():
    X = _window([1000.0, 2000.0, 7000.0])
    np.testing.assert_allclose(persistence(X, 4), np.full((1, 4), 7000.0), rtol=1e-5)


def test_persistence_reads_power_from_the_window_not_from_a_target():
    # Nothing in the call carries the answer, which is the point: a baseline
    # that could see targets would not be a baseline.
    X = _window([500.0] * 6)
    assert persistence(X, 3).shape == (1, 3)


def test_drift_continues_a_straight_line_exactly():
    X = _window([0.0, 1000.0, 2000.0, 3000.0, 4000.0])
    np.testing.assert_allclose(
        drift(X, 3, steps=5), [[5000.0, 6000.0, 7000.0]], rtol=1e-4
    )


def test_drift_on_a_flat_window_reduces_to_persistence():
    X = _window([3000.0] * 5)
    np.testing.assert_allclose(drift(X, 4, steps=5), persistence(X, 4), atol=1e-3)


def test_drift_refuses_a_slope_it_cannot_measure():
    X = _window([1.0] * 5)
    with pytest.raises(ValueError, match="steps must be at least 2"):
        drift(X, 3, steps=1)
    with pytest.raises(ValueError, match="exceeds"):
        drift(X, 3, steps=9)


def test_a_zero_length_horizon_is_rejected_rather_than_returned_empty():
    X = _window([1000.0] * 4)
    with pytest.raises(ValueError, match="horizon must be at least 1"):
        persistence(X, 0)
