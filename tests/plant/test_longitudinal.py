import math
import pytest
from evpil.plant.longitudinal import mechanical_power_w, road_load

PARAMS = dict(mass_kg=1400.0, c_rr=0.01, cd=0.29, frontal_area_m2=2.38,
              rho_kgm3=1.2, g=9.81)


def test_all_four_terms_on_the_flat_at_constant_speed():
    load = road_load(v_mps=20.0, a_mps2=0.0, grade_rad=0.0, **PARAMS)
    assert load.rolling_n == pytest.approx(137.340000, rel=1e-9)
    assert load.aero_n == pytest.approx(165.648000, rel=1e-9)
    assert load.grade_n == pytest.approx(0.0, abs=1e-12)
    assert load.inertia_n == pytest.approx(0.0, abs=1e-12)
    assert load.tractive_n == pytest.approx(302.988000, rel=1e-9)


def test_power_on_the_flat_at_constant_speed():
    load = road_load(v_mps=20.0, a_mps2=0.0, grade_rad=0.0, **PARAMS)
    assert mechanical_power_w(load, 20.0) == pytest.approx(6059.760000, rel=1e-9)


def test_climbing_while_accelerating():
    load = road_load(v_mps=10.0, a_mps2=1.0, grade_rad=math.radians(5.0), **PARAMS)
    assert load.rolling_n == pytest.approx(136.817380, rel=1e-6)
    assert load.aero_n == pytest.approx(41.412000, rel=1e-9)
    assert load.grade_n == pytest.approx(1196.996971, rel=1e-6)
    assert load.inertia_n == pytest.approx(1400.0, rel=1e-12)
    assert load.tractive_n == pytest.approx(2775.226351, rel=1e-6)
    assert mechanical_power_w(load, 10.0) == pytest.approx(27752.263507, rel=1e-6)


def test_aero_force_scales_with_the_square_of_speed():
    a = road_load(v_mps=10.0, a_mps2=0.0, grade_rad=0.0, **PARAMS).aero_n
    b = road_load(v_mps=20.0, a_mps2=0.0, grade_rad=0.0, **PARAMS).aero_n
    assert b == pytest.approx(4.0 * a, rel=1e-12)


def test_descending_gives_negative_grade_force():
    load = road_load(v_mps=15.0, a_mps2=0.0, grade_rad=math.radians(-5.0), **PARAMS)
    assert load.grade_n < 0
    assert load.grade_n == pytest.approx(-1196.996971, rel=1e-6)


def test_rolling_resistance_opposes_motion_when_reversing():
    fwd = road_load(v_mps=5.0, a_mps2=0.0, grade_rad=0.0, **PARAMS)
    rev = road_load(v_mps=-5.0, a_mps2=0.0, grade_rad=0.0, **PARAMS)
    assert fwd.rolling_n > 0
    assert rev.rolling_n < 0
    assert rev.rolling_n == pytest.approx(-fwd.rolling_n, rel=1e-12)


def test_rolling_and_aero_vanish_at_standstill():
    load = road_load(v_mps=0.0, a_mps2=0.0, grade_rad=0.0, **PARAMS)
    assert load.rolling_n == pytest.approx(0.0, abs=1e-12)
    assert load.aero_n == pytest.approx(0.0, abs=1e-12)


def test_aero_force_opposes_motion_when_reversing():
    rev = road_load(v_mps=-20.0, a_mps2=0.0, grade_rad=0.0, **PARAMS)
    assert rev.aero_n == pytest.approx(-165.648000, rel=1e-9)


def test_rotational_mass_raises_the_inertial_force():
    """Spinning up wheels, gear and rotor costs force the plain m*a term misses."""
    plain = road_load(v_mps=10.0, a_mps2=2.0, grade_rad=0.0, **PARAMS)
    spun = road_load(v_mps=10.0, a_mps2=2.0, grade_rad=0.0,
                     rot_mass_factor=0.10, **PARAMS)
    assert spun.inertia_n == pytest.approx(plain.inertia_n * 1.10, rel=1e-12)
    # Only the inertial term moves; the resistances are unchanged.
    assert spun.rolling_n == pytest.approx(plain.rolling_n)
    assert spun.aero_n == pytest.approx(plain.aero_n)
    assert spun.grade_n == pytest.approx(plain.grade_n)


def test_rotational_mass_is_inert_at_constant_speed():
    """It multiplies acceleration, so it must do nothing when there is none."""
    plain = road_load(v_mps=20.0, a_mps2=0.0, grade_rad=0.0, **PARAMS)
    spun = road_load(v_mps=20.0, a_mps2=0.0, grade_rad=0.0,
                     rot_mass_factor=0.25, **PARAMS)
    assert spun.tractive_n == pytest.approx(plain.tractive_n)


def test_rotational_mass_defaults_to_no_correction():
    assert (road_load(v_mps=10.0, a_mps2=1.0, grade_rad=0.0, **PARAMS).inertia_n
            == pytest.approx(road_load(v_mps=10.0, a_mps2=1.0, grade_rad=0.0,
                                       rot_mass_factor=0.0, **PARAMS).inertia_n))
