"""Does a classical detector already meet the speed-sensor fault criteria?

The design's section 7.3 asks that a stuck, dropped or offset speed reading
be flagged within 0.5 s, with fewer than one false alarm per hour of clean
driving. This runs the classical arm, B4 (the adaptive Kalman estimate with an
innovation test on top), against that, on US06, eight onsets per fault, at the
noise floor and at ten times it. A drifting offset is run as well; it is not
one of the faults the criteria name and is reported separately.

The same faults are run through B3a, the estimate with no detector, so the
table shows what a missed fault costs and what catching it buys.

One process, on purpose: the board is in use and a loaded laptop disturbs it.
SIMULATED on the laptop.

    PYTHONPATH="src:." python3 scripts/run_fault_arms.py
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import replace
from pathlib import Path

import numpy as np

from evpil.control.cycles import Cycle, load_cycle
from evpil.control.rule_ems import RuleParams, rule_action
from evpil.control.sim import simulate
from evpil.control.speed_estimators import (
    FaultTolerantKalman, KalmanSpeed, KinematicFaultKalman, SpeedFault,
)
from scripts.identify_params import params_from_json

FLOOR = 0.02
FAULTS = (            # (label, kind, magnitude, named in the criteria)
    ("stuck",      "stuck",   0.0, True),
    ("dropout",    "dropout", 0.0, True),
    ("bias +0.5",  "bias",    0.5, True),
    ("bias -0.5",  "bias",   -0.5, True),
    ("bias +3.0",  "bias",    3.0, True),
    ("drift 0.5/s", "drift",  0.5, False),
)
ONSETS_S = tuple(float(x) for x in np.linspace(16.0, 580.0, 8))
FAULT_S = 5.0          # then the sensor comes back
TAIL_S = 8.0           # simulated after the fault ends
CLEAN = (             # (label, cycle, noise multiple or "step", mass factor)
    ("udds, floor",       "udds",  1.0,    1.0),
    ("hwfet, floor",      "hwfet", 1.0,    1.0),
    ("us06, floor",       "us06",  1.0,    1.0),
    ("us06, 10x",         "us06",  10.0,   1.0),
    ("us06, noise step",  "us06",  "step", 1.0),
    ("us06, mass +10%",   "us06",  1.0,    1.1),
)
SEEDS = (0, 1, 2, 3, 4)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tuned", default="docs/week11-speed-arms-tuned.json")
    ap.add_argument("--out-json", default="docs/week11-fault-arms.json")
    ap.add_argument("--kinematic", action="store_true",
                    help="B6: detect from speed against measured acceleration; "
                         "faults are then also run on a car 10%% heavier")
    ap.add_argument("--disturbance", action="store_true",
                    help="give both arms the unknown-acceleration state (B5)")
    args = ap.parse_args()

    nominal = params_from_json("data/i3_params.json")
    tuned = json.loads(Path(args.tuned).read_text())
    q = tuned["b3a"]["q_mps"]
    q_d = tuned["b5"]["q_d_mps2"] if (args.disturbance or args.kinematic) else 0.0
    A_FLOOR = 0.05          # NOISE_SIGMA["a_mps2"] in evpil.control.scenarios

    def detector():
        if args.kinematic:
            return KinematicFaultKalman(nominal, q_mps=q, q_d_mps2=q_d)
        return FaultTolerantKalman(nominal, q_mps=q, q_d_mps2=q_d)

    masses = (1.0, 1.1) if args.kinematic else (1.0,)
    rules = RuleParams()
    policy = lambda o: rule_action(rules, soc_frac=o.soc_frac, v_mps=o.v_mps)
    us06 = load_cycle("us06")
    t0 = time.time()

    fault_rows = []
    for label, kind, mag, named in FAULTS:
      for mass in masses:
        plant_f = replace(nominal, mass_kg=nominal.mass_kg * mass)
        for mult in (1.0, 10.0):
            for k, onset in enumerate(ONSETS_S):
                n = int((onset + FAULT_S + TAIL_S) / us06.dt_s)
                n = min(n, len(us06.v_ref_mps))
                cyc = Cycle(name="us06", dt_s=us06.dt_s,
                            v_ref_mps=us06.v_ref_mps[:n],
                            grade_rad=us06.grade_rad[:n])
                a = int(onset / cyc.dt_s)
                b = min(n, int((onset + FAULT_S) / cyc.dt_s))
                row = {"fault": label, "named": named, "noise_x": mult,
                       "onset_s": onset, "mass": mass}
                for arm in ("B4", "B3a"):
                    est = (detector() if arm == "B4"
                           else KalmanSpeed(nominal, q_mps=q, r_mps=FLOOR,
                                            adaptive=True, q_d_mps2=q_d))
                    r = simulate(plant_f, cyc, policy, ff_params=nominal,
                                 accel_noise_mps2=mult * A_FLOOR,
                                 speed_noise_mps=mult * FLOOR, seed=k,
                                 speed_estimator=est, keep_trace=True,
                                 speed_fault=SpeedFault(kind, onset, mag,
                                                        duration_s=FAULT_S))
                    err = np.abs(r.trace.v_ref_mps - r.trace.v_mps)
                    row[f"{arm}_peak_err_mps"] = float(err[a:].max())
                    if arm == "B4":
                        before = [s for s in est.alarm_steps if s < a]
                        after = [s for s in est.alarm_steps if s >= a]
                        row["false_alarms_before"] = len(before)
                        row["delay_s"] = ((after[0] - a) * cyc.dt_s
                                          if after else None)
                        row["flag_dropped_after"] = not est.flag_history[-1]
                        row["v_ref_at_onset_mps"] = float(cyc.v_ref_mps[a])
                fault_rows.append(row)
            sub = [r for r in fault_rows if r["fault"] == label
                   and r["noise_x"] == mult and r["mass"] == mass]
            d = [r["delay_s"] for r in sub]
            print(f"{label:12s} m{mass:.1f} {mult:4.0f}x  delays "
                  f"{[None if x is None else round(x, 2) for x in d]}  "
                  f"peak err B4 {max(r['B4_peak_err_mps'] for r in sub):.2f} "
                  f"B3a {max(r['B3a_peak_err_mps'] for r in sub):.2f}  "
                  f"{time.time() - t0:4.0f} s", flush=True)

    clean_rows = []
    for label, cyc_name, mult, mass in CLEAN:
        cyc = load_cycle(cyc_name)
        n = len(cyc.v_ref_mps)
        if mult == "step":
            t = np.arange(n) * cyc.dt_s
            noise = np.where((t >= 200.0) & (t < 400.0), 10 * FLOOR, FLOOR)
        else:
            noise = mult * FLOOR
        plant = replace(nominal, mass_kg=nominal.mass_kg * mass)
        for seed in SEEDS:
            est = detector()
            r = simulate(plant, cyc, policy, ff_params=nominal,
                         accel_noise_mps2=(10 * A_FLOOR if mult == 10.0
                                           else A_FLOOR),
                         speed_noise_mps=noise, seed=seed, speed_estimator=est)
            clean_rows.append({
                "scenario": label, "seed": seed, "hours": n * cyc.dt_s / 3600.0,
                "false_alarms": len(est.alarm_steps),
                "alarm_times_s": [s * cyc.dt_s for s in est.alarm_steps],
                "flagged_fraction": float(np.mean(est.flag_history)),
                "equivalent_wh_per_km": r.equivalent_wh_per_km,
                "tracking_rmse_mps": r.tracking_rmse_mps,
            })
        sub = [r for r in clean_rows if r["scenario"] == label]
        print(f"{label:18s} false alarms {sum(r['false_alarms'] for r in sub)}"
              f" in {sum(r['hours'] for r in sub):.2f} h  "
              f"{time.time() - t0:4.0f} s", flush=True)

    named = [r for r in fault_rows if r["named"]]
    floor_clean = [r for r in clean_rows if r["scenario"].endswith("floor")]
    hours = sum(r["hours"] for r in floor_clean)
    alarms = sum(r["false_alarms"] for r in floor_clean)
    delays = [r["delay_s"] for r in named]
    verdict = {
        "named faults run": len(named),
        "named faults missed": sum(d is None for d in delays),
        "named faults flagged later than 0.5 s":
            sum(d is not None and d > 0.5 for d in delays),
        "worst delay, s": max((d for d in delays if d is not None), default=None),
        "every named fault flagged within 0.5 s":
            all(d is not None and d <= 0.5 for d in delays),
        "clean hours at the noise floor": hours,
        "false alarms in them": alarms,
        "false alarms per hour": alarms / hours,
        "fewer than one false alarm per hour": alarms / hours < 1.0,
        "false alarms before any fault onset":
            sum(r["false_alarms_before"] for r in fault_rows),
    }
    heavy = [r for r in clean_rows if "mass" in r["scenario"]]
    verdict["false alarms per hour, car 10% heavier than the model"] = (
        sum(r["false_alarms"] for r in heavy) / sum(r["hours"] for r in heavy))
    verdict["tracking RMSE, car 10% heavier, m/s"] = float(
        np.mean([r["tracking_rmse_mps"] for r in heavy]))
    verdict["worst peak tracking error through a named fault, m/s"] = max(
        r["B4_peak_err_mps"] for r in named)
    verdict["named faults where the flag never dropped after the sensor came back"] = sum(
        not r["flag_dropped_after"] for r in named)
    verdict["meets both fault criteria"] = bool(
        verdict["every named fault flagged within 0.5 s"]
        and verdict["fewer than one false alarm per hour"])
    Path(args.out_json).write_text(json.dumps({
        "provenance": "SIMULATED on the laptop; no board involved",
        "q_mps": q, "q_d_mps2": q_d, "onsets_s": ONSETS_S, "fault_s": FAULT_S,
        "faults": fault_rows, "clean": clean_rows, "verdict": verdict,
    }, indent=1))
    print()
    for k, v in verdict.items():
        print(f"  {k}: {v}")
    print(f"wrote {args.out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
