"""The board campaign's fault cases, on the laptop.

The same 40 cases scripts/run_b7_pil.py ran on the chip, through the
simulation's own loop, for the three arms. The noise draws are not the
board's (the board campaign puts noise on every channel from one generator,
the simulation on two), so this is the same experiment, not the same
samples. Writes docs/week13-b7-pil-sim.json. SIMULATED.

    PYTHONPATH="src:." python3 scripts/sim_b7_pil_cases.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from evpil.control import sensor_eval as se
from scripts.identify_params import params_from_json
from scripts.run_b7_pil import cases
from scripts.sensor_arms import make_arm

ARMS = (("B6", "b6", None), ("B7", "b7", None),
        ("B7 + rule monitor", "sup", {"fast": "monitor"}))


def main() -> int:
    nominal = params_from_json("data/i3_params.json")
    tuned = json.loads(Path("docs/week11-speed-arms-tuned.json").read_text())
    q, q_d = tuned["b3a"]["q_mps"], tuned["b5"]["q_d_mps2"]
    todo = [c for c in cases() if c.fault]
    out = {"provenance": "SIMULATED on the laptop; the board campaign's "
                         "fault cases, different noise draws",
           "arms": {}}
    for label, arm, settings in ARMS:
        rows = [se.run_fault_case(
            nominal, c, lambda: make_arm(arm, nominal, q, q_d, settings))
            for c in todo]
        ok = [r["delay_s"] is not None and r["delay_s"] <= 0.5 for r in rows]
        delays = [r["delay_s"] for r in rows if r["delay_s"] is not None]
        out["arms"][label] = {
            "fault_runs": len(rows), "detected_in_time": int(sum(ok)),
            "worst_delay_s": max(delays) if delays else None,
            "alarms_before_onset": int(sum(r["false_alarms_before"]
                                           for r in rows)),
            "released_early": int(sum(r["false_clear"] for r in rows)),
            "still_flagged_at_end": int(sum(r["lingering"] for r in rows)),
            "worst_peak_err_mps": float(max(r["peak_err_mps"] for r in rows)),
            "median_peak_err_mps": float(np.median(
                [r["peak_err_mps"] for r in rows]))}
        a = out["arms"][label]
        print(f"{label:20s} caught {a['detected_in_time']}/40  worst delay "
              f"{a['worst_delay_s']}  early {a['released_early']}  stuck "
              f"{a['still_flagged_at_end']}  worst peak "
              f"{a['worst_peak_err_mps']:.2f}  median "
              f"{a['median_peak_err_mps']:.2f}", flush=True)
    Path("docs/week13-b7-pil-sim.json").write_text(
        json.dumps(out, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
