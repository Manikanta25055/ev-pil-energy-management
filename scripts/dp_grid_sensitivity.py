"""Review R1 (2026-10-30): does the DP reference move with its discretisation?

The DP of scripts/run_control_baselines.py carries SOC as its only state, treats
the RC branch as exogenous (taken from a nominal forward run) and holds the
discharge ceiling at the motor maximum. Its reference energy is the derived
policy run through the full vehicle model. This script re-solves it on finer and
coarser SOC grids and action sets and reports the rule-based manager's gap to
each reference. It says how sensitive the 0.01 to 0.16% gaps are to the grid;
it does not turn the reference into a certified optimum. SIMULATED.

    PYTHONPATH="src:." python3 scripts/dp_grid_sensitivity.py
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from evpil.control import dp as dpm
from evpil.control.cycles import load_cycle
from evpil.control.rule_ems import RuleParams, rule_action
from evpil.control.sim import simulate
from scripts.identify_params import params_from_json

CYCLES = ("wltc3b", "udds", "hwfet", "us06")
GRIDS = {
    "coarse": dict(soc_grid_n=81, blends=(0.0, 0.5, 1.0), derates=(0.0, 0.30)),
    "nominal": dict(soc_grid_n=161),
    "fine_soc": dict(soc_grid_n=321),
    "fine_actions": dict(soc_grid_n=161,
                         blends=tuple(np.round(np.linspace(0, 1, 11), 2)),
                         derates=tuple(np.round(np.linspace(0, 0.3, 7), 3))),
    "fine_both": dict(soc_grid_n=321,
                      blends=tuple(np.round(np.linspace(0, 1, 11), 2)),
                      derates=tuple(np.round(np.linspace(0, 0.3, 7), 3))),
}
OUT = Path("docs/2026-10-30-dp-grid-sensitivity.json")


def main() -> int:
    params = params_from_json("data/i3_params.json")
    p_open = params.motor.power_max_w * 2.0
    rules = RuleParams()
    soc0, t_amb = 0.80, 12.0

    rows = []
    for name in CYCLES:
        cycle = load_cycle(name)
        rule = simulate(params, cycle,
                        lambda o: rule_action(rules, soc_frac=o.soc_frac, v_mps=o.v_mps),
                        soc0=soc0, t_ambient_c=t_amb)
        for label, kw in GRIDS.items():
            t0 = time.time()
            sol = dpm.solve(params, cycle,
                            spec=dpm.DpSpec(comfort_price=1.0, **kw),
                            soc0=soc0, t_ambient_c=t_amb)
            r = simulate(params, cycle, dpm.dp_policy(sol, p_open),
                         soc0=soc0, t_ambient_c=t_amb)
            gap = 100.0 * (rule.equivalent_wh - r.equivalent_wh) / r.equivalent_wh
            rows.append({
                "cycle": name, "grid": label, "soc_grid_n": sol.spec.soc_grid_n,
                "n_blends": len(sol.spec.blends), "n_derates": len(sol.spec.derates),
                "dp_equivalent_wh_per_km": r.equivalent_wh_per_km,
                "dp_value_error_pct": 100.0 * (sol.predicted_wh - r.energy_wh) / r.energy_wh,
                "rule_equivalent_wh_per_km": rule.equivalent_wh_per_km,
                "rule_gap_pct": gap, "solve_s": time.time() - t0,
            })
            print(f"{name:7} {label:13} DP {r.equivalent_wh_per_km:8.3f} Wh/km  "
                  f"rule gap {gap:+.3f}%")

    gaps = {}
    for name in CYCLES:
        g = [r["rule_gap_pct"] for r in rows if r["cycle"] == name]
        gaps[name] = {"min_pct": min(g), "max_pct": max(g)}
    OUT.write_text(json.dumps({
        "provenance": "SIMULATED on the host; corrected plant; review item R1",
        "soc0": soc0, "t_ambient_c": t_amb, "comfort_price": 1.0,
        "ceiling": "held at twice the motor maximum, as in the reference",
        "rows": rows, "rule_gap_range_by_cycle": gaps,
    }, indent=2) + "\n")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
