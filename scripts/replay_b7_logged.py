"""Does the bias-aware detector (B7) stay quiet on real, healthy trips?

The first detector (B6) was replayed on the 70 logged BMW i3 trips by
scripts/check_accel_channel.py and was flagged 99% of the time: the logged
acceleration carries a slow error that B6's dead reckoning cannot absorb. B7
was built to live with that error, but it was only ever tested on simulated
channels. This replays B7, with its tuned settings unchanged, on the same
logged speed and acceleration. No fault is in the data, so every alarm is a
false alarm.

Two passes, fixed in docs/2026-10-14-measurement-plan.md before the run:

  10 Hz    the logs' own rate, as the B6 replay used (primary)
  100 Hz   speed and acceleration interpolated, with the campaign's speed
           noise floor added (seed 0) (secondary)

Logged speed repeats exactly while the car stands still, which a sensor with
noise never does, so frozen-test alarms below 0.5 m/s are counted apart.

Reads logged data only. No board.

    PYTHONPATH="src:." python3 scripts/replay_b7_logged.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from evpil.control.scenarios import NOISE_SIGMA
from scripts.identify_params import params_from_json
from scripts.sensor_arms import make_arm

STANDSTILL_MPS = 0.5
TEST_NAMES = {1: "gross", 2: "frozen", 3: "mean", 4: "step"}


def load_trips(raw: Path):
    for path in sorted(raw.glob("Trip*.csv")):
        df = pd.read_csv(path, sep=";", encoding="cp1252")
        df.columns = [c.replace("]]]", "]").strip() for c in df.columns]
        need = ("Time [s]", "Velocity [km/h]",
                "Longitudinal Acceleration [m/s^2]")
        if any(c not in df.columns for c in need):
            continue
        df = df[list(need)].apply(pd.to_numeric, errors="coerce").dropna()
        t = df["Time [s]"].to_numpy()
        if len(t) < 600:
            continue
        yield (path.stem, t, df["Velocity [km/h]"].to_numpy() / 3.6,
               df["Longitudinal Acceleration [m/s^2]"].to_numpy())


def run_detector(nominal, q, q_d, v, a, dt):
    det = make_arm("b7", nominal, q, q_d)
    flagged = 0
    for k in range(len(v)):
        det.step(v_meas_mps=float(v[k]), torque_prev_nm=0.0, grade_rad=0.0,
                 dt_s=dt, a_meas_mps2=float(a[k]))
        flagged += bool(det.flagged)
    counted = standstill_frozen = 0
    by_test = {name: 0 for name in TEST_NAMES.values()}
    for step, test in zip(det.alarm_steps, det.alarm_tests):
        by_test[TEST_NAMES[test]] += 1
        if test == 2 and abs(float(v[step])) < STANDSTILL_MPS:
            standstill_frozen += 1
        else:
            counted += 1
    return {"alarms_counted": counted,
            "frozen_at_standstill": standstill_frozen,
            "by_test": by_test, "flagged_share": flagged / len(v)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="data/raw/i3")
    ap.add_argument("--out-json",
                    default="docs/2026-10-14-bias-aware-logged-replay.json")
    args = ap.parse_args()

    nominal = params_from_json("data/i3_params.json")
    tuned = json.loads(Path("docs/week11-speed-arms-tuned.json").read_text())
    q, q_d = tuned["b3a"]["q_mps"], tuned["b5"]["q_d_mps2"]
    rng = np.random.default_rng(0)

    rows = []
    for name, t, v, a in load_trips(Path(args.raw)):
        dt10 = float(np.median(np.diff(t)))
        r10 = run_detector(nominal, q, q_d, v, a, dt10)
        t100 = np.arange(t[0], t[-1], 0.01)
        v100 = np.interp(t100, t, v) + rng.normal(0.0, NOISE_SIGMA["v_mps"],
                                                  len(t100))
        a100 = np.interp(t100, t, a)
        r100 = run_detector(nominal, q, q_d, v100, a100, 0.01)
        minutes = float((t[-1] - t[0]) / 60.0)
        rows.append({"trip": name, "minutes": minutes, "dt_s": dt10,
                     "hz10": r10, "hz100": r100})
        print(f"{name:8s} {minutes:5.1f} min  10 Hz: {r10['alarms_counted']:3d}"
              f" alarms ({r10['frozen_at_standstill']} frozen at rest), "
              f"flagged {100 * r10['flagged_share']:5.1f}%   100 Hz: "
              f"{r100['alarms_counted']:3d} alarms, flagged "
              f"{100 * r100['flagged_share']:5.1f}%", flush=True)

    hours = sum(r["minutes"] for r in rows) / 60.0
    summary = {"trips": len(rows), "hours": hours}
    for key in ("hz10", "hz100"):
        counted = sum(r[key]["alarms_counted"] for r in rows)
        by_test = {n: sum(r[key]["by_test"][n] for r in rows)
                   for n in TEST_NAMES.values()}
        summary[key] = {
            "alarms_counted": counted,
            "alarms_per_hour": counted / hours,
            "frozen_at_standstill": sum(r[key]["frozen_at_standstill"]
                                        for r in rows),
            "by_test": by_test,
            "flagged_share": float(np.average(
                [r[key]["flagged_share"] for r in rows],
                weights=[r["minutes"] for r in rows])),
            "trips_with_no_counted_alarm": int(sum(
                r[key]["alarms_counted"] == 0 for r in rows)),
            "meets_registered_limit": counted / hours < 1.0,
        }
    Path(args.out_json).write_text(json.dumps({
        "provenance": "logged BMW i3 trips, no fault in the data; B7 with "
                      "tuned default settings; plan docs/2026-10-14-"
                      "measurement-plan.md item H2",
        "standstill_mps": STANDSTILL_MPS, "summary": summary,
        "rows": rows}, indent=1) + "\n")
    print(json.dumps(summary, indent=1))
    print(f"wrote {args.out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
