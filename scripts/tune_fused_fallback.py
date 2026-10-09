"""Set the fused backup speed (B8) on the training split.

Three numbers decide how B8 weighs the model against the acceleration
reading while the speed sensor is flagged: how fast the model's error may
wander (`q_d_mps2`), how fast the accelerometer's may (`q_b_mps2`), and the
white noise on the acceleration reading (`r_a_mps2`).

Each candidate is run on the urban training cycle only, on the faults that
keep the flag up for their whole five seconds (stuck, dropout, a 3 m/s
offset), under four acceleration cases and on the heavier car, at both noise
levels. The rule, fixed here before the runs:

  1. the smallest worst-case tracking error through a fault
  2. ties, within 0.01 m/s, go to the smaller median

Validation and test are not opened. SIMULATED on the laptop.

    PYTHONPATH="src:." python3 scripts/tune_fused_fallback.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from scripts.run_sensor_eval import evaluate

GRID = [{"q_d_mps2": qd, "q_b_mps2": qb, "r_a_mps2": ra}
        for qd in (3e-4, 1e-3, 3e-3) for qb in (3e-4, 1e-3, 3e-3)
        for ra in (0.1, 0.3)]
FAULTS = ("stuck", "dropout", "bias +3.0")
ACCELS = ("white", "wander hard", "slope", "replay")


def main() -> int:
    rows = []
    for g in GRID:
        out = evaluate("b8", "train", settings=g, clean=False, accels=ACCELS,
                       fault_labels=FAULTS, cycles=("udds",))
        peaks = [r["peak_err_mps"] for r in out["faults"]]
        rows.append({**g, "runs": len(peaks),
                     "worst_peak_err_mps": float(max(peaks)),
                     "median_peak_err_mps": float(np.median(peaks)),
                     "stuck_flags": int(sum(r["lingering"]
                                            for r in out["faults"]))})
        print(rows[-1], flush=True)
    best = min(rows, key=lambda r: (round(r["worst_peak_err_mps"], 2),
                                    r["median_peak_err_mps"]))
    ref = evaluate("b7", "train", clean=False, accels=ACCELS,
                   fault_labels=FAULTS, cycles=("udds",))
    ref_peaks = [r["peak_err_mps"] for r in ref["faults"]]
    Path("docs/week14-b8-tuning.json").write_text(json.dumps({
        "provenance": "SIMULATED on the laptop; training split only",
        "rule": __doc__.split("the runs:")[1].split("Validation")[0].strip(),
        "chosen": {k: best[k] for k in ("q_d_mps2", "q_b_mps2", "r_a_mps2")},
        "b7_on_the_same_runs": {
            "worst_peak_err_mps": float(max(ref_peaks)),
            "median_peak_err_mps": float(np.median(ref_peaks))},
        "candidates": rows}, indent=1) + "\n")
    print("chosen", best, "| b7:", max(ref_peaks), np.median(ref_peaks))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
