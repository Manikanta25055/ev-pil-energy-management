"""Identify the motor efficiency map from logged trips.

The plant shipped with a representative PMSM surface because BMW publishes no
map for the I01. That assumption was measurably wrong: it is 7.4% pessimistic
overall and wrongest at low torque, which is where most driving happens.

The archive logs motor torque, and battery power and auxiliary power are
known, so the efficiency at each operating point is not an assumption at all --
it is a measurement waiting to be taken. This module takes it.

Efficiency here is motor-plus-inverter: shaft power over electrical power at
the inverter terminals, the same quantity `evpil.plant.motor.efficiency`
returns.
"""

from __future__ import annotations

import numpy as np

# Nothing outside this band is a credible traction-drive efficiency; a cell
# that lands outside it is telling us about the data, not the machine.
ETA_MIN, ETA_MAX = 0.60, 0.97

# Below these magnitudes the ratio of two nearly equal small numbers is noise.
MIN_MECH_W = 2000.0
MIN_SAMPLES_PER_CELL = 300


def _cell_edges(axis: np.ndarray) -> np.ndarray:
    """Bin edges midway between grid nodes, open at both ends."""
    mid = (axis[:-1] + axis[1:]) / 2.0
    return np.concatenate([[-np.inf], mid, [np.inf]])


def identify_efficiency_grid(
    torque_nm: np.ndarray,
    omega_radps: np.ndarray,
    p_elec_w: np.ndarray,
    torque_axis: tuple[float, ...],
    speed_axis: tuple[float, ...],
) -> tuple[np.ndarray, np.ndarray]:
    """Return (efficiency grid, samples per cell) on the given axes.

    `p_elec_w` is electrical power at the inverter: battery power less the
    auxiliary load. Only motoring points are used. Regeneration is excluded
    because the measured generating ratio exceeds 1 at the median, which is
    impossible and means the logged torque does not account for all the shaft
    power in that direction; fitting to it would bake that error into the map.
    """
    t_ax = np.asarray(torque_axis, dtype=float)
    w_ax = np.asarray(speed_axis, dtype=float)

    tq = np.asarray(torque_nm, dtype=float)
    om = np.asarray(omega_radps, dtype=float)
    pe = np.asarray(p_elec_w, dtype=float)
    pm = tq * om

    ok = np.isfinite(pm) & np.isfinite(pe) & (pm > MIN_MECH_W) & (pe > 0.0)
    tq, om, eta = np.abs(tq[ok]), np.abs(om[ok]), pm[ok] / pe[ok]
    eta = eta[(eta > 0.0) & (eta < 1.5)]
    tq, om = tq[: len(eta)], om[: len(eta)]

    ti = np.digitize(tq, _cell_edges(t_ax)[1:-1])
    wi = np.digitize(om, _cell_edges(w_ax)[1:-1])

    grid = np.full((len(t_ax), len(w_ax)), np.nan)
    counts = np.zeros_like(grid, dtype=int)
    for i in range(len(t_ax)):
        for j in range(len(w_ax)):
            m = (ti == i) & (wi == j)
            counts[i, j] = int(m.sum())
            if counts[i, j] >= MIN_SAMPLES_PER_CELL:
                grid[i, j] = float(np.median(eta[m]))

    grid = np.clip(grid, ETA_MIN, ETA_MAX)
    return _fill_unvisited(grid, t_ax, w_ax), counts


def _fill_unvisited(grid: np.ndarray, t_ax: np.ndarray, w_ax: np.ndarray) -> np.ndarray:
    """Fill cells the vehicle never visited from the nearest cell it did.

    High torque at high speed is empty because the car was never driven that
    way, not because efficiency is undefined there. Nearest-neighbour on the
    normalised axes keeps the surface smooth without inventing a trend.
    """
    out = grid.copy()
    known = np.argwhere(np.isfinite(grid))
    if len(known) == 0:
        raise ValueError("no cell had enough samples to identify")

    tn = t_ax / max(t_ax[-1], 1e-9)
    wn = w_ax / max(w_ax[-1], 1e-9)
    for i, j in np.argwhere(~np.isfinite(grid)):
        d = [(tn[i] - tn[a]) ** 2 + (wn[j] - wn[b]) ** 2 for a, b in known]
        a, b = known[int(np.argmin(d))]
        out[i, j] = grid[a, b]
    return out
