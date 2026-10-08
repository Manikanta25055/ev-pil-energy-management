"""The classical speed planner: dynamic programming along the route.

State: the speed at each node. Decision: the speed at the next. Between two
nodes the acceleration is constant, so the time and the energy of every
(speed, next speed) pair are known in closed form and are the same at every
node of a flat route: one table, computed once.

The arrival time is met with a price on time, `lam_w` (watts: what a second
is worth in joules per second). A higher price makes a faster drive; the
price that makes the drive arrive on time is found by bisection.

Three planners share the table and the recursion:

  full horizon     backward over the whole route: the classical planner
  short horizon    at each node, backward over the next `horizon` nodes only,
                   first step applied, then again from the next node
  with a terminal  the same, with a cost on the speed the short horizon ends
  cost             at: what the rest of the route would have cost from there

The energy in the table is the planner's own model of the car: road load,
the motor's efficiency map, the drivetrain, regeneration up to its power
limit, and the auxiliary load for the time the segment takes. It is used to
choose a profile. The number reported for an arm comes from driving the
profile through the plant with the speed loop and the energy manager in it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np

from evpil.plan.route import DV_MPS, Route, planned_time_s
from evpil.plant.auxiliary import aux_power_w
from evpil.plant.params import VehicleParams

RHO, G = 1.2, 9.81
T_AMBIENT_C = 12.0              # as evpil.control.sim.simulate defaults
INF = 1e18


@dataclass(frozen=True)
class Table:
    """Time and energy of going from each grid speed to each other over one
    node spacing, and whether the pair is drivable at all."""
    v: np.ndarray               # the speed grid
    dt_s: np.ndarray            # (nv, nv)
    energy_j: np.ndarray        # (nv, nv)
    accel: np.ndarray           # (nv, nv)
    ok: np.ndarray              # (nv, nv) the motor can deliver it


def _efficiency(p: VehicleParams, torque: np.ndarray,
                omega: np.ndarray) -> np.ndarray:
    """evpil.plant.motor.efficiency, for arrays."""
    m = p.motor
    t_axis = np.asarray(m.torque_axis_nm, dtype=float)
    w_axis = np.asarray(m.speed_axis_radps, dtype=float)
    t = np.clip(np.abs(torque), t_axis[0], t_axis[-1])
    w = np.clip(np.abs(omega), w_axis[0], w_axis[-1])
    i = np.clip(np.searchsorted(t_axis, t) - 1, 0, len(t_axis) - 2)
    j = np.clip(np.searchsorted(w_axis, w) - 1, 0, len(w_axis) - 2)
    ft = (t - t_axis[i]) / (t_axis[i + 1] - t_axis[i])
    fw = (w - w_axis[j]) / (w_axis[j + 1] - w_axis[j])
    g = np.asarray(m.efficiency_grid, dtype=float)
    return (g[i, j] * (1 - ft) * (1 - fw) + g[i + 1, j] * ft * (1 - fw)
            + g[i, j + 1] * (1 - ft) * fw + g[i + 1, j + 1] * ft * fw)


def build_table(p: VehicleParams, ds_m: float, v_max_mps: float) -> Table:
    v = np.arange(0.0, v_max_mps + DV_MPS / 2, DV_MPS)
    v0, v1 = np.meshgrid(v, v, indexing="ij")
    mean = 0.5 * (v0 + v1)
    moving = mean > 0.0
    dt = np.where(moving, ds_m / np.where(moving, mean, 1.0), INF)
    a = (v1 * v1 - v0 * v0) / (2.0 * ds_m)

    force = (p.c_rr * p.mass_kg * G
             + 0.5 * RHO * p.cd * p.frontal_area_m2 * mean * mean
             + p.mass_kg * (1.0 + p.rot_mass_factor) * a)
    omega = mean / p.wheel_radius_m * p.gear_ratio
    torque = np.where(
        force >= 0.0,
        force * p.wheel_radius_m / (p.gear_ratio * p.drivetrain_eta),
        force * p.wheel_radius_m * p.drivetrain_eta / p.gear_ratio)
    limit = np.minimum(p.motor.torque_max_nm,
                       p.motor.power_max_w / np.maximum(omega, 1e-9))
    ok = moving & (torque <= limit) & (omega <= p.motor.speed_max_radps)
    # Braking the machine cannot take goes to the friction brakes and is not
    # recovered; nor is anything above the regeneration power limit.
    machine = np.maximum(torque, -limit)
    eta = _efficiency(p, machine, omega)
    p_mech = machine * omega
    p_elec = np.where(p_mech > 0.0, p_mech / eta, p_mech * eta)
    p_elec = np.maximum(p_elec, -p.regen.power_limit_w)
    energy = (p_elec + aux_power_w(p.aux, T_AMBIENT_C)) * np.where(ok, dt, 0.0)
    return Table(v=v, dt_s=dt, energy_j=energy, accel=a, ok=ok)


def _allowed(tab: Table, route: Route) -> np.ndarray:
    """(nv, nv) pairs inside the route's acceleration bounds."""
    return (tab.ok & (tab.accel <= route.a_max_mps2 + 1e-9)
            & (tab.accel >= route.a_min_mps2 - 1e-9))


def _node_mask(tab: Table, route: Route, k: int) -> np.ndarray:
    """Speeds allowed at node k."""
    if route.stop[k]:
        return tab.v == 0.0
    return (tab.v > 0.0) & (tab.v <= route.limit_mps[k] + 1e-9)


def backward(tab: Table, route: Route, lam_w: float, k0: int, k1: int,
             terminal: np.ndarray | None = None):
    """Cost-to-go from every speed at nodes k0..k1, with `terminal` (one
    value per grid speed, default zero) at k1. Returns J of shape
    (k1 - k0 + 1, nv) and the best next-speed index for each."""
    nv = len(tab.v)
    cost = np.where(_allowed(tab, route),
                    tab.energy_j + lam_w * tab.dt_s, INF)
    J = np.full((k1 - k0 + 1, nv), INF)
    nxt = np.zeros((k1 - k0 + 1, nv), dtype=np.int32)
    last = np.zeros(nv) if terminal is None else np.asarray(terminal, float)
    J[-1] = np.where(_node_mask(tab, route, k1), last, INF)
    for k in range(k1 - 1, k0 - 1, -1):
        total = cost + J[k - k0 + 1][None, :]
        best = np.argmin(total, axis=1)
        val = total[np.arange(nv), best]
        ok = _node_mask(tab, route, k)
        J[k - k0] = np.where(ok, val, INF)
        nxt[k - k0] = best
    return J, nxt


def plan_full(tab: Table, route: Route, lam_w: float):
    """The classical planner. Returns the speed at every node and the
    cost-to-go table, which the learned arms are trained from."""
    J, nxt = backward(tab, route, lam_w, 0, route.n - 1)
    idx = np.zeros(route.n, dtype=np.int32)
    for k in range(route.n - 1):
        idx[k + 1] = nxt[k, idx[k]]
    if J[0, 0] >= INF:
        raise ValueError(f"no feasible profile on {route.name}")
    return tab.v[idx], J, nxt


def plan_receding(tab: Table, route: Route, lam_w: float, horizon: int,
                  terminal: Callable[[int, float], np.ndarray] | None = None,
                  apply: int = 4) -> np.ndarray:
    """Plan `horizon` nodes ahead, drive `apply` of them, plan again.
    `terminal(k, lam_w)` gives the cost of ending the horizon at node k at
    each grid speed; without it the horizon's end costs nothing, and the
    planner has no reason to arrive there at a useful speed."""
    idx = np.zeros(route.n, dtype=np.int32)
    k = 0
    while k < route.n - 1:
        k1 = min(route.n - 1, k + horizon)
        term = None
        if terminal is not None and k1 < route.n - 1:
            term = terminal(k1, lam_w)
        J, nxt = backward(tab, route, lam_w, k, k1, term)
        if J[0, idx[k]] >= INF:
            raise ValueError(f"short horizon infeasible at node {k}")
        for j in range(min(apply, k1 - k)):
            idx[k + j + 1] = nxt[j, idx[k + j]]
        k += min(apply, k1 - k)
    return tab.v[idx]


def meet_arrival(route: Route, plan: Callable[[float], np.ndarray], *,
                 lo_w: float = -2.0e4, hi_w: float = 2.0e5, iters: int = 20):
    """The price on time that makes `plan(lam_w)` arrive on time. Returns the
    profile, the price, and how far from on time it is. Bisection: a higher
    price never makes the full-horizon planner slower, and the short-horizon
    ones follow it closely enough for the bracket to hold. The price may be
    negative: a cycle that dawdled in traffic allows more time than the
    cheapest drive would take, and the planner then has to be paid to use it."""
    best = None
    for _ in range(iters):
        mid = 0.5 * (lo_w + hi_w)
        try:
            v = plan(mid)
        except ValueError:
            lo_w = mid          # too cheap a second to get anywhere
            continue
        gap = planned_time_s(route, v) - route.duration_s
        if best is None or abs(gap) < abs(best[2]):
            best = (v, mid, gap)
        if abs(gap) <= 0.2 * route.arrival_tolerance_s:
            break
        if gap > 0.0:
            lo_w = mid          # late: time must cost more
        else:
            hi_w = mid
    if best is None:
        raise ValueError(f"no feasible profile on {route.name}")
    return best
