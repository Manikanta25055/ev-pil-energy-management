import numpy as np
import pytest
from evpil.plant.motor import MotorParams, clamp_torque, efficiency, electrical_power_w

M = MotorParams(
    torque_axis_nm=(0.0, 100.0, 200.0),
    speed_axis_radps=(0.0, 500.0, 1000.0),
    efficiency_grid=np.array([
        [0.70, 0.80, 0.75],   # torque 0
        [0.80, 0.94, 0.90],   # torque 100
        [0.75, 0.90, 0.85],   # torque 200
    ]),
    torque_max_nm=250.0,
    speed_max_radps=1200.0,
    power_max_w=125000.0,
)


def test_efficiency_at_grid_points():
    assert efficiency(M, 100.0, 500.0) == pytest.approx(0.94)
    assert efficiency(M, 0.0, 0.0) == pytest.approx(0.70)
    assert efficiency(M, 200.0, 1000.0) == pytest.approx(0.85)


def test_efficiency_interpolates_bilinearly():
    # Midpoint of the (0,100)x(0,500) cell: mean of 0.70, 0.80, 0.80, 0.94
    assert efficiency(M, 50.0, 250.0) == pytest.approx(0.81)


def test_efficiency_uses_torque_magnitude_so_regen_shares_the_map():
    assert efficiency(M, -100.0, 500.0) == pytest.approx(efficiency(M, 100.0, 500.0))


def test_efficiency_clamps_beyond_the_grid():
    assert efficiency(M, 400.0, 2000.0) == pytest.approx(0.85)


def test_driving_draws_more_electrical_than_mechanical_power():
    # 100 Nm at 500 rad/s is 50 kW mechanical, at 0.94 efficiency.
    p = electrical_power_w(M, 100.0, 500.0)
    assert p == pytest.approx(50000.0 / 0.94, rel=1e-9)
    assert p > 50000.0


def test_regeneration_returns_less_electrical_than_mechanical_power():
    p = electrical_power_w(M, -100.0, 500.0)
    assert p == pytest.approx(-50000.0 * 0.94, rel=1e-9)
    assert -50000.0 < p < 0.0


def test_zero_speed_gives_zero_power():
    assert electrical_power_w(M, 150.0, 0.0) == pytest.approx(0.0)


def test_torque_clamped_to_the_rated_maximum():
    assert clamp_torque(M, 400.0, 100.0) == pytest.approx(250.0)
    assert clamp_torque(M, -400.0, 100.0) == pytest.approx(-250.0)


def test_torque_clamped_by_the_power_limit_at_high_speed():
    # At 1000 rad/s, 125 kW allows only 125 Nm.
    assert clamp_torque(M, 250.0, 1000.0) == pytest.approx(125.0, rel=1e-9)


def test_no_torque_above_the_speed_limit():
    assert clamp_torque(M, 200.0, 1500.0) == pytest.approx(0.0)
