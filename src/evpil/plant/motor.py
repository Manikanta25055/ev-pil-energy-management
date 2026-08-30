"""Motor and drivetrain: a 2-D efficiency map plus torque and power limits.

Efficiency is looked up on |torque| so that motoring and generating share one
map, which is the usual simplification when only a single map is published.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class MotorParams:
    torque_axis_nm: tuple[float, ...]
    speed_axis_radps: tuple[float, ...]
    efficiency_grid: np.ndarray      # shape (len(torque_axis), len(speed_axis))
    torque_max_nm: float
    speed_max_radps: float
    power_max_w: float


def efficiency(params: MotorParams, torque_nm: float, omega_radps: float) -> float:
    """Bilinear interpolation on the efficiency map, clamped at the grid edges."""
    t_axis = np.asarray(params.torque_axis_nm, dtype=float)
    w_axis = np.asarray(params.speed_axis_radps, dtype=float)

    t = float(np.clip(abs(torque_nm), t_axis[0], t_axis[-1]))
    w = float(np.clip(abs(omega_radps), w_axis[0], w_axis[-1]))

    i = int(np.clip(np.searchsorted(t_axis, t) - 1, 0, len(t_axis) - 2))
    j = int(np.clip(np.searchsorted(w_axis, w) - 1, 0, len(w_axis) - 2))

    t0, t1 = t_axis[i], t_axis[i + 1]
    w0, w1 = w_axis[j], w_axis[j + 1]
    ft = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
    fw = 0.0 if w1 == w0 else (w - w0) / (w1 - w0)

    g = params.efficiency_grid
    return float(
        g[i, j] * (1 - ft) * (1 - fw) + g[i + 1, j] * ft * (1 - fw)
        + g[i, j + 1] * (1 - ft) * fw + g[i + 1, j + 1] * ft * fw
    )


def electrical_power_w(params: MotorParams, torque_nm: float, omega_radps: float) -> float:
    """Electrical power at the inverter terminals. Negative means generating.

    Driving divides by efficiency (losses add to the draw); generating
    multiplies by it (losses subtract from the return).
    """
    p_mech = torque_nm * omega_radps
    if p_mech == 0.0:
        return 0.0

    eta = efficiency(params, torque_nm, omega_radps)
    return p_mech / eta if p_mech > 0.0 else p_mech * eta


def clamp_torque(params: MotorParams, torque_nm: float, omega_radps: float) -> float:
    """Clamp to the rated torque, the constant-power envelope, and the speed limit."""
    if abs(omega_radps) > params.speed_max_radps:
        return 0.0

    limit = params.torque_max_nm
    if abs(omega_radps) > 0.0:
        limit = min(limit, params.power_max_w / abs(omega_radps))

    return float(np.clip(torque_nm, -limit, limit))
