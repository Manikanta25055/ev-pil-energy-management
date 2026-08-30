"""Leaf parameters: the coastdown conversion is where a silent error would hide."""

import numpy as np
import pytest

from evpil.plant.auxiliary import AuxParams
from evpil.plant.leaf import (
    CAPACITY_AH, COASTDOWN_A_N, COASTDOWN_C_N, FRONTAL_AREA_M2, GEAR_RATIO,
    MASS_KG, MEASURED_C_RR, MEASURED_CD, MEASURED_R0_OHM, OCV_SOC_POINTS,
    OCV_VOLTS, SPEED_MAX_RADPS, WHEEL_RADIUS_M, build_leaf,
)

AUX = AuxParams(p_base_w=358.0, k_heat_w_per_c=76.4, k_cool_w_per_c=125.9)
GRID = np.full((4, 4), 0.9)


def _leaf(**kw):
    base = dict(c_rr=MEASURED_C_RR, cd=MEASURED_CD, r0_ohm=MEASURED_R0_OHM,
                rot_mass_factor=0.17, aux=AUX, efficiency_grid=GRID)
    base.update(kw)
    return build_leaf(**base)


def test_coastdown_constant_term_converts_to_newtons():
    """31.911 lbf is 141.9 N; a wrong factor here rescales every road load."""
    assert COASTDOWN_A_N == pytest.approx(141.95, rel=1e-3)


def test_coastdown_quadratic_term_recovers_the_published_drag_coefficient():
    """The strongest check available: 2C/rho over the frontal area must land on
    Nissan's published Cd of about 0.29, a number it was not fitted to."""
    cda = 2.0 * COASTDOWN_C_N / 1.2
    assert cda == pytest.approx(0.659, rel=1e-2)
    assert cda / FRONTAL_AREA_M2 == pytest.approx(0.29, abs=0.01)
    assert MEASURED_CD == pytest.approx(0.29, abs=0.01)


def test_measured_rolling_resistance_is_physical():
    """A passenger car on normal tyres sits near 0.008 to 0.012."""
    assert 0.006 < MEASURED_C_RR < 0.013


def test_the_i3_fitted_rolling_resistance_is_not_the_leafs_measured_one():
    """The premise of the transfer arm: these differ by more than a little."""
    assert 0.019 / MEASURED_C_RR > 2.0


def test_wheel_radius_matches_the_fitted_tyre():
    # 205/55 R16: rim 16 in plus twice the 55% aspect of a 205 mm section.
    assert WHEEL_RADIUS_M == pytest.approx(0.3160, abs=5e-4)


def test_mass_is_curb_plus_one_driver():
    assert MASS_KG == pytest.approx(3302 * 0.45359237 + 75.0)
    assert 1500 < MASS_KG < 1650


def test_speed_envelope_covers_the_logged_maximum():
    """VED reaches 36.7 m/s; the motor model must not switch off below that."""
    assert 36.7 / WHEEL_RADIUS_M * GEAR_RATIO < SPEED_MAX_RADPS


def test_ocv_curve_is_monotonic_and_spans_the_pack_voltage():
    assert list(OCV_VOLTS) == sorted(OCV_VOLTS)
    assert len(OCV_VOLTS) == len(OCV_SOC_POINTS)
    assert 350.0 < OCV_VOLTS[0] < 360.0
    assert 385.0 < OCV_VOLTS[-1] < 395.0


def test_measured_capacity_is_well_below_nameplate():
    """66.2 Ah rated; VED's five-year-old packs Coulomb-count to 42."""
    assert CAPACITY_AH == pytest.approx(42.0)
    assert CAPACITY_AH / 66.2 < 0.7


def test_measured_r0_is_a_plausible_pack_resistance():
    """0.079 ohm over 96 series groups is 0.8 milliohm each."""
    assert 0.03 < MEASURED_R0_OHM < 0.15


def test_every_parameter_carries_a_citation():
    _leaf()          # VehicleParams raises when a citation is missing


def test_the_arm_under_test_is_recorded_in_the_citations():
    transferred = _leaf(c_rr_source="TRANSFERRED from the i3 identification")
    measured = _leaf(c_rr_source="MEASURED: coastdown")
    assert "TRANSFERRED" in transferred.citations["c_rr"]
    assert "MEASURED" in measured.citations["c_rr"]


def test_battery_and_motor_limits_are_the_leafs_not_the_i3s():
    p = _leaf()
    assert p.motor.power_max_w == pytest.approx(80_000.0)
    assert p.motor.torque_max_nm == pytest.approx(253.0)
    assert p.battery.capacity_ah == pytest.approx(CAPACITY_AH)
