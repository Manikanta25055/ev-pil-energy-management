"""How much of the planning saving survives traffic.

The planner of `evpil.plan.corridor` is run with the car held within 5, 10,
25, 50, 100 and 200 m of the recorded drive, on the highway (validation) and
aggressive (test) routes. Each plan is driven through the plant with the
speed loop and the rule energy manager, beside the recorded drive itself.
Distance and arrival time are the recorded drive's exactly, by construction.
No learning in this experiment. SIMULATED on the laptop.

    PYTHONPATH="src:." python3 scripts/run_corridor_planner.py
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import numpy as np

from evpil.control.cycles import load_cycle
from evpil.control.rule_ems import RuleParams, rule_action
from evpil.control.sim import simulate
from evpil.plan import corridor
from evpil.plan.route import route_from_cycle
from scripts.identify_params import params_from_json

WIDTHS_M = (5.0, 10.0, 25.0, 50.0, 100.0, 200.0)
ROUTES = (("val", "hwfet"), ("test", "us06"))
_RULES = RuleParams()


def _policy(o):
    return rule_action(_RULES, soc_frac=o.soc_frac, v_mps=o.v_mps)


def drive(params, cyc) -> dict:
    r = simulate(params, cyc, _policy)
    return {"equivalent_wh_per_km": r.equivalent_wh_per_km,
            "equivalent_wh": r.equivalent_wh, "distance_km": r.distance_km,
            "peak_current_a": r.peak_current_a,
            "tracking_rmse_mps": r.tracking_rmse_mps}


def main() -> int:
    params = params_from_json("data/i3_params.json")
    doc = {"provenance": "SIMULATED on the laptop; no board involved",
           "commit": subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                                    capture_output=True, text=True).stdout.strip(),
           "what": "planner held within a corridor around the recorded "
                   "drive, in metres ahead and behind; one run per width",
           "routes": {}}
    for split, name in ROUTES:
        route = route_from_cycle(name)
        base = drive(params, load_cycle(name))
        rows = {"recorded": {**base, "width_m": 0.0}}
        print(f"{name} recorded      {base['equivalent_wh_per_km']:7.2f} Wh/km",
              flush=True)
        for w in WIDTHS_M:
            t0 = time.time()
            plan = corridor.plan_corridor(params, name, w, route)
            d = drive(params, corridor.plan_to_cycle(name, plan))
            rows[f"{w:g} m"] = {
                **d, "width_m": w,
                "saving_vs_recorded_frac":
                    1.0 - d["equivalent_wh_per_km"] / base["equivalent_wh_per_km"],
                "furthest_ahead_m": float(plan.offset_m.max()),
                "furthest_behind_m": float(-plan.offset_m.min()),
                "top_speed_mps": float(plan.v_mps.max()),
                "seconds_at_rest": int(np.sum(plan.v_mps == 0.0)),
                "plan_s": time.time() - t0}
            r = rows[f"{w:g} m"]
            print(f"{name} within {w:5g} m {r['equivalent_wh_per_km']:7.2f} "
                  f"Wh/km ({100 * r['saving_vs_recorded_frac']:+.1f}%)  "
                  f"ahead {r['furthest_ahead_m']:.0f} behind "
                  f"{r['furthest_behind_m']:.0f}  peak "
                  f"{r['peak_current_a']:.0f} A  [{r['plan_s']:.0f} s]",
                  flush=True)
        doc["routes"][name] = {"split": split, "rows": rows,
                               "a_max_mps2": route.a_max_mps2,
                               "a_min_mps2": route.a_min_mps2}
    Path("docs/week14-corridor-planner.json").write_text(
        json.dumps(doc, indent=1) + "\n")
    print("wrote docs/week14-corridor-planner.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
