"""The two learned planning arms, and the small network both use.

  terminal cost   what the rest of the route costs from the speed a short
                  horizon ends at, learned from the classical planner's own
                  cost-to-go on the training routes. The short-horizon
                  planner adds it at its last node.
  student         the classical planner's choice of next speed, learned
                  directly: no optimisation at run time at all.

Both see the same seven numbers about a node: the speed, the limit there and
100, 200 and 400 m on, the distance to the next stop, and the price on time.
Neither sees the rest of the route.

Both are guarded by arithmetic rather than trusted: a speed from which the
stops and limits ahead cannot be met inside the braking bound is never
offered to the short horizon and never taken by the student. That set is
worked out exactly on the speed grid (`drivable`); it depends on the route
only as far ahead as the car needs to brake.

The network is run in numpy from saved weights. Training is in
scripts/run_energy_planner.py.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from evpil.plan.planner import INF, Table, _allowed, _node_mask
from evpil.plan.route import Route

LOOKAHEAD_NODES = (0, 10, 20, 40)
STOP_CAP_M = 1000.0
COST_SCALE_J = 1.0e5
COST_CAP = 5.0                  # in units of COST_SCALE_J
# Prices on time the learned arms are trained at. Zero and a negative one
# are in it because a route with slack in its arrival time needs them.
LAM_GRID_W = (-4000.0, 0.0, 500.0, 1000.0, 2000.0, 4000.0, 8000.0, 16000.0,
              32000.0, 64000.0)
LAM_SCALE_W = 64000.0


def stop_distance(route: Route) -> np.ndarray:
    """Metres from each node to the next stop at or after it."""
    d = np.zeros(route.n)
    nxt = route.n - 1
    for k in range(route.n - 1, -1, -1):
        if route.stop[k]:
            nxt = k
        d[k] = (nxt - k) * route.ds_m
    return d


def node_features(route: Route, k: int, lam_w: float,
                  d_stop: np.ndarray) -> np.ndarray:
    """The six numbers that do not depend on the speed."""
    lim = [route.limit_mps[min(route.n - 1, k + j)] / 40.0
           for j in LOOKAHEAD_NODES]
    return np.array(lim + [min(d_stop[k], STOP_CAP_M) / STOP_CAP_M,
                           lam_w / LAM_SCALE_W])


def drivable(tab: Table, route: Route) -> np.ndarray:
    """(n, nv): the speeds at each node from which the rest of the route can
    be driven inside the bounds. No cost in it, only whether."""
    allowed = _allowed(tab, route)
    out = np.zeros((route.n, len(tab.v)), dtype=bool)
    out[-1] = _node_mask(tab, route, route.n - 1)
    for k in range(route.n - 2, -1, -1):
        out[k] = _node_mask(tab, route, k) & (allowed & out[k + 1][None, :]).any(axis=1)
    return out


class Mlp:
    """A three-layer perceptron with tanh units."""

    def __init__(self, weights: dict) -> None:
        self.w = [np.asarray(weights[f"w{i}"], dtype=np.float64)
                  for i in range(3)]
        self.b = [np.asarray(weights[f"b{i}"], dtype=np.float64)
                  for i in range(3)]

    @classmethod
    def load(cls, path: Path | str) -> "Mlp":
        with np.load(path) as z:
            return cls({k: z[k] for k in z.files})

    def n_params(self) -> int:
        return int(sum(w.size for w in self.w) + sum(b.size for b in self.b))

    def __call__(self, x: np.ndarray) -> np.ndarray:
        h = np.tanh(x @ self.w[0].T + self.b[0])
        h = np.tanh(h @ self.w[1].T + self.b[1])
        return (h @ self.w[2].T + self.b[2])[:, 0]


def _with_speed(v: np.ndarray, node: np.ndarray) -> np.ndarray:
    return np.column_stack([v / 40.0, np.tile(node, (len(v), 1))])


def terminal_cost(net: Mlp, tab: Table, route: Route):
    """The function plan_receding wants: node and price in, a cost for each
    grid speed out."""
    d_stop = stop_distance(route)
    ok = drivable(tab, route)

    def cost(k: int, lam_w: float) -> np.ndarray:
        x = _with_speed(tab.v, node_features(route, k, lam_w, d_stop))
        out = np.clip(net(x), 0.0, COST_CAP) * COST_SCALE_J
        return np.where(ok[k], out, INF)

    return cost


def plan_student(net: Mlp, tab: Table, route: Route,
                 lam_w: float) -> np.ndarray:
    """Roll the student along the route. At each node it names a change of
    speed; the nearest speed that the bounds, the limit and the next stop
    allow is taken."""
    d_stop = stop_distance(route)
    allowed = _allowed(tab, route)
    can = drivable(tab, route)
    idx = np.zeros(route.n, dtype=np.int32)
    for k in range(route.n - 1):
        i = idx[k]
        x = _with_speed(tab.v[i:i + 1],
                        node_features(route, k, lam_w, d_stop))
        want = tab.v[i] + float(net(x)[0])
        ok = allowed[i] & can[k + 1]
        if not ok.any():
            raise ValueError(f"student stranded at node {k}")
        cand = np.flatnonzero(ok)
        idx[k + 1] = cand[np.argmin(np.abs(tab.v[cand] - want))]
    return tab.v[idx]


def training_rows(tab: Table, route: Route, lam_w: float, J: np.ndarray,
                  nxt: np.ndarray):
    """Features, cost-to-go above the node's best, and the planner's change
    of speed, for every (node, speed) the planner could be at."""
    d_stop = stop_distance(route)
    xs, cost, dv = [], [], []
    for k in range(route.n - 1):
        ok = J[k] < INF
        if not ok.any():
            continue
        v = tab.v[ok]
        xs.append(_with_speed(v, node_features(route, k, lam_w, d_stop)))
        cost.append(np.minimum((J[k][ok] - J[k][ok].min()) / COST_SCALE_J,
                               COST_CAP))
        dv.append(tab.v[nxt[k][ok]] - v)
    return np.concatenate(xs), np.concatenate(cost), np.concatenate(dv)
