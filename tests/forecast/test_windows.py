"""What these tests defend is the shape of the supervision, not its accuracy.

A leaked window scores well. That is the whole problem with it, and it is why
these checks assert on indices and group labels rather than on error metrics.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from evpil.forecast.windows import (
    FEATURE_COLUMNS,
    TARGET_COLUMN,
    WindowError,
    WindowSpec,
    add_battery_power,
    build_dataset,
    contiguous_runs,
    last_observed_power,
)


def _trip(trip_id: str, n: int, dt: float = 0.1, t0: float = 0.0) -> pd.DataFrame:
    k = np.arange(n, dtype=float)
    return pd.DataFrame({
        "t_s": t0 + k * dt,
        "v_mps": k,
        "a_mps2": -k,
        "soc_frac": 0.8 - k * 1e-5,
        "i_batt_a": k + 1.0,
        "v_batt_v": np.full(n, 400.0),
        "t_ambient_c": np.full(n, 10.0),
        "grade_rad": np.zeros(n),
        "p_aux_w": np.full(n, 500.0),
        "trip_id": trip_id,
    })


def test_battery_power_is_current_times_voltage_with_discharge_positive():
    df = add_battery_power(_trip("A", 3))
    assert df[TARGET_COLUMN].tolist() == [400.0, 800.0, 1200.0]


def test_inputs_and_targets_never_share_a_sample():
    spec = WindowSpec(seq_len=4, horizon=3, stride=1)
    X, Y, _, _ = build_dataset(_trip("A", 10), ["A"], spec)

    # v_mps is the sample index by construction, so the input channel reads
    # back the exact rows the window covers.
    for i in range(len(Y)):
        covered = X[i, :, FEATURE_COLUMNS.index("v_mps")]
        assert covered.tolist() == [float(i + j) for j in range(4)]
        # First predicted step is row i+4, one past the last input row i+3.
        assert Y[i, 0] == pytest.approx(400.0 * (i + 4 + 1))


def test_window_count_is_exactly_what_the_geometry_allows():
    spec = WindowSpec(seq_len=4, horizon=3, stride=1)
    _, Y, _, _ = build_dataset(_trip("A", 10), ["A"], spec)
    assert len(Y) == 10 - 7 + 1


def test_stride_subsamples_without_moving_the_first_window():
    dense = build_dataset(_trip("A", 20), ["A"], WindowSpec(4, 3, 1))[1]
    sparse = build_dataset(_trip("A", 20), ["A"], WindowSpec(4, 3, 5))[1]
    assert len(sparse) == len(range(0, 20 - 7 + 1, 5))
    np.testing.assert_array_equal(sparse[0], dense[0])
    np.testing.assert_array_equal(sparse[1], dense[5])


def test_no_window_spans_two_trips():
    df = pd.concat([_trip("A", 9), _trip("B", 9)], ignore_index=True)
    spec = WindowSpec(seq_len=4, horizon=3, stride=1)
    _, Y, groups, _ = build_dataset(df, ["A", "B"], spec)

    # Three windows per trip, six total. Concatenating the trips and windowing
    # blindly would yield twelve, six of which would straddle the seam.
    assert len(Y) == 6
    assert sorted(np.unique(groups)) == ["A", "B"]
    assert (groups == "A").sum() == 3


def test_a_logging_gap_cuts_the_run_rather_than_stretching_the_horizon():
    df = _trip("A", 16)
    # A 5 s hole in a 10 Hz log. Windowing across it would call 3.0 s of
    # horizon something that actually spans 8.0 s.
    df.loc[8:, "t_s"] = df.loc[8:, "t_s"] + 5.0

    assert contiguous_runs(df["t_s"].to_numpy()) == [(0, 8), (8, 16)]

    spec = WindowSpec(seq_len=4, horizon=3, stride=1)
    _, Y, _, _ = build_dataset(df, ["A"], spec)
    assert len(Y) == 2 * (8 - 7 + 1)


def test_trips_too_short_for_one_window_are_dropped_not_padded():
    df = pd.concat([_trip("A", 6), _trip("B", 12)], ignore_index=True)
    _, Y, groups, _ = build_dataset(df, ["A", "B"], WindowSpec(4, 3, 1))
    assert set(np.unique(groups)) == {"B"}
    assert len(Y) == 12 - 7 + 1


def test_no_trip_yields_a_window_is_an_error_not_an_empty_array():
    with pytest.raises(WindowError, match="contiguous samples"):
        build_dataset(_trip("A", 5), ["A"], WindowSpec(4, 3, 1))


def test_requesting_an_absent_trip_fails_loudly():
    with pytest.raises(WindowError, match="not present"):
        build_dataset(_trip("A", 20), ["A", "Z"], WindowSpec(4, 3, 1))


def test_t0_reports_the_time_of_the_first_predicted_step():
    _, _, _, t0 = build_dataset(_trip("A", 10, dt=0.1), ["A"], WindowSpec(4, 3, 1))
    np.testing.assert_allclose(t0, [0.4, 0.5, 0.6, 0.7])


def test_last_observed_power_reads_the_final_input_step():
    X, Y, _, _ = build_dataset(_trip("A", 10), ["A"], WindowSpec(4, 3, 1))
    # Window i ends at row i+3, where power is 400*(i+3+1).
    np.testing.assert_allclose(
        last_observed_power(X), [400.0 * (i + 4) for i in range(len(Y))]
    )


def test_the_target_is_not_reachable_as_a_named_feature():
    # p_batt_w must never be selectable as an input: predicting it from itself
    # is the failure mode the whole module is arranged to prevent.
    assert TARGET_COLUMN not in FEATURE_COLUMNS
