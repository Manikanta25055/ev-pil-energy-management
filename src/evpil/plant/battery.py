"""First-order Thevenin battery model with a temperature-dependent series
resistance.

Current sign convention: positive is discharge, matching the BMW i3 archive.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

# Floor on r0 so extreme temperatures cannot drive it to zero or negative,
# which would make the terminal-voltage equation nonsensical.
_R0_FLOOR_FRACTION = 0.1


@dataclass(frozen=True)
class BatteryParams:
    capacity_ah: float
    ocv_soc_points: tuple[float, ...]
    ocv_volts: tuple[float, ...]
    r0_ohm: float
    r1_ohm: float
    c1_farad: float
    i_discharge_max_a: float
    i_charge_max_a: float
    soc_min: float
    soc_max: float
    r0_temp_coeff_per_c: float = 0.0
    t_ref_c: float = 25.0


@dataclass(frozen=True)
class BatteryState:
    soc_frac: float
    v_rc_v: float
    t_batt_c: float


def ocv_v(params: BatteryParams, soc_frac: float) -> float:
    """Open-circuit voltage, linearly interpolated and clamped at the table ends."""
    return float(np.interp(soc_frac, params.ocv_soc_points, params.ocv_volts))


def r0_at(params: BatteryParams, t_batt_c: float) -> float:
    """Series resistance at a given cell temperature.

    A negative temperature coefficient means resistance rises as the cell
    cools, which is the physically correct direction for lithium-ion.
    """
    scale = 1.0 + params.r0_temp_coeff_per_c * (t_batt_c - params.t_ref_c)
    floor = params.r0_ohm * _R0_FLOOR_FRACTION
    return max(params.r0_ohm * scale, floor)


def terminal_voltage_v(params: BatteryParams, state: BatteryState, i_a: float) -> float:
    """Terminal voltage for a given current, using the current RC-branch state."""
    return ocv_v(params, state.soc_frac) - i_a * r0_at(params, state.t_batt_c) - state.v_rc_v


def emf_v(params: BatteryParams, state: BatteryState) -> float:
    """Terminal voltage at zero current: OCV less the RC-branch drop."""
    return ocv_v(params, state.soc_frac) - state.v_rc_v


def max_power_w(params: BatteryParams, state: BatteryState) -> float:
    """Peak deliverable power, at the matched-load point i = E / (2 * r0)."""
    e = emf_v(params, state)
    return e * e / (4.0 * r0_at(params, state.t_batt_c))


def current_for_power(
    params: BatteryParams, state: BatteryState, p_target_w: float
) -> float:
    """Exact current that delivers `p_target_w` at the terminals.

    Solves (E - i*r0) * i = P for i, i.e. r0*i^2 - E*i + P = 0, and takes the
    lower root, which is the physically realised branch (the upper root is past
    the matched-load point, where more current yields less power).

    Solving this in closed form rather than dividing by a previous step's
    voltage is what makes a commanded power limit actually binding. Using a
    stale voltage lets the realised power overshoot the limit by several
    percent, which would silently corrupt any energy-management result.
    """
    e = emf_v(params, state)
    r0 = r0_at(params, state.t_batt_c)

    disc = e * e - 4.0 * r0 * p_target_w
    if disc <= 0.0:
        return e / (2.0 * r0)          # demand exceeds peak power; clamp to it
    return (e - math.sqrt(disc)) / (2.0 * r0)


def clamp_current(params: BatteryParams, state: BatteryState, i_a: float) -> float:
    """Clamp to the rated limits and block current that would breach an SoC bound."""
    i = float(np.clip(i_a, -params.i_charge_max_a, params.i_discharge_max_a))
    if i > 0.0 and state.soc_frac <= params.soc_min:
        return 0.0
    if i < 0.0 and state.soc_frac >= params.soc_max:
        return 0.0
    return i


def battery_step(
    params: BatteryParams, state: BatteryState, i_a: float, dt_s: float
) -> BatteryState:
    """Advance SoC by Coulomb counting and the RC branch by one forward-Euler step.

    Terminal voltage is evaluated by the caller *before* this call, so the RC
    voltage used for the output is the one at the start of the interval.
    """
    d_soc = i_a * dt_s / (3600.0 * params.capacity_ah)
    soc = float(np.clip(state.soc_frac - d_soc, params.soc_min, params.soc_max))

    tau = params.r1_ohm * params.c1_farad
    dv_rc = dt_s * (i_a / params.c1_farad - state.v_rc_v / tau)

    return BatteryState(soc_frac=soc, v_rc_v=state.v_rc_v + dv_rc, t_batt_c=state.t_batt_c)
