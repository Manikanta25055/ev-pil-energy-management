"""Does a real acceleration channel agree with speed well enough for B6?

The fault detector B6 trusts measured acceleration: it dead-reckons a speed
from it and calls a fault when the speed reading departs from that. In the
simulation the acceleration channel is the vehicle's true acceleration plus
white noise. A real one carries an offset, and reads gravity along a slope.

The BMW i3 archive logs `Longitudinal Acceleration [m/s^2]` beside speed, at
10 Hz. The project's loader discards that column and derives acceleration from
speed, for exactly the reason this script looks at: the two do not agree. Here
the logged column is kept and compared with the speed it should explain.

Two things are computed per trip, with no fault anywhere in the data:

  1. The disagreement itself: logged acceleration minus the acceleration the
     speed implies, its mean (an offset) and its relation to road slope.
  2. What B6 would do with it: the detector's dead reckoning and mean test,
     run on the logged pair at the logs' own 10 Hz, counting the times the
     flag goes up and the share of the drive spent flagged.

B6 runs at 100 Hz on the board and its window is 20 samples. At 10 Hz the same
20 samples span two seconds, so the count here is not the count the firmware
would give on these trips; it is evidence about whether the assumption holds.
The offset in (1) does not depend on the rate.

Reads logged data only. No simulation, no board.

    PYTHONPATH="src:." python3 scripts/check_accel_channel.py
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from evpil.control.speed_estimators import FaultSettings, JitterMeter

G = 9.81
TAU_S = 2.0


def detector_on_logs(v: np.ndarray, a: np.ndarray, dt: float) -> dict:
    """B6's dead reckoning and three tests, on a logged speed and
    acceleration. The Kalman estimate is left out: the tests do not use it."""
    s = FaultSettings()
    meter = JitterMeter()
    r2 = 0.02 ** 2
    v_dr = float(v[0])
    last = float(v[0])
    gaps: list[float] = []
    pulls: list[float] = []
    gross = same = quiet = 0
    flagged = False
    alarms: list[int] = []
    tests: list[int] = []
    flagged_steps = 0
    for k in range(1, len(v)):
        z = float(v[k])
        dr = v_dr + float(a[k]) * dt
        gap = z - dr
        scale = math.sqrt(r2)
        gross = gross + 1 if abs(gap) > max(s.gross_mps, 8.0 * scale) else 0
        same = same + 1 if z == last else 0
        last = z
        gaps.append(gap)
        pulls.append(0.0)
        if len(gaps) > s.window:
            gaps.pop(0)
            pulls.pop(0)
        test = 0
        if gross >= s.gross_count:
            test = 1
        elif same >= s.frozen_count and meter.sigma_mps > 1e-4:
            test = 2
        elif len(gaps) == s.window:
            m = sum(gaps) / s.window
            var = sum((g - m) ** 2 for g in gaps) / (s.window - 1)
            if abs(m) > s.t_limit * math.sqrt(max(var, r2) / s.window):
                test = 3
        if not flagged and test:
            flagged, quiet = True, 0
            alarms.append(k)
            tests.append(test)
            dr -= sum(pulls[:-1])
        elif flagged:
            band = max(s.clear_band_mps, 4.0 * scale)
            ok = abs(gap) < band and same < s.frozen_count and gross == 0
            quiet = quiet + 1 if ok else 0
            if quiet >= s.clear_count:
                flagged = False
                dr += sum(gaps) / len(gaps)
                gaps.clear()
                pulls.clear()
        if flagged:
            flagged_steps += 1
            v_dr = dr
            continue
        if abs(gap) > max(s.gross_mps, 8.0 * scale):
            v_dr = dr
            continue
        if pulls:
            pulls[-1] = (dt / TAU_S) * gap
        v_dr = dr + (dt / TAU_S) * gap
        meter.push(z)
        if meter.new_block:
            r2 = max(meter.sigma_mps ** 2, 0.005 ** 2)
    return {"alarms": len(alarms), "flagged_share": flagged_steps / len(v),
            "tests": {str(t): tests.count(t) for t in (1, 2, 3)}}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="data/raw/i3")
    ap.add_argument("--out-json", default="docs/week12-accel-channel-check.json")
    args = ap.parse_args()

    rows = []
    for path in sorted(Path(args.raw).glob("Trip*.csv")):
        df = pd.read_csv(path, sep=";", encoding="cp1252")
        df.columns = [c.replace("]]]", "]").strip() for c in df.columns]
        need = ("Time [s]", "Velocity [km/h]", "Elevation [m]",
                "Longitudinal Acceleration [m/s^2]")
        if any(c not in df.columns for c in need):
            continue
        df = df[list(need)].apply(pd.to_numeric, errors="coerce").dropna()
        t = df["Time [s]"].to_numpy()
        v = df["Velocity [km/h]"].to_numpy() / 3.6
        a = df["Longitudinal Acceleration [m/s^2]"].to_numpy()
        h = df["Elevation [m]"].to_numpy()
        if len(t) < 600:
            continue
        dt = float(np.median(np.diff(t)))
        a_kin = np.gradient(v, t)
        moving = v > 2.0
        diff = (a - a_kin)[moving]
        # Slope from elevation over a five-second span; the logged elevation
        # moves in whole metres and is useless over shorter ones.
        span = max(1, int(round(5.0 / dt)))
        dist = np.cumsum(v * dt)
        dh = h[span:] - h[:-span]
        dd = dist[span:] - dist[:-span]
        ok = dd > 5.0
        slope = np.zeros(len(h))
        slope[span:][ok] = dh[ok] / dd[ok]
        g_along = G * slope[moving]
        # Smooth both to five seconds before relating them: the comparison is
        # about the slow component, which is what dead reckoning integrates.
        k = np.ones(span) / span
        d_s = np.convolve(diff, k, mode="same")
        g_s = np.convolve(g_along, k, mode="same")
        corr = float(np.corrcoef(d_s, g_s)[0, 1]) if np.std(g_s) > 0 else float("nan")
        fit = float(np.polyfit(g_s, d_s, 1)[0]) if np.std(g_s) > 0 else float("nan")
        det = detector_on_logs(v, a, dt)
        rows.append({
            "trip": path.stem, "minutes": float((t[-1] - t[0]) / 60.0),
            "dt_s": dt,
            "offset_mps2": float(np.mean(diff)),
            "disagreement_sd_mps2": float(np.std(diff)),
            "slow_disagreement_sd_mps2": float(np.std(d_s)),
            "corr_with_slope_gravity": corr,
            "fit_against_slope_gravity": fit,
            "steady_gap_from_offset_mps": float(abs(np.mean(diff)) * TAU_S),
            **det,
        })
        print(f"{path.stem:8s} {rows[-1]['minutes']:5.1f} min  offset "
              f"{rows[-1]['offset_mps2']:+.3f} m/s2  slow sd "
              f"{rows[-1]['slow_disagreement_sd_mps2']:.3f}  corr with slope "
              f"{corr:+.2f}  alarms {det['alarms']:3d}  flagged "
              f"{100 * det['flagged_share']:5.1f}%", flush=True)

    hours = sum(r["minutes"] for r in rows) / 60.0
    alarms = sum(r["alarms"] for r in rows)
    offs = np.array([r["offset_mps2"] for r in rows])
    summary = {
        "trips": len(rows), "hours": hours,
        "offset_mps2_median_abs": float(np.median(np.abs(offs))),
        "offset_mps2_worst_abs": float(np.max(np.abs(offs))),
        "slow_disagreement_sd_mps2_median": float(np.median(
            [r["slow_disagreement_sd_mps2"] for r in rows])),
        "corr_with_slope_gravity_median": float(np.nanmedian(
            [r["corr_with_slope_gravity"] for r in rows])),
        "fit_against_slope_gravity_median": float(np.nanmedian(
            [r["fit_against_slope_gravity"] for r in rows])),
        "alarms": alarms, "alarms_per_hour": alarms / hours,
        "flagged_share": float(np.average(
            [r["flagged_share"] for r in rows],
            weights=[r["minutes"] for r in rows])),
        "trips_with_no_alarm": int(sum(r["alarms"] == 0 for r in rows)),
        "mean_test_threshold_at_floor_mps": 8.0 * 0.02 / math.sqrt(20),
    }
    Path(args.out_json).write_text(json.dumps({
        "provenance": "logged BMW i3 trips, 10 Hz; no fault in the data; "
                      "detector run at the logs' rate, not the firmware's",
        "tau_s": TAU_S, "summary": summary, "rows": rows}, indent=1) + "\n")
    print()
    for k, x in summary.items():
        print(f"  {k}: {x}")
    print(f"wrote {args.out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
