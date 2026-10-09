"""Speed planning in traffic: the planner may not stray from the recorded
drive by more than a set distance.

`evpil.plan.route` let the planner drive an empty road, and said so: its
saving is the most planning could give. The recorded drive is a car in
traffic. A second car on the same road at the same time cannot be far from
it: ahead, there is the car the recorded driver was following; behind, the
gap grows and the trip takes longer. This module keeps the planner inside a
corridor around the recorded drive, `width_m` ahead of it and `width_m`
behind, at every second.

  width 0       the recorded drive itself
  width large   the empty road, without the forced stops

Between the two is how much of the saving survives traffic.

The planner works in time, one second at a time. State: how far ahead of
the recorded drive the car is, and its speed. It starts and ends where the
recorded drive does, at rest, so distance and arrival time match exactly.
Speed limit and acceleration bounds are the route's. There is no separate
stop constraint: where the recorded drive stands still, the corridor
stands still with it.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from evpil.control.cycles import Cycle, load_cycle
from evpil.plan.planner import G, RHO, T_AMBIENT_C, _efficiency
from evpil.plan.route import Route, route_from_cycle
from evpil.plant.auxiliary import aux_power_w
from evpil.plant.params import VehicleParams

DT_S = 1.0
DV_MPS = 0.5
DO_M = 0.25                     # offset grid: half of DV times DT
INF = 1e18


@dataclass(frozen=True)
class CorridorPlan:
    v_mps: np.ndarray           # the plan, one speed per second
    offset_m: np.ndarray        # metres ahead of the recorded drive
    model_energy_j: float


def step_energy(p: VehicleParams, v: np.ndarray):
    """Energy and feasibility of going from each grid speed to each other
    in one second: the planner's own model of the car, as in
    `evpil.plan.planner.build_table` but over a time step."""
    v0, v1 = np.meshgrid(v, v, indexing="ij")
    mean = 0.5 * (v0 + v1)
    a = (v1 - v0) / DT_S
    force = np.where(
        mean > 0.0,
        p.c_rr * p.mass_kg * G
        + 0.5 * RHO * p.cd * p.frontal_area_m2 * mean * mean
        + p.mass_kg * (1.0 + p.rot_mass_factor) * a, 0.0)
    omega = mean / p.wheel_radius_m * p.gear_ratio
    torque = np.where(
        force >= 0.0,
        force * p.wheel_radius_m / (p.gear_ratio * p.drivetrain_eta),
        force * p.wheel_radius_m * p.drivetrain_eta / p.gear_ratio)
    limit = np.minimum(p.motor.torque_max_nm,
                       p.motor.power_max_w / np.maximum(omega, 1e-9))
    ok = (torque <= limit) & (omega <= p.motor.speed_max_radps)
    machine = np.maximum(torque, -limit)
    p_mech = machine * omega
    eta = _efficiency(p, machine, omega)
    p_elec = np.where(p_mech > 0.0, p_mech / eta, p_mech * eta)
    p_elec = np.maximum(p_elec, -p.regen.power_limit_w)
    energy = (p_elec + aux_power_w(p.aux, T_AMBIENT_C)) * DT_S
    return energy, ok, a


def recorded(name: str):
    """The recorded drive at one-second steps, its position rounded to the
    offset grid so that the planner's arithmetic is exact."""
    c = load_cycle(name, dt_s=DT_S)
    v = c.v_ref_mps
    s = np.concatenate([[0.0], np.cumsum(0.5 * (v[:-1] + v[1:]) * DT_S)])
    return v, np.round(s / DO_M) * DO_M


def plan_corridor(p: VehicleParams, name: str, width_m: float,
                  route: Route | None = None) -> CorridorPlan:
    route = route or route_from_cycle(name)
    _, s_c = recorded(name)
    T = len(s_c) - 1
    v = np.arange(0.0, 40.0 + DV_MPS / 2, DV_MPS)
    nv = len(v)
    n_half = int(round(width_m / DO_M))
    no = 2 * n_half + 1
    off = (np.arange(no) - n_half) * DO_M
    energy, ok, a = step_energy(p, v)
    allowed = ok & (a <= route.a_max_mps2 + 1e-9) & (a >= route.a_min_mps2 - 1e-9)
    k_lo = int(np.floor(route.a_min_mps2 * DT_S / DV_MPS))
    k_hi = int(np.ceil(route.a_max_mps2 * DT_S / DV_MPS))
    node_s = np.arange(route.n) * route.ds_m
    # The limit where the recorded drive stood still is zero in the route;
    # here the corridor does that job, so the limit is bridged across stops.
    lim_nodes = np.where(route.stop, np.nan, route.limit_mps)
    idx = np.arange(route.n)
    good = ~np.isnan(lim_nodes)
    lim_nodes = np.interp(idx, idx[good], lim_nodes[good])

    def limit_at(t: int) -> np.ndarray:
        return np.interp(s_c[t] + off, node_s, lim_nodes)

    J = np.full((no, nv), INF)
    J[n_half, 0] = 0.0
    best = np.zeros((T, no, nv), dtype=np.int8)
    for t in range(T - 1, -1, -1):
        d_c = (s_c[t + 1] - s_c[t]) / DO_M
        new = np.full((no, nv), INF)
        arg = np.zeros((no, nv), dtype=np.int8)
        for i in range(nv):
            for k in range(k_lo, k_hi + 1):
                j = i + k
                if j < 0 or j >= nv or not allowed[i, j]:
                    continue
                # Offset moves by the car's distance minus the recorded one.
                m = int(round(0.5 * (v[i] + v[j]) * DT_S / DO_M - d_c))
                lo, hi = max(0, -m), min(no, no - m)
                if lo >= hi:
                    continue
                cand = energy[i, j] + J[lo + m:hi + m, j]
                seg = new[lo:hi, i]
                better = cand < seg
                seg[better] = cand[better]
                arg[lo:hi, i][better] = k
        new[v[None, :] > limit_at(t)[:, None] + 1e-9] = INF
        J, best[t] = new, arg
    if J[n_half, 0] >= INF:
        raise ValueError(f"no plan inside {width_m} m of {name}")
    o, i = n_half, 0
    vs, os_ = [0.0], [0.0]
    for t in range(T):
        k = int(best[t, o, i])
        j = i + k
        d_c = (s_c[t + 1] - s_c[t]) / DO_M
        o += int(round(0.5 * (v[i] + v[j]) * DT_S / DO_M - d_c))
        i = j
        vs.append(float(v[i]))
        os_.append((o - n_half) * DO_M)
    return CorridorPlan(np.array(vs), np.array(os_), float(J[n_half, 0]))


def plan_to_cycle(name: str, plan: CorridorPlan, *,
                  dt_s: float = 0.01) -> Cycle:
    """The plan as the 10 ms trace the speed loop follows."""
    t1 = np.arange(len(plan.v_mps)) * DT_S
    t = np.arange(0.0, t1[-1] + 1.0, dt_s)
    v = np.interp(t, t1, plan.v_mps, right=0.0)
    return Cycle(name=f"{name}-corridor", dt_s=dt_s, v_ref_mps=v,
                 grade_rad=np.zeros(len(v)))
