"""Put the three board arms' fault runs into one file with their verdicts.

Reads docs/week13-b7-pil-{b7mon,b7,b6}.json (scripts/run_b7_pil.py) and the
record of what image the board was left holding, and writes
docs/week13-b7-pil.json. Counts and worst cases; nothing is fitted.

    PYTHONPATH="src:." python3 scripts/report_b7_pil.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from evpil.control import sensor_eval as se

ARMS = (("b6", 4, "B6"), ("b7", 5, "B7"), ("b7mon", 6, "B7 + rule monitor"))
DROPPED_LIMIT = 16              # as in the week-12 campaigns


def summarise(runs: list[dict]) -> dict:
    f = [r for r in runs if r["fault"]]
    c = [r for r in runs if not r["fault"]]
    out = {"cells": len(runs), "fault_runs": len(f), "clean_runs": len(c)}
    if f:
        ok = [r["delay_s"] is not None
              and r["delay_s"] <= se.CRITERIA["detect_within_s"] for r in f]
        delays = [r["delay_s"] for r in f if r["delay_s"] is not None]
        fault_steps = int(se.FAULT_S / 0.01)
        out.update({
            "detected_in_time": int(sum(ok)),
            "worst_delay_s": max(delays) if delays else None,
            "median_delay_s": float(np.median(delays)) if delays else None,
            "alarms_before_onset": int(sum(r["alarms_before_onset"]
                                           for r in f)),
            # The flag state is known per 500 ms DIAG interval, so these two
            # are coarser than the simulation's step-exact versions.
            "released_early": int(sum(
                o and r["flagged_steps_in_fault"] < 0.8 * fault_steps
                for o, r in zip(ok, f))),
            "still_flagged_in_last_second": int(sum(
                r["flagged_in_last_second"] > 0 for r in f)),
            "worst_peak_err_mps": float(max(r["peak_err_mps"] for r in f)),
            "median_peak_err_mps": float(np.median(
                [r["peak_err_mps"] for r in f])),
            "by_fault": {
                name: {"runs": len(g),
                       "detected_in_time": int(sum(
                           r["delay_s"] is not None and r["delay_s"] <= 0.5
                           for r in g)),
                       "worst_peak_err_mps": float(max(
                           r["peak_err_mps"] for r in g))}
                for name in sorted({r["fault"] for r in f})
                for g in [[r for r in f if r["fault"] == name]]},
            "by_accel": {
                name: {"runs": len(g),
                       "detected_in_time": int(sum(
                           r["delay_s"] is not None and r["delay_s"] <= 0.5
                           for r in g)),
                       "worst_peak_err_mps": float(max(
                           r["peak_err_mps"] for r in g))}
                for name in sorted({r["accel"] for r in f})
                for g in [[r for r in f if r["accel"] == name]]},
        })
    if c:
        hours = sum(r["steps"] for r in c) * 0.01 / 3600.0
        out.update({
            "clean_hours": hours,
            "clean_false_alarms": int(sum(r["alarms_total"] for r in c)),
            "clean_flagged_share": float(
                sum(r["flagged_steps"] for r in c)
                / sum(r["steps"] for r in c)),
            "clean_tracking_rmse_mps": {r["accel"]: r["tracking_rmse_mps"]
                                        for r in c},
            "clean_equivalent_wh_per_km": {r["accel"]: r["equivalent_wh_per_km"]
                                           for r in c},
        })
    out.update({
        "late_control_steps": int(sum(r["ctrl_late"] for r in runs)),
        "worst_control_computation_us": int(max(r["ctrl_wcet_us"]
                                                for r in runs)),
        "cells_over_dropped_limit": int(sum(
            r["dropped_frames"] > DROPPED_LIMIT for r in runs)),
        "max_dropped_frames": int(max(r["dropped_frames"] for r in runs)),
    })
    return out


def main() -> int:
    arms, modes_ok, late = {}, True, 0
    for key, mode, label in ARMS:
        path = Path(f"docs/week13-b7-pil-{key}.json")
        if not path.exists():
            continue
        d = json.loads(path.read_text())
        runs = d["runs"]
        modes_ok &= all(r["speed_est_mode"] == mode and r["actor_steps"] == 0
                        for r in runs)
        s = summarise(runs)
        late += s["late_control_steps"]
        arms[label] = {"speed_est_mode": mode, "file": str(path), **s}
    restored = Path(".claude/night/b7-pil-restored.json")
    image = (json.loads(restored.read_text()).get("image")
             if restored.exists() and restored.read_text().strip() else None)
    doc = {
        "provenance": "MEASURED on the board (ESP32-S3); the laptop "
                      "simulates the vehicle and injects the faults. One "
                      "run per cell.",
        "cases": "US06 from the registered test split: five named faults, "
                 "two onsets, white and wander acceleration cases, noise "
                 "floor and 10x; two clean cycles",
        "config": se.config_hash(),
        "estimator_mode_verified": bool(modes_ok and arms),
        "late_control_steps": late,
        "board_restored_to": image,
        "arms": arms,
    }
    Path("docs/week13-b7-pil.json").write_text(json.dumps(doc, indent=1) + "\n")
    for label, s in arms.items():
        print(f"{label:20s} cells {s['cells']:3d}  caught "
              f"{s.get('detected_in_time')}/{s['fault_runs']}  worst delay "
              f"{s.get('worst_delay_s')}  early releases "
              f"{s.get('released_early')}  stuck {s.get('still_flagged_in_last_second')}"
              f"  worst peak {s.get('worst_peak_err_mps')}  clean alarms "
              f"{s.get('clean_false_alarms')}  late {s['late_control_steps']}"
              f"  wcet {s['worst_control_computation_us']} us")
    print(f"modes verified {doc['estimator_mode_verified']}, board holds "
          f"{image}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
