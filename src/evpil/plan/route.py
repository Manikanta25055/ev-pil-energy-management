"""The speed-planning task, and what an arm on it is judged by.

`docs/2026-10-07-model-advancement-research.md`, sections 5 and 8. Up to
here every controller followed a speed trace it was handed. A planner
chooses the trace, which is a different task and gets its own definition,
fixed here before any planner was run.

A route is what a drive cycle leaves behind when the driver is taken out:

  distance      the cycle's
  stops         where the cycle stood still, each with the wait it had
  speed limit   at each point, the fastest the cycle went within 150 m
  bounds        the hardest acceleration and braking the cycle used
  arrival       the cycle's duration, within ARRIVAL_TOL_FRAC

A planner may drive any speed profile that makes every stop, keeps under
the limit and inside the bounds, and arrives on time. The cycle itself is
one such profile and is the reference arm.

What this leaves out, and it matters: other traffic. The cycle's own speed
dips that were not stops (a slower car ahead) are not constraints here, so a
planner is free to smooth them away. Savings measured on this task are
savings against a driver in that traffic, on an empty road. They are an
upper bound on what planning buys, not an estimate of it.

Splits follow the rest of the project: train UDDS and WLTC, validation
HWFET, test US06.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

import numpy as np

from evpil.control.cycles import Cycle, load_cycle

DS_M = 10.0                     # node spacing along the route
DV_MPS = 0.5                    # speed grid
LIMIT_WINDOW_M = 150.0
MIN_LIMIT_MPS = 3.0
STOP_MIN_S = 1.0                # standing this long is a stop
ARRIVAL_TOL_FRAC = 0.01         # of the cycle's duration
DISTANCE_TOL_FRAC = 0.01
SPEED_TOL_MPS = 0.5             # over the limit by more than this counts
ACCEL_TOL_MPS2 = 0.05
SPLIT_CYCLES = {"train": ("udds", "wltc3b"), "val": ("hwfet",),
                "test": ("us06",)}


@dataclass(frozen=True)
class Route:
    name: str
    ds_m: float
    limit_mps: np.ndarray       # per node; 0 at a stop
    stop: np.ndarray            # bool per node
    dwell_s: np.ndarray         # per node; 0 away from stops
    a_max_mps2: float
    a_min_mps2: float
    duration_s: float           # the arrival time to meet
    distance_m: float

    @property
    def n(self) -> int:
        return len(self.limit_mps)

    @property
    def arrival_tolerance_s(self) -> float:
        return ARRIVAL_TOL_FRAC * self.duration_s


def route_from_cycle(name: str) -> Route:
    """Take the driver out of a cycle."""
    c = load_cycle(name, dt_s=0.1)
    v, dt = c.v_ref_mps, c.dt_s
    s = np.concatenate([[0.0], np.cumsum(v[:-1] * dt)])
    total = float(s[-1])
    n = int(round(total / DS_M)) + 1
    nodes = np.arange(n) * DS_M

    # Stops: maximal runs of standstill at least STOP_MIN_S long.
    still = v < 0.05
    stop = np.zeros(n, dtype=bool)
    dwell = np.zeros(n)
    k = 0
    while k < len(v):
        if still[k]:
            j = k
            while j < len(v) and still[j]:
                j += 1
            if (j - k) * dt >= STOP_MIN_S or k == 0 or j == len(v):
                node = min(n - 1, int(round(s[k] / DS_M)))
                stop[node] = True
                dwell[node] += (j - k) * dt
            k = j
        else:
            k += 1
    stop[0] = stop[-1] = True

    limit = np.zeros(n)
    for i, x in enumerate(nodes):
        near = (s >= x - LIMIT_WINDOW_M) & (s <= x + LIMIT_WINDOW_M)
        limit[i] = max(MIN_LIMIT_MPS, float(v[near].max()) if near.any()
                       else MIN_LIMIT_MPS)
    limit[stop] = 0.0

    a = np.gradient(np.convolve(v, np.ones(10) / 10, mode="same"), dt)
    return Route(name=name, ds_m=DS_M, limit_mps=limit, stop=stop,
                 dwell_s=dwell, a_max_mps2=float(a.max()),
                 a_min_mps2=float(a.min()), duration_s=float(len(v) * dt),
                 distance_m=float((n - 1) * DS_M))


def profile_to_cycle(route: Route, v_nodes: np.ndarray, *,
                     dt_s: float = 0.01) -> Cycle:
    """A speed at every node, as the time trace the speed loop follows:
    constant acceleration between nodes, and each stop's wait."""
    out: list[np.ndarray] = []
    carry = 0.0                 # time already used of the next sample
    for k in range(route.n):
        if route.dwell_s[k] > 0.0:
            m = int(round(route.dwell_s[k] / dt_s))
            out.append(np.zeros(m))
        if k == route.n - 1:
            break
        v0, v1 = float(v_nodes[k]), float(v_nodes[k + 1])
        if v0 + v1 <= 0.0:
            raise ValueError(f"no motion between nodes {k} and {k + 1}")
        seg_t = 2.0 * route.ds_m / (v0 + v1)
        a = (v1 - v0) / seg_t
        t = np.arange(carry, seg_t, dt_s)
        out.append(v0 + a * t)
        carry = (t[-1] + dt_s - seg_t) if len(t) else carry - seg_t
    v = np.concatenate(out + [np.zeros(int(round(1.0 / dt_s)))])
    return Cycle(name=f"{route.name}-planned", dt_s=dt_s, v_ref_mps=v,
                 grade_rad=np.zeros(len(v)))


def planned_time_s(route: Route, v_nodes: np.ndarray) -> float:
    v0, v1 = v_nodes[:-1], v_nodes[1:]
    return float(np.sum(2.0 * route.ds_m / (v0 + v1)) + route.dwell_s.sum())


def violations(route: Route, v_nodes: np.ndarray) -> dict:
    """What a profile breaks: counted, not judged."""
    v0, v1 = v_nodes[:-1], v_nodes[1:]
    a = (v1 * v1 - v0 * v0) / (2.0 * route.ds_m)
    return {
        "over_limit_nodes": int(np.sum(
            v_nodes > np.where(route.stop, 0.0, route.limit_mps)
            + SPEED_TOL_MPS)),
        "missed_stops": int(np.sum(v_nodes[route.stop] > 0.0)),
        "over_accel_segments": int(np.sum(a > route.a_max_mps2 + ACCEL_TOL_MPS2)),
        "over_brake_segments": int(np.sum(a < route.a_min_mps2 - ACCEL_TOL_MPS2)),
        "late_or_early_s": float(max(0.0, abs(
            planned_time_s(route, v_nodes) - route.duration_s)
            - route.arrival_tolerance_s)),
    }


def cycle_as_profile(route: Route, name: str) -> np.ndarray:
    """The cycle's own speed at each node, for counting what it breaks. Not
    used to drive it: the reference arm follows the cycle's time trace."""
    c = load_cycle(name, dt_s=0.1)
    s = np.concatenate([[0.0], np.cumsum(c.v_ref_mps[:-1] * c.dt_s)])
    v = np.interp(np.arange(route.n) * route.ds_m, s, c.v_ref_mps)
    v[route.stop] = 0.0
    return v


def config_hash() -> str:
    blob = json.dumps([DS_M, DV_MPS, LIMIT_WINDOW_M, MIN_LIMIT_MPS,
                       STOP_MIN_S, ARRIVAL_TOL_FRAC, DISTANCE_TOL_FRAC,
                       SPEED_TOL_MPS, ACCEL_TOL_MPS2, SPLIT_CYCLES],
                      sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]
