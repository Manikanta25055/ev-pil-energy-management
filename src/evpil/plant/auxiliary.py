"""Auxiliary and HVAC electrical load as a function of ambient temperature.

Piecewise-linear about a cabin setpoint, with separate heating and cooling
coefficients because the two use different mechanisms and are not symmetric.
Coefficients are fitted from the i3 archive's heating-circuit channel rather
than assumed.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class AuxParams:
    p_base_w: float
    k_heat_w_per_c: float
    k_cool_w_per_c: float
    t_setpoint_c: float = 21.0


def aux_power_w(params: AuxParams, t_ambient_c: float) -> float:
    """Auxiliary electrical power in watts. Never negative."""
    heat_deficit = max(0.0, params.t_setpoint_c - t_ambient_c)
    cool_excess = max(0.0, t_ambient_c - params.t_setpoint_c)

    p = (params.p_base_w
         + params.k_heat_w_per_c * heat_deficit
         + params.k_cool_w_per_c * cool_excess)
    return max(0.0, p)


def fit_auxiliary(
    t_ambient_c: np.ndarray,
    p_aux_w: np.ndarray,
    t_setpoint_c: float = 21.0,
) -> AuxParams:
    """Least-squares fit of the three coefficients from logged data.

    The design matrix has one column per coefficient, so this is an ordinary
    linear least-squares problem despite the piecewise form.
    """
    t = np.asarray(t_ambient_c, dtype=float).ravel()
    p = np.asarray(p_aux_w, dtype=float).ravel()
    if t.shape != p.shape:
        raise ValueError(f"shape mismatch: {t.shape} vs {p.shape}")

    heat = np.maximum(0.0, t_setpoint_c - t)
    cool = np.maximum(0.0, t - t_setpoint_c)
    design = np.column_stack([np.ones_like(t), heat, cool])

    coeffs, *_ = np.linalg.lstsq(design, p, rcond=None)
    base, k_heat, k_cool = (float(c) for c in coeffs)

    # Negative coefficients are unphysical: more heating demand cannot reduce
    # electrical load. Clamp rather than propagate a nonsense fit.
    return AuxParams(
        p_base_w=max(0.0, base),
        k_heat_w_per_c=max(0.0, k_heat),
        k_cool_w_per_c=max(0.0, k_cool),
        t_setpoint_c=t_setpoint_c,
    )
