"""Pool the board fault campaign over its three draws of noise.

The week-13 campaign (scripts/run_b7_pil.py) and two repeats with seed
offsets 100 and 200, for B7 alone and B7 with the rule monitor. Writes
docs/week14-b7-pil-repeats.json: each draw, and the three pooled.

    PYTHONPATH="src:." python3 scripts/report_b7_pil_repeats.py
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.report_b7_pil import summarise

KEYS = ("detected_in_time", "fault_runs", "worst_delay_s", "median_delay_s",
        "alarms_before_onset", "released_early",
        "still_flagged_in_last_second", "worst_peak_err_mps",
        "median_peak_err_mps", "clean_false_alarms", "clean_hours",
        "late_control_steps", "worst_control_computation_us",
        "max_dropped_frames", "cells_over_dropped_limit")
ARMS = (("B7", "b7", 5), ("B7 + rule monitor", "b7mon", 6))


def main() -> int:
    out = {"provenance": "MEASURED on the board (ESP32-S3); the laptop "
                         "simulates the vehicle and injects the faults. "
                         "Three draws of noise per case.", "arms": {}}
    for label, arm, mode in ARMS:
        files = {"first": f"docs/week13-b7-pil-{arm}.json",
                 "repeat 1": f"docs/week14-b7-pil-{arm}-seed100.json",
                 "repeat 2": f"docs/week14-b7-pil-{arm}-seed200.json"}
        pooled, per = [], {}
        for name, f in files.items():
            runs = json.loads(Path(f).read_text())["runs"]
            if len(runs) != 42 or any(r["speed_est_mode"] != mode
                                      or r["actor_steps"] for r in runs):
                raise SystemExit(f"{f}: incomplete or wrong image")
            per[name] = {k: summarise(runs)[k] for k in KEYS}
            pooled += runs
        s = summarise(pooled)
        out["arms"][label] = {"per_draw": per,
                              "pooled": {k: s[k] for k in KEYS},
                              "by_fault": s["by_fault"]}
        p = out["arms"][label]["pooled"]
        print(f"{label:20s} caught {p['detected_in_time']}/{p['fault_runs']} "
              f"worst delay {p['worst_delay_s']} early {p['released_early']} "
              f"stuck {p['still_flagged_in_last_second']} worst peak "
              f"{p['worst_peak_err_mps']:.2f} median "
              f"{p['median_peak_err_mps']:.2f} clean alarms "
              f"{p['clean_false_alarms']} in {p['clean_hours']:.2f} h late "
              f"{p['late_control_steps']} max dropped "
              f"{p['max_dropped_frames']}")
        for name, v in per.items():
            print(f"    {name:9s} worst peak {v['worst_peak_err_mps']:.2f} "
                  f"median {v['median_peak_err_mps']:.2f} early "
                  f"{v['released_early']} stuck "
                  f"{v['still_flagged_in_last_second']}")
    restored = Path(".claude/night/b7-pil-repeat-restored.json")
    out["board_restored_to"] = (json.loads(restored.read_text())["image"]
                                if restored.exists() else None)
    Path("docs/week14-b7-pil-repeats.json").write_text(
        json.dumps(out, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
