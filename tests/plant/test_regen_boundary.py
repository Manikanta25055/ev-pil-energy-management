"""Regeneration boundary at the plant level, against an oracle written here.

The unit tests in test_regen.py check `split_braking` on its own. This file
checks what one `Plant.step` does with braking: the declared split between
machine and friction, the charge-current and full-pack limits, and the
terminal-port accounting. The oracle below does not call the production
helpers it checks (`split_braking`, `current_for_power`, `clamp_current`,
`battery_step`); it uses the fixture's constant 0.90 motor efficiency, its
linear OCV table and the quadratic of a series resistance.

Valid domain, fixed before the run: positive open-circuit voltage, positive
R0 (0.05 ohm at the 25 C reference), RC branch at rest, nonnegative auxiliary
load supplied as a measured input, flat road, motor inside its torque and
power envelope. Single-step algebra is compared at rel 1e-9; the timestep
refinement at rel 1e-3.
"""

import dataclasses
import math

import numpy as np
import pytest

from evpil.plant.auxiliary import AuxParams
from evpil.plant.battery import BatteryParams, BatteryState
from evpil.plant.motor import MotorParams
from evpil.plant.params import VehicleParams
from evpil.plant.plant import Plant, PlantState
from evpil.plant.regen import RegenParams

# The fixture of test_plant.py, copied so this file stands alone.
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
    rot_mass_factor=0.0,
    battery=BATT, motor=MOTOR, regen=RegenParams(power_limit_w=50000.0), aux=AUX,
    citations={
        "mass_kg": "test fixture", "c_rr": "test fixture", "cd": "test fixture",
        "frontal_area_m2": "test fixture", "wheel_radius_m": "test fixture",
        "gear_ratio": "test fixture", "drivetrain_eta": "test fixture",
        "rot_mass_factor": "test fixture",
        "battery": "test fixture", "motor": "test fixture",
        "regen": "test fixture", "aux": "test fixture",
    },
)

ETA = 0.90
AUX_W = 300.0
V_MPS = 20.0
R0 = 0.05


def _state(soc):
    return PlantState(v_mps=V_MPS, battery=BatteryState(soc_frac=soc, v_rc_v=0.0, t_batt_c=25.0),
                      distance_m=0.0, energy_wh=0.0)


def _ocv(soc):
    # Linear table 300 V at 0, 350 V at 0.5, 400 V at 1.0.
    return 300.0 + 100.0 * soc


def _oracle(torque_nm, blend, soc, i_charge_max_a=150.0, regen_limit_w=50000.0, soc_max=0.98):
    omega = V_MPS / VP.wheel_radius_m * VP.gear_ratio
    p_elec = torque_nm * omega * ETA                # braking: losses reduce the return
    e = _ocv(soc)
    if soc >= soc_max:
        p_regen = 0.0
    else:
        ceiling = min(regen_limit_w, i_charge_max_a * e)
        p_regen = max(blend * p_elec, -ceiling)
    p_term = p_regen + AUX_W
    i = (e - math.sqrt(e * e - 4.0 * R0 * p_term)) / (2.0 * R0)
    return {"p_elec": p_elec, "p_regen": p_regen, "p_friction": p_elec - p_regen,
            "p_term": p_term, "i": i, "v": e - R0 * i}


def _step(plant, soc, torque_nm=-80.0, blend=1.0, dt=0.1):
    return plant.step(_state(soc), torque_nm=torque_nm, regen_blend=blend, p_limit_w=1e6,
                      grade_rad=0.0, t_ambient_c=21.0, dt_s=dt, p_aux_w=AUX_W)


@pytest.mark.parametrize("blend", [0.0, 0.4, 1.0])
def test_braking_split_and_terminal_port_match_the_oracle(blend):
    out = _step(Plant(VP), 0.5, blend=blend)
    o = _oracle(-80.0, blend, 0.5)
    assert out.p_regen_w == pytest.approx(o["p_regen"], rel=1e-9, abs=1e-9)
    assert out.p_regen_w + out.p_friction_w == pytest.approx(o["p_elec"], rel=1e-9)
    # Terminal port: what the pack receives is the machine's regenerated
    # electrical power net of the auxiliary load it also serves.
    assert out.p_batt_w == pytest.approx(o["p_term"], rel=1e-9, abs=1e-9)
    assert out.i_batt_a == pytest.approx(o["i"], rel=1e-9, abs=1e-9)
    assert out.v_batt_v * out.i_batt_a == pytest.approx(out.p_batt_w, rel=1e-9, abs=1e-9)


def test_charge_current_limit_caps_regeneration():
    weak = dataclasses.replace(VP.battery, i_charge_max_a=50.0)
    out = _step(Plant(dataclasses.replace(VP, battery=weak)), 0.5)
    o = _oracle(-80.0, 1.0, 0.5, i_charge_max_a=50.0)
    assert o["p_regen"] == pytest.approx(-50.0 * 350.0)
    assert out.p_regen_w == pytest.approx(o["p_regen"], rel=1e-9)
    assert out.p_friction_w == pytest.approx(o["p_friction"], rel=1e-9)
    assert -out.i_batt_a <= 50.0
    assert out.i_batt_a == pytest.approx(o["i"], rel=1e-9)


def test_a_full_pack_takes_no_charge_and_still_serves_the_auxiliary_load():
    out = _step(Plant(VP), 0.98)
    o = _oracle(-80.0, 1.0, 0.98)
    assert out.p_regen_w == 0.0
    assert out.p_friction_w == pytest.approx(o["p_elec"], rel=1e-9)
    assert out.i_batt_a >= 0.0
    assert out.p_batt_w == pytest.approx(AUX_W, rel=1e-9)


def test_soc_rises_by_the_coulombs_charged_and_gross_draw_does_not_move():
    dt = 0.1
    out = _step(Plant(VP), 0.5, dt=dt)
    o = _oracle(-80.0, 1.0, 0.5)
    cap_as = VP.battery.capacity_ah * 3600.0
    assert out.state.battery.soc_frac == pytest.approx(0.5 - o["i"] * dt / cap_as, rel=1e-9)
    # PlantState.energy_wh is gross draw by design: a charging step adds nothing.
    assert out.state.energy_wh == 0.0


def test_net_terminal_energy_converges_under_timestep_refinement():
    plant = Plant(VP)

    def net_wh(dt, t_end=2.0):
        st, total = _state(0.5), 0.0
        for _ in range(int(round(t_end / dt))):
            out = plant.step(st, torque_nm=-80.0, regen_blend=1.0, p_limit_w=1e6,
                             grade_rad=0.0, t_ambient_c=21.0, dt_s=dt, p_aux_w=AUX_W)
            total += out.p_batt_w * dt / 3600.0
            st = out.state
        return total

    coarse, fine = net_wh(0.01), net_wh(0.005)
    assert coarse < 0.0
    assert coarse == pytest.approx(fine, rel=1e-3)
