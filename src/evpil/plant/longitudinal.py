"""Longitudinal vehicle dynamics.

All four resistance terms are present. Sign conventions: positive v is forward,
positive grade is uphill, and rolling and aerodynamic forces always oppose
motion.
"""

from __future__ import annotations

import math
from typing import NamedTuple


class RoadLoad(NamedTuple):
    rolling_n: float
    aero_n: float
    grade_n: float
    inertia_n: float
    tractive_n: float


def road_load(
    v_mps: float,
    a_mps2: float,
    grade_rad: float,
    *,
    mass_kg: float,
    c_rr: float,
    cd: float,
    frontal_area_m2: float,
    rho_kgm3: float = 1.2,
    g: float = 9.81,
) -> RoadLoad:
    """Return the four force components and their sum, in newtons.

    `tractive_n` is the force the powertrain must supply. It is negative when
    the vehicle is being decelerated or is descending, which is the condition
    under which regeneration is available.
    """
    direction = 0.0 if v_mps == 0.0 else math.copysign(1.0, v_mps)

    rolling = c_rr * mass_kg * g * math.cos(grade_rad) * direction
    aero = 0.5 * rho_kgm3 * cd * frontal_area_m2 * v_mps * v_mps * direction
    grade = mass_kg * g * math.sin(grade_rad)
    inertia = mass_kg * a_mps2

    return RoadLoad(
        rolling_n=rolling,
        aero_n=aero,
        grade_n=grade,
        inertia_n=inertia,
        tractive_n=rolling + aero + grade + inertia,
    )


def mechanical_power_w(load: RoadLoad, v_mps: float) -> float:
    """Mechanical power at the wheels, in watts. Negative means regeneration."""
    return load.tractive_n * v_mps
