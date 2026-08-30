"""The EV plant: composes road load, motor, regeneration, auxiliary and battery.

The battery coupling I = P/V(I) is solved in closed form (see
battery.current_for_power) rather than by dividing by the previous step's
voltage. The lagged form let a commanded power limit be exceeded by several
percent, which matters because in Phase 3 that limit is an RL action.
"""

from __future__ import annotations

from dataclasses import dataclass

from evpil.plant.auxiliary import aux_power_w
from evpil.plant.battery import (
    BatteryState, battery_step, clamp_current, current_for_power, emf_v,
    terminal_voltage_v,
)
from evpil.plant.longitudinal import road_load
from evpil.plant.motor import clamp_torque, electrical_power_w
from evpil.plant.params import VehicleParams
from evpil.plant.regen import split_braking


@dataclass(frozen=True)
class PlantState:
    v_mps: float
    battery: BatteryState
    distance_m: float
    energy_wh: float


@dataclass(frozen=True)
class PlantOutput:
    state: PlantState
    a_mps2: float
    i_batt_a: float
    v_batt_v: float
    p_batt_w: float
    p_mech_w: float
    p_regen_w: float
    p_friction_w: float
    p_aux_w: float


class Plant:
    def __init__(self, params: VehicleParams) -> None:
        self.p = params

    def reset(self, soc0: float, t_ambient_c: float, t_batt_c: float) -> PlantState:
        batt = BatteryState(soc_frac=soc0, v_rc_v=0.0, t_batt_c=t_batt_c)
        return PlantState(
            v_mps=0.0,
            battery=batt,
            distance_m=0.0,
            energy_wh=0.0,
        )

    def step(
        self,
        state: PlantState,
        *,
        torque_nm: float,
        regen_blend: float,
        p_limit_w: float,
        grade_rad: float,
        t_ambient_c: float,
        dt_s: float,
        p_aux_w: float | None = None,
    ) -> PlantOutput:
        """Advance one step.

        `p_aux_w` overrides the auxiliary model with a measured load. The HVAC
        draw is an exogenous disturbance set by weather, cabin state and what
        the driver asked for, not a function of the powertrain, so when it has
        been measured it is an input like speed or grade. Leaving it None falls
        back to predicting it from ambient temperature, which is what a
        deployed controller without a measurement has to do.
        """
        p = self.p

        omega = (state.v_mps / p.wheel_radius_m) * p.gear_ratio
        torque = clamp_torque(p.motor, torque_nm, omega)

        # Drivetrain losses always reduce power in its direction of flow.
        if torque >= 0.0:
            f_wheel = torque * p.gear_ratio * p.drivetrain_eta / p.wheel_radius_m
        else:
            f_wheel = torque * p.gear_ratio / (p.drivetrain_eta * p.wheel_radius_m)

        load = road_load(
            v_mps=state.v_mps, a_mps2=0.0, grade_rad=grade_rad,
            mass_kg=p.mass_kg, c_rr=p.c_rr, cd=p.cd,
            frontal_area_m2=p.frontal_area_m2,
            rot_mass_factor=p.rot_mass_factor,
        )
        f_resist = load.rolling_n + load.aero_n + load.grade_n
        a_mps2 = (f_wheel - f_resist) / (p.mass_kg * (1.0 + p.rot_mass_factor))

        p_mech_w = torque * omega
        p_elec_w = electrical_power_w(p.motor, torque, omega)

        if p_elec_w < 0.0:
            p_regen_w, p_friction_w = split_braking(
                p_elec_w, regen_blend,
                regen_params=p.regen, batt_params=p.battery,
                batt_state=state.battery, v_term_v=emf_v(p.battery, state.battery),
            )
            p_machine_w = p_regen_w
        else:
            p_regen_w, p_friction_w = 0.0, 0.0
            p_machine_w = p_elec_w

        p_aux = aux_power_w(p.aux, t_ambient_c) if p_aux_w is None else p_aux_w
        p_batt_w = min(p_machine_w + p_aux, p_limit_w)

        # Exact solve, so p_limit_w is genuinely binding. Clamping afterwards
        # only ever reduces |i| on the lower root, so it cannot push power back
        # above the limit.
        i_raw = current_for_power(p.battery, state.battery, p_batt_w)
        i_batt = clamp_current(p.battery, state.battery, i_raw)

        v_term = terminal_voltage_v(p.battery, state.battery, i_batt)
        p_batt_actual = v_term * i_batt

        batt_next = battery_step(p.battery, state.battery, i_batt, dt_s)

        v_next = state.v_mps + a_mps2 * dt_s
        dist_next = state.distance_m + abs(state.v_mps) * dt_s
        energy_next = state.energy_wh + max(0.0, p_batt_actual) * dt_s / 3600.0

        next_state = PlantState(
            v_mps=v_next,
            battery=batt_next,
            distance_m=dist_next,
            energy_wh=energy_next,
        )

        return PlantOutput(
            state=next_state, a_mps2=a_mps2, i_batt_a=i_batt, v_batt_v=v_term,
            p_batt_w=p_batt_actual, p_mech_w=p_mech_w, p_regen_w=p_regen_w,
            p_friction_w=p_friction_w, p_aux_w=p_aux,
        )
