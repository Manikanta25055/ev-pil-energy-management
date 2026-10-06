"""The power-ceiling correction, before and after, from one script.

Until commit 82ca2fe the plant capped the battery power it billed at the
commanded ceiling but computed acceleration from the unclipped torque, so a
binding ceiling lowered the bill and left the drive alone. This runs the same
controllers against the plant as it stood and as it stands, so the correction
is a measurement in the repository rather than a paragraph.

The old plant is not kept in the tree. It is read out of history, from the
parent of the fixing commit, and swapped in for the "before" runs only.

    PYTHONPATH="src:." python3 scripts/run_plant_correction.py
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import types
from pathlib import Path

from evpil.control import sim
from evpil.control.actor import Actor
from evpil.control.cycles import CONTROL_SPLIT, load_cycle
from evpil.control.rule_ems import EmsAction, RuleParams, rule_action
from evpil.control.sac_policy import actor_policy
from evpil.control.sim import fixed_policy, simulate
from evpil.plant.plant import Plant as FixedPlant
from scripts.identify_params import params_from_json

FIX_COMMIT = "82ca2fe"
CEILINGS_KW = (250, 80, 60, 40, 20, 5)
CYCLES = ("wltc3b", "udds", "hwfet", "us06")


def legacy_plant():
    """The Plant class from the commit before the fix."""
    src = subprocess.run(
        ["git", "show", f"{FIX_COMMIT}^:src/evpil/plant/plant.py"],
        check=True, capture_output=True, text=True).stdout
    mod = types.ModuleType("evpil_plant_legacy")
    mod.__dict__["__name__"] = "evpil_plant_legacy"
    sys.modules["evpil_plant_legacy"] = mod
    exec(compile(src, "plant_legacy.py", "exec"), mod.__dict__)
    return mod.Plant


def row(plant: str, cycle: str, arm: str, r) -> dict:
    return {
        "plant": plant, "cycle": cycle, "arm": arm,
        "equivalent_wh_per_km": r.equivalent_wh_per_km,
        "wh_per_km": r.wh_per_km,
        "distance_km": r.distance_km,
        "tracking_rmse_mps": r.tracking_rmse_mps,
        "tracking_max_mps": r.tracking_max_mps,
        "peak_current_a": r.peak_current_a,
        "soc_end": r.soc_end,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--params", default="data/i3_params.json")
    ap.add_argument("--actor",
                    default="data/actors/sac-without-forecast-seed3.npz")
    ap.add_argument("--soc0", type=float, default=0.80)
    ap.add_argument("--t-ambient", type=float, default=12.0)
    ap.add_argument("--out-json", default="docs/week11-plant-correction.json")
    args = ap.parse_args()

    params = params_from_json(args.params)
    rules = RuleParams()
    actor = Actor.load(args.actor)
    kw = dict(soc0=args.soc0, t_ambient_c=args.t_ambient)

    def rule_policy(obs):
        return rule_action(rules, soc_frac=obs.soc_frac, v_mps=obs.v_mps)

    rows: list[dict] = []
    for label, plant_cls in (("before", legacy_plant()), ("after", FixedPlant)):
        sim.Plant = plant_cls
        try:
            us06 = load_cycle("us06")
            for kw_lim in CEILINGS_KW:
                r = simulate(params, us06, fixed_policy(
                    EmsAction(1.0, kw_lim * 1000.0, 0.0)), **kw)
                rows.append(row(label, "us06", f"ceiling-{kw_lim}kw", r))
                print(f"{label:6s} us06   ceiling {kw_lim:3d} kW  "
                      f"{r.equivalent_wh_per_km:7.2f} Wh/km  "
                      f"rmse {r.tracking_rmse_mps:.4f}", flush=True)
            for name in CYCLES:
                cycle = load_cycle(name)
                for arm, policy in (
                    ("rule", rule_policy),
                    ("actor", actor_policy(actor, cycle, params,
                                           use_forecast=False)),
                ):
                    r = simulate(params, cycle, policy, **kw)
                    rows.append(row(label, name, arm, r))
                    print(f"{label:6s} {name:6s} {arm:5s}  "
                          f"{r.equivalent_wh_per_km:7.2f} Wh/km  "
                          f"rmse {r.tracking_rmse_mps:.4f}", flush=True)
        finally:
            sim.Plant = FixedPlant

    out = {
        "fix_commit": FIX_COMMIT,
        "actor": args.actor,
        "soc0": args.soc0,
        "t_ambient_c": args.t_ambient,
        "split": {c: next(k for k, v in CONTROL_SPLIT.items() if c in v)
                  for c in CYCLES},
        "provenance": "SIMULATED on the laptop; no board involved",
        "rows": rows,
    }
    Path(args.out_json).write_text(json.dumps(out, indent=1))
    print(f"wrote {args.out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
