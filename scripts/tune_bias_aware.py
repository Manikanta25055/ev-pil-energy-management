"""Set B7's step test on the training split.

The step test is what catches a 0.5 m/s offset at ten times the sensor
noise, and it is marginal there: the offset is two and a half deviations of
one sample. Three settings decide it: how many samples each side
(`step_half`), how many standard errors (`t_step`), and the allowance for
the acceleration channel moving during the window (`step_slope_mps2`).

Each candidate is run on the training cycles only: the two 0.5 m/s offsets
at 10x noise, and clean driving at the floor and at 10x, under white, hard
wander, slope and replayed acceleration error. The rule, fixed here before
the runs:

  1. keep the candidates with fewer than one false alarm per clean hour, at
     the floor and at 10x separately
  2. of those, the fewest offsets missed or late
  3. ties go to the larger t_step, then the smaller window

Validation and test are not opened. SIMULATED on the laptop.

    PYTHONPATH="src:." python3 scripts/tune_bias_aware.py
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.run_sensor_eval import evaluate

GRID = [{"step_half": h, "t_step": t, "step_slope_mps2": sl}
        for h in (20, 30) for t in (5.0, 6.0) for sl in (0.2, 0.3)]
ACCELS = ("white", "wander hard", "slope", "replay")


def main() -> int:
    rows = []
    for g in GRID:
        f = evaluate("b7", "train", settings=g, clean=False, accels=ACCELS,
                     noise_x=(10.0,), fault_labels=("bias +0.5", "bias -0.5"))
        c = evaluate("b7", "train", settings=g, faults=False, accels=ACCELS,
                     cycles=("udds",))
        missed = int(sum(r["delay_s"] is None or r["delay_s"] > 0.5
                         for r in f["faults"]))
        before = int(sum(r["false_alarms_before"] for r in f["faults"]))
        rate = {}
        for mult in (1.0, 10.0):
            sub = [r for r in c["clean"] if r["noise_x"] == mult]
            rate[mult] = (sum(r["false_alarms"] for r in sub)
                          / sum(r["hours"] for r in sub))
        rows.append({**g, "offsets_run": len(f["faults"]), "missed": missed,
                     "false_alarms_before_onset": before,
                     "false_alarms_per_hour_floor": rate[1.0],
                     "false_alarms_per_hour_10x": rate[10.0],
                     "clean_hours_each": sum(r["hours"] for r in c["clean"]) / 2})
        print(rows[-1], flush=True)
    ok = [r for r in rows if r["false_alarms_per_hour_floor"] < 1.0
          and r["false_alarms_per_hour_10x"] < 1.0
          and r["false_alarms_before_onset"] == 0]
    best = min(ok, key=lambda r: (r["missed"], -r["t_step"], r["step_half"]))
    Path("docs/week13-b7-tuning.json").write_text(json.dumps({
        "provenance": "SIMULATED on the laptop; training split only",
        "rule": __doc__.split("the runs:")[1].split("Validation")[0].strip(),
        "chosen": {k: best[k] for k in ("step_half", "t_step",
                                        "step_slope_mps2")},
        "candidates": rows}, indent=1) + "\n")
    print("chosen", best)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
