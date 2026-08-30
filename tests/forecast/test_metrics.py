from __future__ import annotations

import numpy as np
import pytest

from evpil.forecast.metrics import (
    MetricError,
    bootstrap_ci,
    per_horizon,
    per_trip_rmse,
    skill_against,
)


def test_a_perfect_forecast_scores_zero_error_and_unit_r2():
    y = np.array([[1.0, 2.0], [3.0, 5.0], [4.0, 1.0]])
    m = per_horizon(y, y.copy())
    np.testing.assert_allclose(m.mae, [0.0, 0.0])
    np.testing.assert_allclose(m.rmse, [0.0, 0.0])
    np.testing.assert_allclose(m.r2, [1.0, 1.0])


def test_metrics_are_computed_per_step_and_not_pooled():
    y = np.array([[0.0, 0.0], [0.0, 0.0]])
    p = np.array([[1.0, 3.0], [1.0, 3.0]])
    m = per_horizon(y, p)
    # Pooling would report 2.0 at both steps and hide that the far step is
    # three times worse than the near one.
    np.testing.assert_allclose(m.mae, [1.0, 3.0])
    np.testing.assert_allclose(m.rmse, [1.0, 3.0])


def test_r2_is_zero_not_one_where_the_targets_do_not_vary():
    y = np.array([[5.0], [5.0], [5.0]])
    assert per_horizon(y, y.copy()).r2.tolist() == [0.0]


def test_predicting_the_mean_scores_r2_of_zero():
    y = np.array([[1.0], [2.0], [6.0]])
    p = np.full_like(y, y.mean())
    np.testing.assert_allclose(per_horizon(y, p).r2, [0.0], atol=1e-12)


def test_at_indexes_horizon_steps_from_one():
    y = np.zeros((2, 3))
    p = np.array([[1.0, 2.0, 3.0], [1.0, 2.0, 3.0]])
    m = per_horizon(y, p)
    assert m.at(1)["mae"] == pytest.approx(1.0)
    assert m.at(3)["mae"] == pytest.approx(3.0)
    with pytest.raises(MetricError, match="outside 1..3"):
        m.at(0)


def test_skill_is_the_fractional_rmse_reduction_the_gate_is_written_in():
    y = np.zeros((4, 1))
    base = np.full((4, 1), 10.0)
    model = np.full((4, 1), 8.5)
    np.testing.assert_allclose(skill_against(y, model, base), [0.15])


def test_skill_is_negative_when_the_model_loses_to_the_baseline():
    y = np.zeros((4, 1))
    assert skill_against(y, np.full((4, 1), 12.0), np.full((4, 1), 10.0))[0] < 0.0


def test_per_trip_rmse_separates_trips_rather_than_averaging_over_them():
    y = np.zeros((4, 1))
    p = np.array([[1.0], [1.0], [5.0], [5.0]])
    groups = np.array(["A", "A", "B", "B"])
    assert per_trip_rmse(y, p, groups) == {"A": pytest.approx(1.0), "B": pytest.approx(5.0)}


def test_per_trip_rmse_can_isolate_one_horizon_step():
    y = np.zeros((2, 2))
    p = np.array([[1.0, 9.0], [1.0, 9.0]])
    groups = np.array(["A", "A"])
    assert per_trip_rmse(y, p, groups, step=2)["A"] == pytest.approx(9.0)


def test_bootstrap_resamples_trips_so_an_outlier_trip_widens_the_interval():
    rng = np.random.default_rng(0)
    good = rng.normal(0.0, 1.0, size=(300, 1))
    bad = rng.normal(0.0, 20.0, size=(300, 1))
    y = np.zeros((600, 1))
    p = np.concatenate([good, bad])
    groups = np.array(["A"] * 300 + ["B"] * 300)

    rmse = lambda t, q: float(np.sqrt(((q - t) ** 2).mean()))
    lo, hi = bootstrap_ci(y, p, groups, rmse, n_boot=200)
    # Two trips, one twenty times noisier: any resample is all-A, all-B or
    # mixed, so the interval has to span from near 1 to near 20.
    assert lo < 3.0 < 15.0 < hi


def test_bootstrap_is_deterministic_for_a_given_seed():
    y = np.zeros((40, 1))
    p = np.random.default_rng(1).normal(size=(40, 1))
    groups = np.array(["A"] * 20 + ["B"] * 20)
    rmse = lambda t, q: float(np.sqrt(((q - t) ** 2).mean()))
    assert bootstrap_ci(y, p, groups, rmse, n_boot=50) == bootstrap_ci(
        y, p, groups, rmse, n_boot=50
    )


def test_a_single_trip_cannot_produce_a_between_trip_interval():
    y = np.zeros((10, 1))
    groups = np.array(["A"] * 10)
    with pytest.raises(MetricError, match="cannot express uncertainty"):
        bootstrap_ci(y, y.copy(), groups, lambda t, q: 0.0)


def test_mismatched_shapes_and_empty_input_are_refused():
    with pytest.raises(MetricError, match="shape mismatch"):
        per_horizon(np.zeros((3, 2)), np.zeros((3, 4)))
    with pytest.raises(MetricError, match="no windows"):
        per_horizon(np.zeros((0, 2)), np.zeros((0, 2)))
    with pytest.raises(MetricError, match="dimensions"):
        per_horizon(np.zeros(3), np.zeros(3))
