"""Regenerative braking: split braking demand between the machine and friction.

Whatever the machine cannot absorb goes to the friction brakes, so the braking
demand is always met in full. Only the recovered fraction changes.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from evpil.plant.battery import BatteryParams, BatteryState


@dataclass(frozen=True)
class RegenParams:
    power_limit_w: float
    blend_min: float = 0.0
    blend_max: float = 1.0


def split_braking(
    p_brake_w: float,
    blend: float,
    *,
    regen_params: RegenParams,
    batt_params: BatteryParams,
    batt_state: BatteryState,
    v_term_v: float,
) -> tuple[float, float]:
    """Return (p_regen_w, p_friction_w), both negative or zero, summing to demand.

    `p_brake_w` is the *electrical* braking power the machine can return,
    negative when braking. `blend` is the commanded regenerative fraction,
    clamped to its declared range; the realised fraction may be lower when a
    limit binds.
    """
    if p_brake_w >= 0.0:
        return 0.0, 0.0

    b = float(np.clip(blend, regen_params.blend_min, regen_params.blend_max))

    if batt_state.soc_frac >= batt_params.soc_max:
        return 0.0, p_brake_w

    ceiling = min(
        regen_params.power_limit_w,
        batt_params.i_charge_max_a * max(v_term_v, 0.0),
    )

    p_regen = max(b * p_brake_w, -ceiling)
    return p_regen, p_brake_w - p_regen
