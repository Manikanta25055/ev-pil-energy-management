"""Speed planning for energy: the cycle as driven, the classical planner, a
short-horizon planner with and without a learned terminal cost, and a
student policy.

The task and what an arm is judged by are in `evpil.plan.route`, written
before this script. Every arm drives the same route: the same distance, the
same stops and waits, under the same limit and inside the same bounds,
arriving at the cycle's own time within 1%. Each arm's speed profile is then
driven through the plant with the speed loop and the rule energy manager,
and the energy reported is the plant's, on the comparable scale.

  tracked_cycle     the drive cycle as it is: the driver the others replace
  classical         dynamic programming over the whole route
  classical_short   the same, seeing 300 m ahead
  terminal_cost     300 m ahead plus a learned cost of what lies beyond
  student           a network that names the next speed; no optimisation

The two learned arms are trained on the classical planner's solutions for
the training routes (UDDS, WLTC) at ten prices on time. Validation is
HWFET, test is US06. SIMULATED on the laptop.

    PYTHONPATH="src:." python3 scripts/run_energy_planner.py
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

import numpy as np

from evpil.control.cycles import load_cycle
from evpil.control.rule_ems import RuleParams, rule_action
from evpil.control.sim import simulate
from evpil.plan import learned
from evpil.plan import route as rt
from evpil.plan.planner import (
    build_table, meet_arrival, plan_full, plan_receding,
)
from scripts.identify_params import params_from_json

HORIZON_NODES = 30              # 300 m
V_GRID_MAX_MPS = 40.0
MODEL_DIR = Path("models/planner")
_RULES = RuleParams()


def _policy(o):
    return rule_action(_RULES, soc_frac=o.soc_frac, v_mps=o.v_mps)


def train(params, seed: int = 0) -> dict:
    """Fit the terminal cost and the student on the training routes."""
    import torch
    from torch import nn

    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    xs, costs, dvs = [], [], []
    for name in rt.SPLIT_CYCLES["train"]:
        r = rt.route_from_cycle(name)
        tab = build_table(params, r.ds_m, V_GRID_MAX_MPS)
        for lam in learned.LAM_GRID_W:
            _, J, nxt = plan_full(tab, r, lam)
            x, c, dv = learned.training_rows(tab, r, lam, J, nxt)
            xs.append(x), costs.append(c), dvs.append(dv)
    x = np.concatenate(xs)
    record = {"rows": int(len(x)), "seed": seed}
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    keep = rng.permutation(len(x))[:600_000]
    xt = torch.tensor(x[keep], dtype=torch.float32)
    for label, y in (("terminal_cost", np.concatenate(costs)),
                     ("student", np.concatenate(dvs))):
        yt = torch.tensor(y[keep], dtype=torch.float32)
        net = nn.Sequential(nn.Linear(7, 48), nn.Tanh(), nn.Linear(48, 48),
                            nn.Tanh(), nn.Linear(48, 1))
        opt = torch.optim.Adam(net.parameters(), lr=2e-3)
        n_val = len(xt) // 10
        for epoch in range(30):
            order = torch.randperm(len(xt) - n_val) + n_val
            for i in range(0, len(order), 2048):
                b = order[i:i + 2048]
                loss = nn.functional.smooth_l1_loss(net(xt[b])[:, 0], yt[b])
                opt.zero_grad()
                loss.backward()
                opt.step()
        with torch.no_grad():
            held = float(nn.functional.l1_loss(net(xt[:n_val])[:, 0],
                                               yt[:n_val]))
        lin = [m for m in net if isinstance(m, nn.Linear)]
        w = {}
        for i, m in enumerate(lin):
            w[f"w{i}"] = m.weight.detach().numpy()
            w[f"b{i}"] = m.bias.detach().numpy()
        np.savez(MODEL_DIR / f"{label}.npz", **w)
        record[label] = {
            "held_out_mean_abs_error": held,
            "unit": "1e5 J" if label == "terminal_cost" else "m/s",
            "parameters": learned.Mlp(w).n_params()}
        print(f"trained {label}: held-out error {held:.4f} "
              f"{record[label]['unit']}", flush=True)
    return record


def drive(params, cyc) -> dict:
    r = simulate(params, cyc, _policy)
    return {"equivalent_wh_per_km": r.equivalent_wh_per_km,
            "equivalent_wh": r.equivalent_wh,
            "distance_km": r.distance_km,
            "tracking_rmse_mps": r.tracking_rmse_mps,
            "peak_current_a": r.peak_current_a}


def evaluate(params, name: str) -> dict:
    r = rt.route_from_cycle(name)
    tab = build_table(params, r.ds_m, V_GRID_MAX_MPS)
    cost_net = learned.Mlp.load(MODEL_DIR / "terminal_cost.npz")
    student = learned.Mlp.load(MODEL_DIR / "student.npz")
    term = learned.terminal_cost(cost_net, tab, r)
    planners = {
        "classical": lambda lam: plan_full(tab, r, lam)[0],
        "classical_short": lambda lam: plan_receding(tab, r, lam,
                                                     HORIZON_NODES),
        "terminal_cost": lambda lam: plan_receding(tab, r, lam,
                                                   HORIZON_NODES, term),
        "student": lambda lam: learned.plan_student(student, tab, r, lam),
    }
    arms = {}
    cyc = load_cycle(name)
    broken = rt.violations(r, rt.cycle_as_profile(r, name))
    arms["tracked_cycle"] = {
        **drive(params, cyc), "arrival_s": r.duration_s,
        "constraint_violations": {k: v for k, v in broken.items()},
        "note": "the route is made from this cycle; counts above are its "
                "speed snapped to the 10 m nodes, not how it was driven"}
    for label, plan in planners.items():
        t0 = time.time()
        try:
            v, lam, gap = meet_arrival(r, plan)
        except ValueError as e:
            arms[label] = {"failed": str(e)}
            print(f"{name} {label}: FAILED {e}", flush=True)
            continue
        solve_s = time.time() - t0
        t1 = time.time()
        plan(lam)
        once_s = time.time() - t1
        arms[label] = {
            **drive(params, rt.profile_to_cycle(r, v)),
            "arrival_s": rt.planned_time_s(r, v),
            "arrival_gap_s": gap, "price_on_time_w": lam,
            "constraint_violations": rt.violations(r, v),
            "top_speed_mps": float(v.max()),
            "one_plan_s": once_s, "with_time_search_s": solve_s}
    base = arms["tracked_cycle"]["equivalent_wh_per_km"]
    for label, a in arms.items():
        if "equivalent_wh_per_km" in a:
            a["saving_vs_tracked_frac"] = 1.0 - a["equivalent_wh_per_km"] / base
            print(f"{name} {label:16s} {a['equivalent_wh_per_km']:7.2f} Wh/km "
                  f"({100 * a['saving_vs_tracked_frac']:+.1f}%)  arrival "
                  f"{a['arrival_s']:.1f} s  violations "
                  f"{a['constraint_violations']}", flush=True)
    return {"route": name, "distance_m": r.distance_m,
            "duration_s": r.duration_s, "stops": int(r.stop.sum()),
            "arms": arms}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-json", default="docs/week13-energy-planner.json")
    ap.add_argument("--skip-training", action="store_true")
    args = ap.parse_args()
    params = params_from_json("data/i3_params.json")
    record_path = MODEL_DIR / "training.json"
    if args.skip_training and record_path.exists():
        training = json.loads(record_path.read_text())
    else:
        training = train(params)
        record_path.write_text(json.dumps(training, indent=1) + "\n")
    val = evaluate(params, rt.SPLIT_CYCLES["val"][0])
    test = evaluate(params, rt.SPLIT_CYCLES["test"][0])
    r = rt.route_from_cycle(rt.SPLIT_CYCLES["test"][0])
    doc = {
        "provenance": "SIMULATED on the laptop; no board involved; no "
                      "other traffic on the route",
        "split": "test", "route": test["route"],
        "task_config": rt.config_hash(),
        "commit": subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                                 capture_output=True, text=True).stdout.strip(),
        "constraints": {
            "arrival_tolerance_s": r.arrival_tolerance_s,
            "distance_tolerance_frac": rt.DISTANCE_TOL_FRAC,
            "a_max_mps2": r.a_max_mps2, "a_min_mps2": r.a_min_mps2,
            "horizon_m": HORIZON_NODES * r.ds_m},
        "arms": test["arms"], "validation": val, "training": training}
    Path(args.out_json).write_text(json.dumps(doc, indent=1) + "\n")
    print(f"wrote {args.out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
