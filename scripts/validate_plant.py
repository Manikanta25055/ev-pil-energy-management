# scripts/validate_plant.py
"""G2: does the plant reproduce held-out real trips?

Pass criterion, from spec section 6.1: battery-power RMSE at most 10% of the
trip's mean absolute power, and terminal SoC error at most 2 percentage points,
on every validation trip.

Runs on validation trips only. Test trips stay sealed until the end of the
project.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from evpil.data.i3_loader import load_all_trips
from evpil.data.splits import Split, apply_split
from evpil.plant.auxiliary import AuxParams
from scripts.identify_params import MAPPING, build_params, simulate_trip

POWER_RMSE_FRACTION = 0.10      # of mean absolute power
SOC_ERROR_LIMIT = 0.02          # 2 percentage points


def validate_trip(params, trip: pd.DataFrame) -> dict[str, float]:
    sim_p = simulate_trip(params, trip)
    obs_p = (trip.v_batt_v * trip.i_batt_a).to_numpy()

    rmse = float(np.sqrt(np.mean((sim_p - obs_p) ** 2)))
    mean_abs = float(np.mean(np.abs(obs_p)))
    rel = rmse / mean_abs if mean_abs > 0 else float("inf")

    # Integrate simulated current to get terminal SoC, and compare with logged.
    dt = np.diff(trip.t_s.to_numpy(), prepend=trip.t_s.iloc[0])
    i_sim = np.divide(sim_p, trip.v_batt_v.to_numpy(),
                      out=np.zeros_like(sim_p),
                      where=trip.v_batt_v.to_numpy() > 0)
    ah_used = float(np.sum(i_sim * dt) / 3600.0)
    soc_sim_end = float(trip.soc_frac.iloc[0]) - ah_used / params.battery.capacity_ah
    soc_err = abs(soc_sim_end - float(trip.soc_frac.iloc[-1]))

    return {
        "power_rmse_w": rmse,
        "mean_abs_power_w": mean_abs,
        "power_rmse_frac": rel,
        "soc_sim_end": soc_sim_end,
        "soc_obs_end": float(trip.soc_frac.iloc[-1]),
        "soc_abs_error": soc_err,
        "passes": float(rel <= POWER_RMSE_FRACTION and soc_err <= SOC_ERROR_LIMIT),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/raw/i3")
    ap.add_argument("--splits", default="data/splits.json")
    ap.add_argument("--params", default="data/i3_params.json")
    args = ap.parse_args()

    cfg = json.loads(Path(args.params).read_text())
    aux = AuxParams(**cfg["aux"])
    params = build_params(cfg["identified"]["c_rr"], cfg["identified"]["cd"],
                          cfg["identified"]["r0_ohm"], aux)

    sp = json.loads(Path(args.splits).read_text())
    df = load_all_trips(Path(args.data), MAPPING)
    _, val, _ = apply_split(df, Split(sp["train"], sp["val"], sp["test"]))

    rows = []
    for trip_id in sorted(val.trip_id.unique()):
        trip = val[val.trip_id == trip_id].reset_index(drop=True)
        r = validate_trip(params, trip)
        r["trip_id"] = trip_id
        rows.append(r)
        print(f"{trip_id:20s} rmse={r['power_rmse_w']:9.1f} W "
              f"({r['power_rmse_frac']*100:5.1f}%)  "
              f"soc_err={r['soc_abs_error']*100:5.2f} pp  "
              f"{'PASS' if r['passes'] else 'FAIL'}")

    out = pd.DataFrame(rows)
    out.to_csv("docs/g2-per-trip.csv", index=False)

    n_fail = int((out.passes == 0).sum())
    print(f"\nvalidation trips: {len(out)}")
    print(f"median power RMSE: {out.power_rmse_frac.median()*100:.1f}%")
    print(f"worst  power RMSE: {out.power_rmse_frac.max()*100:.1f}%")
    print(f"worst  SoC error : {out.soc_abs_error.max()*100:.2f} pp")
    print(f"\nG2 {'PASS' if n_fail == 0 else f'FAIL ({n_fail} trips)'}")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
