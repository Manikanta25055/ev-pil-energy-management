"""Week 7: does the inner loop still track when its nominal model is wrong?

On a clean run the feedforward is computed from the same vehicle the plant
simulates, so it is exact and the feedback term corrects almost nothing. The
resulting tracking RMSE of under a millimetre per second is a property of that
arrangement, not evidence that the PID is any good, and quoting it as the
latter would be the control-engineering cousin of testing on the training set.

This script breaks the arrangement on purpose: the feedforward is given a
vehicle that is wrong in the ways a real one is wrong -- heavier than the model
believes, more drag, a road grade the model does not know about -- and the
speed measurement is given noise. What the feedback loop is worth is the
difference between those runs and a run with the feedforward switched off.

    PYTHONPATH="src:." python3 scripts/run_pid_robustness.py
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path

from evpil.control.cycles import load_cycle
from evpil.control.rule_ems import RuleParams, rule_action
from evpil.control.sim import DEFAULT_GAINS, simulate
from scripts.identify_params import params_from_json


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--params", default="data/i3_params.json")
    ap.add_argument("--cycles", nargs="+", default=["udds", "us06"])
    ap.add_argument("--out-csv", default="docs/week7-pid-robustness.csv")
    ap.add_argument("--out-json", default="docs/week7-pid-robustness.json")
    args = ap.parse_args()

    params = params_from_json(args.params)
    rules = RuleParams()

    def policy(obs):
        return rule_action(rules, soc_frac=obs.soc_frac, v_mps=obs.v_mps)

    # A feedforward vehicle with no mass, no drag and no rolling resistance
    # produces zero nominal torque, which is how the feedforward is switched
    # off without adding a branch to the controller.
    no_ff = replace(params, mass_kg=1e-9, c_rr=0.0, cd=1e-12,
                    rot_mass_factor=0.0)

    # Each case is (label, feedforward vehicle, extra simulate kwargs).
    cases = [
        ("nominal", params, {}),
        ("mass +10%", replace(params, mass_kg=params.mass_kg * 1.10), {}),
        ("drag +30%", replace(params, cd=params.cd * 1.30), {}),
        ("rolling +50%", replace(params, c_rr=params.c_rr * 1.50), {}),
        ("grade unknown", params, {"ff_knows_grade": False}),
        ("speed noise 0.2 m/s", params, {"speed_noise_mps": 0.2}),
        ("link delay 100 ms", params, {"delay_steps": 10}),
        ("no feedforward", no_ff, {}),
    ]

    rows = []
    for name in args.cycles:
        # A grade the feedforward does not know about is a separate case: the
        # plant climbs, the nominal model thinks the road is flat.
        for grade_label, cycle in (
            ("flat", load_cycle(name)),
            ("grade +-3% unseen",
             load_cycle(name, grade="sine", grade_amplitude_rad=0.03)),
        ):
            print(f"\n{name} / {grade_label}")
            for label, ff, kwargs in cases:
                if label == "grade unknown" and grade_label == "flat":
                    continue          # nothing to be ignorant of on a flat road
                r = simulate(params, cycle, policy, ff_params=ff,
                             gains=DEFAULT_GAINS, seed=7, **kwargs)
                rows.append({
                    "cycle": name, "grade": grade_label, "case": label,
                    "tracking_rmse_mps": r.tracking_rmse_mps,
                    "tracking_max_mps": r.tracking_max_mps,
                    "wh_per_km": r.wh_per_km,
                })
                print(f"  {label:20} rmse {r.tracking_rmse_mps:8.4f} m/s   "
                      f"max {r.tracking_max_mps:7.3f}   "
                      f"{r.wh_per_km:7.2f} Wh/km")

    head = ["cycle", "grade", "case", "tracking_rmse_mps",
            "tracking_max_mps", "wh_per_km"]
    lines = [",".join(head)]
    for r in rows:
        lines.append(",".join(f"{r[k]:.6g}" if isinstance(r[k], float)
                              else str(r[k]) for k in head))
    Path(args.out_csv).write_text("\n".join(lines) + "\n")
    Path(args.out_json).write_text(json.dumps({"rows": rows}, indent=2) + "\n")
    print(f"\nwrote {args.out_csv} and {args.out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
