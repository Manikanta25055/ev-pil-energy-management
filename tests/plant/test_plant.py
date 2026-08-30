import math
import numpy as np
import pytest
from evpil.plant.auxiliary import AuxParams
from evpil.plant.battery import BatteryParams
from evpil.plant.motor import MotorParams
from evpil.plant.params import VehicleParams
from evpil.plant.plant import Plant
from evpil.plant.regen import RegenParams

BATT = BatteryParams(
    capacity_ah=60.0, ocv_soc_points=(0.0, 0.5, 1.0), ocv_volts=(300.0, 350.0, 400.0),
    r0_ohm=0.05, r1_ohm=0.01, c1_farad=2000.0,
    i_discharge_max_a=400.0, i_charge_max_a=150.0, soc_min=0.05, soc_max=0.98,
)
MOTOR = MotorParams(
    torque_axis_nm=(0.0, 100.0, 200.0), speed_axis_radps=(0.0, 500.0, 1000.0),
    efficiency_grid=np.full((3, 3), 0.90),
    torque_max_nm=250.0, speed_max_radps=1200.0, power_max_w=125000.0,
)
AUX = AuxParams(p_base_w=300.0, k_heat_w_per_c=180.0, k_cool_w_per_c=90.0)

VP = VehicleParams(
    mass_kg=1400.0, c_rr=0.01, cd=0.29, frontal_area_m2=2.38,
    wheel_radius_m=0.32, gear_ratio=9.7, drivetrain_eta=0.95,
    battery=BATT, motor=MOTOR, regen=RegenParams(power_limit_w=50000.0), aux=AUX,
    citations={
        "mass_kg": "test fixture", "c_rr": "test fixture", "cd": "test fixture",
        "frontal_area_m2": "test fixture", "wheel_radius_m": "test fixture",
        "gear_ratio": "test fixture", "drivetrain_eta": "test fixture",
        "battery": "test fixture", "motor": "test fixture",
        "regen": "test fixture", "aux": "test fixture",
    },
)


def test_params_reject_a_missing_citation():
    with pytest.raises(ValueError, match="citation"):
        VehicleParams(
            mass_kg=1400.0, c_rr=0.01, cd=0.29, frontal_area_m2=2.38,
            wheel_radius_m=0.32, gear_ratio=9.7, drivetrain_eta=0.95,
            battery=BATT, motor=MOTOR, regen=RegenParams(power_limit_w=50000.0),
            aux=AUX, citations={"mass_kg": "only this one"},
        )


def test_reset_produces_the_requested_initial_condition():
    st = Plant(VP).reset(soc0=0.8, t_ambient_c=21.0, t_batt_c=25.0)
    assert st.v_mps == pytest.approx(0.0)
    assert st.battery.soc_frac == pytest.approx(0.8)
    assert st.distance_m == pytest.approx(0.0)


def test_zero_torque_from_rest_leaves_the_vehicle_at_rest():
    plant = Plant(VP)
    st = plant.reset(soc0=0.8, t_ambient_c=21.0, t_batt_c=25.0)
    out = plant.step(st, torque_nm=0.0, regen_blend=0.0, p_limit_w=1e6,
                     grade_rad=0.0, t_ambient_c=21.0, dt_s=0.1)
    assert out.state.v_mps == pytest.approx(0.0, abs=1e-9)
    assert out.p_mech_w == pytest.approx(0.0, abs=1e-9)


def test_positive_torque_accelerates_the_vehicle():
    plant = Plant(VP)
    st = plant.reset(soc0=0.8, t_ambient_c=21.0, t_batt_c=25.0)
    out = plant.step(st, torque_nm=100.0, regen_blend=0.0, p_limit_w=1e6,
                     grade_rad=0.0, t_ambient_c=21.0, dt_s=0.1)
    assert out.a_mps2 > 0.0
    assert out.state.v_mps > 0.0


def test_wheel_force_matches_the_gear_and_efficiency_chain():
    plant = Plant(VP)
    st = plant.reset(soc0=0.8, t_ambient_c=21.0, t_batt_c=25.0)
    out = plant.step(st, torque_nm=100.0, regen_blend=0.0, p_limit_w=1e6,
                     grade_rad=0.0, t_ambient_c=21.0, dt_s=0.1)
    # F = T * G * eta / r = 100 * 9.7 * 0.95 / 0.32; from rest the only
    # resistance is rolling (aero is zero at v = 0).
    f_wheel = 100.0 * 9.7 * 0.95 / 0.32
    f_roll = 0.0     # direction is 0 at exactly v = 0
    assert out.a_mps2 == pytest.approx((f_wheel - f_roll) / 1400.0, rel=1e-9)


def test_driving_discharges_and_regeneration_charges():
    plant = Plant(VP)
    st = plant.reset(soc0=0.8, t_ambient_c=21.0, t_batt_c=25.0)
    for _ in range(50):
        out = plant.step(st, torque_nm=80.0, regen_blend=0.0, p_limit_w=1e6,
                         grade_rad=0.0, t_ambient_c=21.0, dt_s=0.1)
        st = out.state
    assert st.battery.soc_frac < 0.8
    soc_after_drive = st.battery.soc_frac

    out = plant.step(st, torque_nm=-80.0, regen_blend=1.0, p_limit_w=1e6,
                     grade_rad=0.0, t_ambient_c=21.0, dt_s=0.1)
    assert out.p_regen_w < 0.0
    assert out.i_batt_a < 0.0
    assert out.state.battery.soc_frac > soc_after_drive


def test_auxiliary_load_flows_into_battery_power():
    plant = Plant(VP)
    st = plant.reset(soc0=0.8, t_ambient_c=21.0, t_batt_c=25.0)

    warm = plant.step(st, torque_nm=0.0, regen_blend=0.0, p_limit_w=1e6,
                      grade_rad=0.0, t_ambient_c=21.0, dt_s=0.1)
    cold = plant.step(st, torque_nm=0.0, regen_blend=0.0, p_limit_w=1e6,
                      grade_rad=0.0, t_ambient_c=-5.0, dt_s=0.1)

    assert cold.p_aux_w > warm.p_aux_w
    assert cold.p_batt_w > warm.p_batt_w


def test_discharge_power_limit_is_enforced():
    plant = Plant(VP)
    st = plant.reset(soc0=0.8, t_ambient_c=21.0, t_batt_c=25.0)
    for _ in range(100):
        st = plant.step(st, torque_nm=200.0, regen_blend=0.0, p_limit_w=1e6,
                        grade_rad=0.0, t_ambient_c=21.0, dt_s=0.1).state

    out = plant.step(st, torque_nm=200.0, regen_blend=0.0, p_limit_w=20000.0,
                     grade_rad=0.0, t_ambient_c=21.0, dt_s=0.1)
    # The limit must be met exactly, not merely not exceeded. Solving the
    # battery coupling with a stale voltage used to overshoot this by ~4.6%,
    # which would silently invalidate every energy-management result in Phase 3.
    assert out.p_batt_w == pytest.approx(20000.0, rel=1e-9)
    assert out.v_batt_v * out.i_batt_a == pytest.approx(out.p_batt_w, rel=1e-9)


def test_climbing_needs_more_energy_than_the_flat():
    plant = Plant(VP)
    base = plant.reset(soc0=0.8, t_ambient_c=21.0, t_batt_c=25.0)

    flat, hill = base, base
    for _ in range(100):
        flat = plant.step(flat, torque_nm=120.0, regen_blend=0.0, p_limit_w=1e6,
                          grade_rad=0.0, t_ambient_c=21.0, dt_s=0.1).state
        hill = plant.step(hill, torque_nm=120.0, regen_blend=0.0, p_limit_w=1e6,
                          grade_rad=math.radians(6.0), t_ambient_c=21.0,
                          dt_s=0.1).state

    assert hill.v_mps < flat.v_mps
    assert hill.distance_m < flat.distance_m


def test_distance_and_energy_accumulate_monotonically():
    plant = Plant(VP)
    st = plant.reset(soc0=0.8, t_ambient_c=21.0, t_batt_c=25.0)
    prev_d, prev_e = -1.0, -1.0
    for _ in range(30):
        st = plant.step(st, torque_nm=100.0, regen_blend=0.0, p_limit_w=1e6,
                        grade_rad=0.0, t_ambient_c=21.0, dt_s=0.1).state
        assert st.distance_m > prev_d
        assert st.energy_wh > prev_e
        prev_d, prev_e = st.distance_m, st.energy_wh
