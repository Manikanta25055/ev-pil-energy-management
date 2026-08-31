"""Week 7: the PID inner loop, the rule-based manager, and the DP optimum.

Three questions, answered in one table.

  1. Does the inner loop track the cycles well enough that an energy
     comparison on top of it is honest?
  2. What does the conventional rule-based energy manager consume?
  3. How much was available? That is the DP optimum, and every controller
     from week 8 onward is reported as a percentage gap to it.

The auxiliary-shed dimension is reported at two prices, because it is the one
action that trades a non-energy good for energy. At price 0 comfort is free
and the optimiser sheds the maximum; at price 1 a watt of cabin heat is worth
exactly the watt it costs and no optimiser sheds anything. Quoting a single
number without saying which was assumed would be the energy-management
equivalent of saving fuel by driving slower.

    PYTHONPATH="src:." python3 scripts/run_control_baselines.py
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

from evpil.control import dp as dpm
from evpil.control.cycles import CONTROL_SPLIT, load_cycle
from evpil.control.rule_ems import EmsAction, RuleParams, rule_action
from evpil.control.sim import fixed_policy, simulate
from scripts.identify_params import params_from_json

CYCLES = ("wltc3b", "udds", "hwfet", "us06")


def split_of(name: str) -> str:
    for k, names in CONTROL_SPLIT.items():
        if name in names:
            return k
    return "unused"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--params", default="data/i3_params.json")
    ap.add_argument("--cycles", nargs="+", default=list(CYCLES))
    ap.add_argument("--soc0", type=float, default=0.80)
    ap.add_argument("--t-ambient", type=float, default=12.0)
    ap.add_argument("--soc-grid", type=int, default=161)
    ap.add_argument("--out-json", default="docs/week7-control-baselines.json")
    ap.add_argument("--out-csv", default="docs/week7-control-baselines.csv")
    args = ap.parse_args()

    params = params_from_json(args.params)
    rules = RuleParams()
    p_open = params.motor.power_max_w * 2.0     # a ceiling that never binds

    def rule_policy(obs):
        return rule_action(rules, soc_frac=obs.soc_frac, v_mps=obs.v_mps)

    rows: list[dict] = []
    for name in args.cycles:
        cycle = load_cycle(name)
        print(f"\n{name}  ({split_of(name)} split, {cycle.duration_s:.0f} s, "
              f"{cycle.distance_m / 1000:.2f} km)")

        arms: dict[str, object] = {
            # No regeneration at all. Not a serious controller: it is the
            # denominator that says how much of the result regen is doing.
            "no-regen": fixed_policy(EmsAction(0.0, p_open, 0.0)),
            # Every controller's floor: recover whatever the pack will take.
            "always-regen": fixed_policy(EmsAction(1.0, p_open, 0.0)),
            "rule-ems": rule_policy,
        }

        results = {}
        for arm, policy in arms.items():
            r = simulate(params, cycle, policy, soc0=args.soc0,
                         t_ambient_c=args.t_ambient)
            results[arm] = r

        for price, label in ((1.0, "dp-comfort-priced"), (0.0, "dp-comfort-free")):
            t0 = time.time()
            sol = dpm.solve(
                params, cycle,
                spec=dpm.DpSpec(soc_grid_n=args.soc_grid, comfort_price=price),
                soc0=args.soc0, t_ambient_c=args.t_ambient,
            )
            r = simulate(params, cycle, dpm.dp_policy(sol, p_open),
                         soc0=args.soc0, t_ambient_c=args.t_ambient)
            results[label] = r
            # The value function is an approximation (it treats the RC branch
            # as exogenous). This is the number that says by how much.
            r.__dict__["dp_predicted_wh"] = sol.predicted_wh
            r.__dict__["dp_solve_s"] = time.time() - t0

        # The optimum is taken on the comparable scale, so that an arm which
        # sheds cabin load cannot appear to beat it.
        optimum = results["dp-comfort-priced"].equivalent_wh
        for arm, r in results.items():
            row = {
                "cycle": name, "split": split_of(name), "arm": arm,
                "tracking_rmse_mps": r.tracking_rmse_mps,
                "tracking_max_mps": r.tracking_max_mps,
                "energy_wh": r.energy_wh, "wh_per_km": r.wh_per_km,
                "equivalent_wh_per_km": r.equivalent_wh_per_km,
                "soc_end": r.soc_end, "peak_current_a": r.peak_current_a,
                "regen_wh": r.regen_wh, "aux_shed_wh": r.aux_shed_wh,
                "gap_to_dp_pct": 100.0 * (r.equivalent_wh - optimum) / optimum,
            }
            if "dp_predicted_wh" in r.__dict__:
                row["dp_predicted_wh"] = r.__dict__["dp_predicted_wh"]
                row["dp_value_error_pct"] = 100.0 * (
                    r.__dict__["dp_predicted_wh"] - r.energy_wh) / r.energy_wh
                row["dp_solve_s"] = r.__dict__["dp_solve_s"]
            rows.append(row)
            print(f"  {arm:19} {r.wh_per_km:7.2f} Wh/km  "
                  f"(equiv {r.equivalent_wh_per_km:7.2f})  "
                  f"regen {r.regen_wh:7.1f} Wh  shed {r.aux_shed_wh:6.1f} Wh  "
                  f"gap {row['gap_to_dp_pct']:+6.2f}%")

    keys = sorted({k for r in rows for k in r})
    head = ["cycle", "split", "arm"] + [k for k in keys
                                        if k not in ("cycle", "split", "arm")]
    lines = [",".join(head)]
    for r in rows:
        lines.append(",".join(
            f"{r[k]:.6g}" if isinstance(r.get(k), float) else str(r.get(k, ""))
            for k in head))
    Path(args.out_csv).write_text("\n".join(lines) + "\n")
    Path(args.out_json).write_text(json.dumps({
        "soc0": args.soc0, "t_ambient_c": args.t_ambient,
        "soc_grid_n": args.soc_grid,
        "control_split": {k: list(v) for k, v in CONTROL_SPLIT.items()},
        "rows": rows,
    }, indent=2) + "\n")
    print(f"\nwrote {args.out_csv} and {args.out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
