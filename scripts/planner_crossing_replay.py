"""Track C: frozen-price replay of the four planner arms, with the planned
time, the reference-cycle duration and the achieved distance crossing kept
apart. docs/2026-10-14-paper-validation-addendum-plan.md, section C.

Run from a checkout of the frozen tree befecb8 (its src/, data/ and
models/planner/), with this file passed by absolute path:

    git worktree add /tmp/befecb8 befecb8
    cd /tmp/befecb8 && PYTHONPATH="src:." python3 <repo>/scripts/planner_crossing_replay.py \
        --out <repo>/docs/2026-10-14-planner-crossing-replay.json

At most eight replays: classical, classical_short, terminal_cost and student
on US06 and HWFET, each at its stored price_on_time_w from
docs/week13-energy-planner.json. No retraining, no bisection (meet_arrival is
bypassed), no tracked-cycle replay. SIMULATED on the host.

Tolerances, declared before the run: a replay reproduces the stored arm if
equivalent_wh_per_km agrees within 1e-6 relative, distance_km within 1e-9 km
and planned arrival within 1e-6 s. Otherwise it is labelled a new frozen
reconstruction and is not used to revise any historical saving.

Distance crossing uses the production interval convention: distance +=
|v_pre_step| * dt, trace times mark interval starts. In the crossing interval
k, f is the remaining distance over that interval's distance; the crossing
time is k*dt + f*dt, and a fraction f of that interval's terminal energy and
auxiliary-shed adjustment is included. A profile that never reaches the
endpoint is reported as non-crossing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np

from evpil.control.cycles import load_cycle  # noqa: F401  (frozen-tree import check)
from evpil.control.rule_ems import RuleParams, rule_action
from evpil.control.sim import simulate
from evpil.plan import learned
from evpil.plan import route as rt
from evpil.plan.planner import build_table, plan_full, plan_receding
from evpil.plant.auxiliary import aux_power_w
from scripts.identify_params import params_from_json

ARMS = ("classical", "classical_short", "terminal_cost", "student")
HORIZON_NODES = 30
V_GRID_MAX_MPS = 40.0
T_AMBIENT_C = 12.0
_RULES = RuleParams()
FILES = ["src/evpil/plan/planner.py", "src/evpil/plan/learned.py", "src/evpil/plan/route.py",
         "src/evpil/control/sim.py", "src/evpil/plant/plant.py", "src/evpil/control/rule_ems.py",
         "src/evpil/control/cycles.py", "scripts/run_energy_planner.py", "data/i3_params.json",
         "models/planner/terminal_cost.npz", "models/planner/student.npz",
         "models/planner/training.json"]


def _policy(o):
    return rule_action(_RULES, soc_frac=o.soc_frac, v_mps=o.v_mps)


def _git(*a):
    return subprocess.run(["git", *a], capture_output=True, text=True).stdout.strip()


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def crossing(trace, dt, target_m, aux_full_w):
    v = np.abs(trace.v_mps)
    seg = v * dt
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    e_seg = trace.p_batt_w * dt / 3600.0
    shed_seg = (aux_full_w - trace.p_aux_w) * dt / 3600.0
    k = int(np.searchsorted(cum, target_m, side="left")) - 1
    if cum[-1] < target_m or k < 0:
        return {"crossed": False, "final_distance_m": float(cum[-1])}
    f = (target_m - cum[k]) / seg[k] if seg[k] > 0 else 0.0
    return {"crossed": True, "interval": k, "fraction": float(f),
            "crossing_time_s": float(k * dt + f * dt),
            "energy_to_crossing_wh": float(e_seg[:k].sum() + f * e_seg[k]),
            "aux_shed_to_crossing_wh": float(shed_seg[:k].sum() + f * shed_seg[k]),
            "final_distance_m": float(cum[-1])}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--stored", default=None,
                    help="stored table; default docs/week13-energy-planner.json of this tree")
    args = ap.parse_args()
    stored_path = Path(args.stored or "docs/week13-energy-planner.json")
    stored = json.loads(stored_path.read_text())
    params = params_from_json("data/i3_params.json")
    cost_net = learned.Mlp.load("models/planner/terminal_cost.npz")
    student = learned.Mlp.load("models/planner/student.npz")
    aux_full = aux_power_w(params.aux, T_AMBIENT_C)
    out = {"provenance": "SIMULATED on the host; frozen-price replay, no retraining, no bisection",
           "head": _git("rev-parse", "HEAD"), "tree": _git("rev-parse", "HEAD^{tree}"),
           "blobs": {f: _git("rev-parse", f"HEAD:{f}") for f in FILES},
           "sha256": {f: sha256(f) for f in FILES},
           "stored_table": str(stored_path), "stored_table_sha256": sha256(stored_path),
           "stored_commit_field": stored.get("commit"),
           "task_config": rt.config_hash(),
           "tolerances": {"equivalent_wh_per_km_rel": 1e-6, "distance_km_abs": 1e-9, "arrival_s_abs": 1e-6},
           "routes": {}}
    for name, arms in (("us06", stored["arms"]), ("hwfet", stored["validation"]["arms"])):
        r = rt.route_from_cycle(name)
        tab = build_table(params, r.ds_m, V_GRID_MAX_MPS)
        term = learned.terminal_cost(cost_net, tab, r)
        planners = {
            "classical": lambda lam: plan_full(tab, r, lam)[0],
            "classical_short": lambda lam: plan_receding(tab, r, lam, HORIZON_NODES),
            "terminal_cost": lambda lam: plan_receding(tab, r, lam, HORIZON_NODES, term),
            "student": lambda lam: learned.plan_student(student, tab, r, lam),
        }
        rows = {}
        for arm in ARMS:
            lam = arms[arm]["price_on_time_w"]
            v = planners[arm](lam)
            cyc = rt.profile_to_cycle(r, v)
            res = simulate(params, cyc, _policy, keep_trace=True)
            dt = cyc.dt_s
            tr = res.trace
            recon_dist_m = float(np.sum(np.abs(tr.v_mps)) * dt)
            recon_energy_wh = float(np.sum(tr.p_batt_w) * dt / 3600.0)
            s = arms[arm]
            match = (abs(res.equivalent_wh_per_km / s["equivalent_wh_per_km"] - 1) <= 1e-6
                     and abs(res.distance_km - s["distance_km"]) <= 1e-9
                     and abs(rt.planned_time_s(r, v) - s["arrival_s"]) <= 1e-6)
            rows[arm] = {
                "price_on_time_w": lam,
                "profile_sha256": hashlib.sha256(np.asarray(v, dtype=np.float64).tobytes()).hexdigest(),
                "planned_time_s": rt.planned_time_s(r, v),
                "reference_cycle_duration_s": r.duration_s,
                "trace_duration_s": len(cyc.v_ref_mps) * dt,
                "route_endpoint_m": r.distance_m,
                "distance_km": res.distance_km,
                "endpoint_distance_tolerance_m": rt.DISTANCE_TOL_FRAC * r.distance_m,
                "equivalent_wh_per_km": res.equivalent_wh_per_km,
                "energy_wh": res.energy_wh, "aux_shed_wh": res.aux_shed_wh,
                "reconstruction_check": {
                    "distance_m": recon_dist_m, "distance_err_m": recon_dist_m - 1000 * res.distance_km,
                    "energy_wh": recon_energy_wh, "energy_err_wh": recon_energy_wh - res.energy_wh},
                "crossing": crossing(tr, dt, r.distance_m, aux_full),
                "planned_node_profile_diagnostics": rt.violations(r, v),
                "stored": {k: s[k] for k in ("equivalent_wh_per_km", "distance_km", "arrival_s")},
                "label": "frozen-snapshot reproduction" if match else "new frozen reconstruction",
            }
            c = rows[arm]["crossing"]
            print(f"{name} {arm:16s} {res.equivalent_wh_per_km:8.3f} Wh/km  planned "
                  f"{rows[arm]['planned_time_s']:7.2f} s  crossing "
                  f"{c.get('crossing_time_s', float('nan')):7.2f} s  {rows[arm]['label']}", flush=True)
        out["routes"][name] = {"duration_s": r.duration_s, "distance_m": r.distance_m,
                               "arrival_tolerance_s": r.arrival_tolerance_s, "arms": rows}
    Path(args.out).write_text(json.dumps(out, indent=1) + "\n")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
