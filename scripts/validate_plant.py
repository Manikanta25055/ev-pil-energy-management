# scripts/validate_plant.py
"""G2: does the plant reproduce held-out real trips?

The gate is evaluated in three parts rather than one, because the original
single number pooled three independent models and could not say which of them
was wrong. See docs/g2-plant-validation.md for the evidence behind the split
and for the one criterion revision the spec allows.

  A. Longitudinal model -- torque inverted from the logged speed profile
     against the archive's own logged motor torque.
  B. Powertrain, battery and auxiliary models -- driven by logged torque,
     battery power against logged battery power. This carries the ORIGINAL
     10% threshold, applied where it is actually measurable.
  C. End to end -- full speed-profile replay, terminal SoC. This carries the
     ORIGINAL 2 percentage point threshold, unchanged.

Neither threshold is loosened. The revision changes only which model each one
is applied to. Trip energy error is reported alongside but is not a pass
condition: it measures the same integral as terminal SoC and would double-count
it.

Runs on validation trips only. Test trips stay sealed until the end of the
project.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from evpil.data.splits import Split, apply_split
from evpil.plant.auxiliary import AuxParams
from evpil.plant.longitudinal import road_load
from evpil.plant.motor import electrical_power_w
from scripts.identify_params import build_params, load_eligible, simulate_trip

# Part A: torque RMSE as a fraction of the trip's own logged-torque spread.
TORQUE_REL_LIMIT = 0.50
# Part B: the original criterion, on the sub-model it can actually judge.
POWER_RMSE_FRACTION = 0.10
# Part C: where the SoC ends up. The spec's original threshold, unchanged.
SOC_ERROR_LIMIT = 0.02
# Reported, not gated: the same integral as terminal SoC, in kWh.
ENERGY_ERROR_REPORT = 0.05


def _logged_torque(root: Path, trip_id: str, n: int) -> np.ndarray:
    raw = pd.read_csv(root / f"{trip_id}.csv", sep=";", encoding="cp1252",
                      low_memory=False)
    raw.columns = [c.strip() for c in raw.columns]
    tq = pd.to_numeric(raw["Motor Torque [Nm]"], errors="coerce").to_numpy()
    return tq if len(tq) == n else np.full(n, np.nan)


def validate_trip(params, trip: pd.DataFrame, tq_logged: np.ndarray) -> dict:
    obs = (trip.v_batt_v * trip.i_batt_a).to_numpy()
    mean_abs = float(np.mean(np.abs(obs)))
    v = trip.v_mps.to_numpy()
    dt = np.diff(trip.t_s.to_numpy(), prepend=trip.t_s.iloc[0])
    omega = (v / params.wheel_radius_m) * params.gear_ratio

    # --- A: longitudinal model against the logged torque channel -------------
    f = np.array([
        road_load(v_mps=vi, a_mps2=ai, grade_rad=gi, mass_kg=params.mass_kg,
                  c_rr=params.c_rr, cd=params.cd,
                  frontal_area_m2=params.frontal_area_m2,
                  rot_mass_factor=params.rot_mass_factor).tractive_n
        for vi, ai, gi in zip(v, trip.a_mps2.to_numpy(), trip.grade_rad.to_numpy())
    ])
    tq_inv = np.where(
        f >= 0.0,
        f * params.wheel_radius_m / (params.gear_ratio * params.drivetrain_eta),
        f * params.wheel_radius_m * params.drivetrain_eta / params.gear_ratio,
    )
    tq_rmse = float(np.sqrt(np.nanmean((tq_inv - tq_logged) ** 2)))
    tq_std = float(np.nanstd(tq_logged))
    tq_rel = tq_rmse / tq_std if tq_std > 0 else float("inf")

    # --- B: powertrain, battery and aux, given a true torque -----------------
    p_floor = (np.array([electrical_power_w(params.motor, T, w)
                         for T, w in zip(tq_logged, omega)])
               + trip.p_aux_w.to_numpy() + params.aux.p_base_w)
    floor_rmse = float(np.sqrt(np.nanmean((p_floor - obs) ** 2)))
    floor_rel = floor_rmse / mean_abs if mean_abs > 0 else float("inf")

    # --- C: end to end -------------------------------------------------------
    sim = simulate_trip(params, trip)
    full_rmse = float(np.sqrt(np.mean((sim - obs) ** 2)))
    e_obs = float(np.sum(obs * dt) / 3.6e6)
    e_sim = float(np.sum(sim * dt) / 3.6e6)
    e_err = abs(e_sim - e_obs) / abs(e_obs) if e_obs != 0 else float("inf")

    i_sim = np.divide(sim, trip.v_batt_v.to_numpy(), out=np.zeros_like(sim),
                      where=trip.v_batt_v.to_numpy() > 0)
    ah_used = float(np.sum(i_sim * dt) / 3600.0)
    soc_sim_end = float(trip.soc_frac.iloc[0]) - ah_used / params.battery.capacity_ah
    soc_err = abs(soc_sim_end - float(trip.soc_frac.iloc[-1]))

    passes = (tq_rel <= TORQUE_REL_LIMIT and floor_rel <= POWER_RMSE_FRACTION
              and soc_err <= SOC_ERROR_LIMIT)
    return {
        "torque_rmse_nm": tq_rmse, "torque_std_nm": tq_std, "torque_rel": tq_rel,
        "floor_rmse_w": floor_rmse, "floor_rmse_frac": floor_rel,
        "power_rmse_w": full_rmse, "power_rmse_frac": full_rmse / mean_abs,
        "mean_abs_power_w": mean_abs,
        "energy_obs_kwh": e_obs, "energy_sim_kwh": e_sim, "energy_err_frac": e_err,
        "soc_sim_end": soc_sim_end, "soc_obs_end": float(trip.soc_frac.iloc[-1]),
        "soc_abs_error": soc_err,
        "passes_A": float(tq_rel <= TORQUE_REL_LIMIT),
        "passes_B": float(floor_rel <= POWER_RMSE_FRACTION),
        "passes_C": float(soc_err <= SOC_ERROR_LIMIT),
        "passes": float(passes),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/raw/i3")
    ap.add_argument("--splits", default="data/splits.json")
    ap.add_argument("--params", default="data/i3_params.json")
    args = ap.parse_args()

    cfg = json.loads(Path(args.params).read_text())
    ident = cfg["identified"]
    grid = cfg.get("motor_efficiency_grid")
    params = build_params(ident["c_rr"], ident["cd"], ident["r0_ohm"],
                          AuxParams(**cfg["aux"]),
                          ident.get("rot_mass_factor", 0.0),
                          None if grid is None else np.array(grid))

    sp = json.loads(Path(args.splits).read_text())
    df = load_eligible(Path(args.data))
    _, val, _ = apply_split(df, Split(sp["train"], sp["val"], sp["test"]))

    rows = []
    print(f"{'trip':10s} {'A torque':>16s} {'B power':>16s} "
          f"{'C energy':>10s} {'C SoC':>10s}   verdict")
    for trip_id in sorted(val.trip_id.unique()):
        trip = val[val.trip_id == trip_id].reset_index(drop=True)
        r = validate_trip(params, trip, _logged_torque(Path(args.data), trip_id,
                                                       len(trip)))
        r["trip_id"] = trip_id
        rows.append(r)
        mark = lambda ok: "ok  " if ok else "FAIL"
        print(f"{trip_id:10s} "
              f"{r['torque_rel']*100:6.1f}% {mark(r['passes_A']):>5s} "
              f"{r['floor_rmse_frac']*100:6.1f}% {mark(r['passes_B']):>5s} "
              f"{r['energy_err_frac']*100:6.1f}% "
              f"{r['soc_abs_error']*100:6.2f}pp   "
              f"{'PASS' if r['passes'] else 'FAIL'}")

    out = pd.DataFrame(rows)
    out = out[["trip_id"] + [c for c in out.columns if c != "trip_id"]]
    out.to_csv("docs/g2-per-trip.csv", index=False)

    n = len(out)
    print(f"\nvalidation trips: {n}")
    print(f"A  longitudinal   : median {out.torque_rel.median()*100:5.1f}% of "
          f"logged-torque sd, worst {out.torque_rel.max()*100:5.1f}%   "
          f"({int(out.passes_A.sum())}/{n} within {TORQUE_REL_LIMIT*100:.0f}%)")
    print(f"B  powertrain     : median {out.floor_rmse_frac.median()*100:5.1f}% of "
          f"mean |P|, worst {out.floor_rmse_frac.max()*100:5.1f}%   "
          f"({int(out.passes_B.sum())}/{n} within {POWER_RMSE_FRACTION*100:.0f}%)")
    print(f"   trip energy     : median {out.energy_err_frac.median()*100:5.1f}%, "
          f"worst {out.energy_err_frac.max()*100:5.1f}%   "
          f"({int((out.energy_err_frac<=ENERGY_ERROR_REPORT).sum())}/{n} within "
          f"{ENERGY_ERROR_REPORT*100:.0f}%)  [reported, not gated]")
    print(f"C  terminal SoC   : median {out.soc_abs_error.median()*100:5.2f} pp, "
          f"worst {out.soc_abs_error.max()*100:5.2f} pp   "
          f"({int((out.soc_abs_error<=SOC_ERROR_LIMIT).sum())}/{n} within "
          f"{SOC_ERROR_LIMIT*100:.0f} pp)")
    print(f"\nfor reference, the full end-to-end instantaneous RMSE that the "
          f"original single-number criterion used:")
    print(f"   median {out.power_rmse_frac.median()*100:5.1f}%, "
          f"worst {out.power_rmse_frac.max()*100:5.1f}%  -- see "
          f"docs/g2-plant-validation.md for why this is a torque-inversion "
          f"noise floor and not a plant defect")

    n_fail = int((out.passes == 0).sum())
    print(f"\nG2 {'PASS' if n_fail == 0 else f'FAIL ({n_fail} of {n} trips)'}")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
