"""The residuals are checked two ways: against hand-computed physics, and for
agreement between the NumPy and Torch paths.

The second matters as much as the first. The training loss runs these functions
on tensors and the reported violation rate runs them on arrays, and a metric
that silently disagrees with the loss it describes is worse than no metric.
"""

from __future__ import annotations

import numpy as np
import pytest

from evpil.forecast.physics import (
    I,
    P,
    SOC,
    V,
    PhysicsConstants,
    ocv_v,
    r1_electrical,
    r2_charge,
    r3_terminal,
    residual_terms,
    violation_rate,
)

CONST = PhysicsConstants()


def _state(p, i, v, soc) -> np.ndarray:
    """One window, one horizon step, as a (1, n, 4) prediction tensor."""
    return np.stack([np.asarray(x, dtype=np.float64)
                     for x in (p, i, v, soc)], axis=-1)[None, ...]


# --- OCV --------------------------------------------------------------------

def test_ocv_matches_numpy_interpolation_including_the_clamps():
    soc = np.array([-0.2, 0.0, 0.05, 0.1, 0.5, 0.75, 1.0, 1.4])
    np.testing.assert_allclose(
        ocv_v(soc, CONST),
        np.interp(soc, CONST.ocv_soc_points, CONST.ocv_volts),
    )


def test_ocv_rises_monotonically_with_charge():
    soc = np.linspace(0.0, 1.0, 50)
    assert np.all(np.diff(ocv_v(soc, CONST)) >= 0.0)


# --- r1, electrical consistency ---------------------------------------------

def test_r1_is_zero_when_power_is_the_product_of_its_factors():
    y = _state([40_000.0], [100.0], [400.0], [0.5])
    assert r1_electrical(y)[0, 0] == pytest.approx(0.0)


def test_r1_reports_the_watts_by_which_a_prediction_is_inconsistent():
    y = _state([41_500.0], [100.0], [400.0], [0.5])
    assert r1_electrical(y)[0, 0] == pytest.approx(1_500.0)


# --- r2, charge conservation ------------------------------------------------

def test_r2_is_zero_for_a_charge_trajectory_that_matches_its_own_current():
    # 100 A discharge for 0.1 s steps out of a 61.7 Ah pack.
    i_a = 100.0
    d = i_a * CONST.dt_s / (3600.0 * CONST.capacity_ah)
    soc = [0.5, 0.5 - d, 0.5 - 2 * d, 0.5 - 3 * d]
    y = _state([0.0] * 4, [i_a] * 4, [0.0] * 4, soc)
    np.testing.assert_allclose(r2_charge(y, CONST), 0.0, atol=1e-12)


def test_r2_returns_one_charge_measurement_per_window_not_thirty():
    y = _state([0.0] * 6, [0.0] * 6, [0.0] * 6, [0.5] * 6)
    # There is one independent charge change in a horizon, not one per step.
    assert r2_charge(y, CONST).shape == (1,)


def test_r2_catches_charge_that_does_not_fall_while_current_flows():
    y = _state([0.0] * 4, [100.0] * 4, [0.0] * 4, [0.5] * 4)
    # Flat SoC under 100 A: the residual is the whole coulomb term, integrated
    # over three 0.1 s intervals by the trapezoidal rule.
    expected = 100.0 * 3 * CONST.dt_s / (3600.0 * CONST.capacity_ah)
    np.testing.assert_allclose(r2_charge(y, CONST), expected, rtol=1e-12)


def test_r2_has_the_sign_that_makes_discharge_lower_the_charge():
    # SoC rising while current is positive is doubly wrong, so the residual
    # must be larger than for flat SoC, not smaller.
    flat = _state([0.0] * 4, [100.0] * 4, [0.0] * 4, [0.5] * 4)
    rising = _state([0.0] * 4, [100.0] * 4, [0.0] * 4, [0.50, 0.51, 0.52, 0.53])
    assert abs(r2_charge(rising, CONST)).mean() > abs(r2_charge(flat, CONST)).mean()


# --- r3, terminal voltage ---------------------------------------------------

def test_r3_is_zero_on_the_thevenin_relation_it_encodes():
    soc, i_a = 0.5, 120.0
    v = float(np.interp(soc, CONST.ocv_soc_points, CONST.ocv_volts)) - i_a * CONST.r0_ohm
    y = _state([v * i_a], [i_a], [v], [soc])
    assert r3_terminal(y, CONST)[0, 0] == pytest.approx(0.0, abs=1e-9)


def test_r3_reports_the_volts_of_disagreement():
    soc, i_a = 0.5, 0.0
    ocv = float(np.interp(soc, CONST.ocv_soc_points, CONST.ocv_volts))
    y = _state([0.0], [i_a], [ocv - 2.5], [soc])
    assert r3_terminal(y, CONST)[0, 0] == pytest.approx(-2.5)


def test_r3_charges_the_ohmic_drop_against_the_predicted_current():
    soc = 0.5
    ocv = float(np.interp(soc, CONST.ocv_soc_points, CONST.ocv_volts))
    at_rest = _state([0.0], [0.0], [ocv], [soc])
    under_load = _state([0.0], [200.0], [ocv], [soc])
    assert r3_terminal(at_rest, CONST)[0, 0] == pytest.approx(0.0, abs=1e-9)
    assert under_load[0, 0, I] * CONST.r0_ohm == pytest.approx(2.0)
    assert r3_terminal(under_load, CONST)[0, 0] == pytest.approx(2.0)


# --- backend agreement ------------------------------------------------------

def test_the_torch_path_gives_the_same_residuals_as_the_numpy_one():
    torch = pytest.importorskip("torch")

    rng = np.random.default_rng(0)
    y = np.stack([
        rng.normal(20_000.0, 8_000.0, size=(6, 12)),
        rng.normal(60.0, 25.0, size=(6, 12)),
        rng.normal(380.0, 8.0, size=(6, 12)),
        rng.uniform(0.2, 0.9, size=(6, 12)),
    ], axis=-1)

    numpy_res = residual_terms(y, CONST)
    torch_res = residual_terms(torch.tensor(y, dtype=torch.float64), CONST)
    for name in ("r1", "r2", "r3"):
        np.testing.assert_allclose(
            numpy_res[name], torch_res[name].numpy(), rtol=1e-12, atol=1e-9
        )


def test_the_residuals_stay_differentiable_through_the_torch_path():
    torch = pytest.importorskip("torch")

    y = torch.tensor(
        [[[30_000.0, 80.0, 375.0, 0.60],
          [30_000.0, 80.0, 375.0, 0.59],
          [31_000.0, 82.0, 374.0, 0.58],
          [31_500.0, 84.0, 373.0, 0.57]]],
        dtype=torch.float64, requires_grad=True,
    )
    loss = sum(v.abs().mean() for v in residual_terms(y, CONST).values())
    loss.backward()
    # Every predicted channel has to receive gradient, or the residual is not
    # constraining the channel it names.
    assert torch.all(y.grad.abs().sum(dim=(0, 1)) > 0.0)


# --- violation rate ---------------------------------------------------------

def test_violation_rate_counts_steps_outside_the_stated_tolerance():
    y = _state([0.0, 0.0, 0.0, 0.0], [0.0] * 4, [0.0] * 4, [0.5] * 4)
    y[0, :2, P] = 5_000.0        # two of four steps inconsistent by 5 kW
    rates = violation_rate(y, CONST, tol={"r1": 1_000.0, "r2": 1.0, "r3": 1_000.0})
    assert rates["r1"] == pytest.approx(0.5)
    assert rates["r2"] == pytest.approx(0.0)


def test_violation_rate_refuses_to_invent_a_tolerance():
    y = _state([0.0] * 4, [0.0] * 4, [0.0] * 4, [0.5] * 4)
    with pytest.raises(KeyError, match="r3"):
        violation_rate(y, CONST, tol={"r1": 1.0, "r2": 1.0})


def test_a_horizon_too_short_for_a_centred_difference_is_an_error():
    from evpil.forecast.physics import r2_charge_pointwise

    y = _state([0.0, 0.0], [0.0, 0.0], [0.0, 0.0], [0.5, 0.5])
    with pytest.raises(ValueError, match="at least 3 horizon steps"):
        r2_charge_pointwise(y, CONST)


def test_the_pointwise_r2_is_kept_and_still_states_spec_4_2_literally():
    from evpil.forecast.physics import r2_charge_pointwise

    i_a = 100.0
    d = i_a * CONST.dt_s / (3600.0 * CONST.capacity_ah)
    soc = [0.5, 0.5 - d, 0.5 - 2 * d, 0.5 - 3 * d]
    y = _state([0.0] * 4, [i_a] * 4, [0.0] * 4, soc)
    np.testing.assert_allclose(r2_charge_pointwise(y, CONST), 0.0, atol=1e-12)


def test_a_held_charge_channel_defeats_the_pointwise_form_but_not_the_integral():
    """The measurement that motivated replacing spec 4.2's r2.

    A charge channel that steps once every four samples instead of every
    sample is consistent over the interval and wrong at every point in it.
    """
    from evpil.forecast.physics import r2_charge_pointwise

    i_a = 100.0
    step = i_a * 4 * CONST.dt_s / (3600.0 * CONST.capacity_ah)
    held = [0.5, 0.5, 0.5, 0.5, 0.5 - step, 0.5 - step, 0.5 - step, 0.5 - step,
            0.5 - 2 * step]
    n = len(held)
    y = _state([0.0] * n, [i_a] * n, [0.0] * n, held)

    coulomb = i_a / (3600.0 * CONST.capacity_ah)
    pointwise = np.abs(r2_charge_pointwise(y, CONST)).mean()
    integral = np.abs(r2_charge(y, CONST)).mean()

    # Pointwise error is of the same order as the whole coulomb term.
    assert pointwise > 0.3 * coulomb
    # Over the interval the same trajectory is consistent to within the half
    # sample the trapezoidal rule gives up at each end.
    assert integral < 0.02 * coulomb * n * CONST.dt_s


def test_constants_can_be_read_from_the_identified_parameter_file():
    import json
    from pathlib import Path

    payload = json.loads(
        (Path(__file__).resolve().parents[2] / "data" / "i3_params.json").read_text()
    )
    const = PhysicsConstants.from_params(payload)
    assert const.capacity_ah == pytest.approx(61.7)
    assert const.r0_ohm == pytest.approx(payload["identified"]["r0_ohm"])


def test_charge_conservation_is_off_by_default_and_says_why():
    from evpil.forecast.physics import ResidualWeights

    # A default that encodes a measurement about the dataset, so it is asserted
    # rather than left to be noticed.
    w = ResidualWeights()
    assert w.lambda_2 == 0.0
    assert w.lambda_1 > 0.0 and w.lambda_3 > 0.0
    assert "3.0 s horizon" in ResidualWeights.__doc__


def test_the_soc_channel_really_does_not_move_within_a_horizon():
    """The measurement behind that default, run against the archive itself.

    If a future reload of the data changes the charge channel's update
    behaviour, this fails and the default has to be reconsidered.
    """
    import pickle
    from pathlib import Path as _Path

    archive = _Path(__file__).resolve().parents[2] / "data" / "i3_canonical.pkl"
    if not archive.exists():
        pytest.skip("canonical archive not present")

    df = pickle.loads(archive.read_bytes())
    soc = df[df["trip_id"] == df["trip_id"].iloc[0]]["soc_frac"].to_numpy()
    horizon = 30
    starts = np.arange(0, len(soc) - horizon, 50)
    distinct = [len(np.unique(soc[a:a + horizon])) for a in starts]
    assert np.median(distinct) == 1.0
