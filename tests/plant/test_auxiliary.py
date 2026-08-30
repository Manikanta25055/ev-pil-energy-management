import numpy as np
import pytest
from evpil.plant.auxiliary import AuxParams, aux_power_w, fit_auxiliary

A = AuxParams(p_base_w=300.0, k_heat_w_per_c=180.0, k_cool_w_per_c=90.0,
              t_setpoint_c=21.0)


def test_only_base_load_at_the_setpoint():
    assert aux_power_w(A, 21.0) == pytest.approx(300.0)


def test_heating_load_below_the_setpoint():
    # 21 degC below setpoint at 180 W/degC, plus 300 W base.
    assert aux_power_w(A, 0.0) == pytest.approx(300.0 + 21.0 * 180.0)


def test_cooling_load_above_the_setpoint():
    # 14 degC above setpoint at 90 W/degC, plus 300 W base.
    assert aux_power_w(A, 35.0) == pytest.approx(300.0 + 14.0 * 90.0)


def test_heating_and_cooling_coefficients_are_independent():
    below = aux_power_w(A, 21.0 - 10.0) - A.p_base_w
    above = aux_power_w(A, 21.0 + 10.0) - A.p_base_w
    assert below == pytest.approx(1800.0)
    assert above == pytest.approx(900.0)
    assert below != above


def test_fit_recovers_known_coefficients():
    t = np.linspace(-10.0, 40.0, 500)
    p = np.array([aux_power_w(A, x) for x in t])

    got = fit_auxiliary(t, p, t_setpoint_c=21.0)
    assert got.p_base_w == pytest.approx(300.0, abs=1.0)
    assert got.k_heat_w_per_c == pytest.approx(180.0, abs=1.0)
    assert got.k_cool_w_per_c == pytest.approx(90.0, abs=1.0)


def test_fit_is_robust_to_moderate_noise():
    rng = np.random.default_rng(0)
    t = np.linspace(-10.0, 40.0, 2000)
    p = np.array([aux_power_w(A, x) for x in t]) + rng.normal(0, 50.0, 2000)

    got = fit_auxiliary(t, p, t_setpoint_c=21.0)
    assert got.k_heat_w_per_c == pytest.approx(180.0, rel=0.05)
    assert got.k_cool_w_per_c == pytest.approx(90.0, rel=0.05)


def test_fitted_power_is_never_negative():
    t = np.linspace(-10.0, 40.0, 100)
    p = np.zeros_like(t)
    got = fit_auxiliary(t, p, t_setpoint_c=21.0)
    assert aux_power_w(got, -20.0) >= 0.0
    assert aux_power_w(got, 50.0) >= 0.0
