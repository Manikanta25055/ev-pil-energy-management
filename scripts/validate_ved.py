# scripts/validate_ved.py
"""Cross-dataset generalisation: run the i3-identified plant against VED.

G2 showed the plant reproduces held-out trips from the vehicle it was
identified on. That answers "does it fit?". This answers "does it transfer?",
which is the question a plant is actually for, since Phase 3 trains a policy
inside it.

Three arms, so that a failure can be attributed instead of merely observed:

  A  TRANSFER          i3-identified c_rr, cd, rot_mass_factor, r0 and
                       efficiency map, on the Leaf's published geometry and
                       measured battery. Everything under test at once.
  B  MEASURED CHASSIS  the Leaf's own coastdown road load from the Idaho
                       National Laboratory report, keeping the i3's
                       efficiency map and rotational mass. Isolates whether
                       the POWERTRAIN knowledge transfers, given a chassis
                       that is right.
  C  RE-IDENTIFIED     c_rr, cd, r0 and rot fitted on VED training trips.
                       The ceiling: what is achievable in-domain, and
                       therefore how much of any error in A and B is the
                       vehicle differing rather than the method failing.

Reported on energy and terminal SoC. G2 established that instantaneous power
RMSE under speed-profile replay is dominated by torque-inversion noise, and
VED logs no motor torque, so that decomposition is unavailable here and the
instantaneous figure is printed for reference only.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import least_squares

from evpil.data.splits import Split, apply_split, make_trip_splits
from evpil.plant.auxiliary import AuxParams, fit_auxiliary
from evpil.plant.leaf import (
    MEASURED_C_RR, MEASURED_CD, MEASURED_R0_OHM, build_leaf,
)
from scripts.identify_params import simulate_trip

ENERGY_REPORT = 0.05
SOC_LIMIT = 0.02


def measure_base_load(train: pd.DataFrame, min_samples: int = 200) -> float:
    """The unlogged 12 V draw, from stationary samples, as done for the i3."""
    per_trip = []
    for _, t in train.groupby("trip_id"):
        rest = t[t.v_mps < 0.05]
        if len(rest) < min_samples:
            continue
        p = (rest.v_batt_v * rest.i_batt_a).to_numpy()
        per_trip.append(float(np.median(p - rest.p_aux_w.to_numpy())))
    return float(np.median(per_trip)) if per_trip else 0.0


def noise_floor(trips: list[pd.DataFrame]) -> float:
    """Best-possible instantaneous RMSE, as a percentage of mean |P|.

    Each trip's observed power is fitted by unconstrained least squares onto
    the road-load basis functions plus the logged auxiliary load. The
    coefficients are free to be unphysical, so no model built from these
    signals can do better. What is left over is what the input signals cannot
    explain, whatever the parameters.
    """
    from evpil.plant.leaf import FRONTAL_AREA_M2, MASS_KG
    out = []
    for t in trips:
        v = t.v_mps.to_numpy()
        obs = (t.v_batt_v * t.i_batt_a).to_numpy()
        mabs = float(np.mean(np.abs(obs)))
        if mabs < 100.0:
            continue
        sgn = np.sign(v)
        X = np.column_stack([
            MASS_KG * 9.81 * sgn * v,
            0.5 * 1.2 * FRONTAL_AREA_M2 * v * v * sgn * v,
            MASS_KG * t.a_mps2.to_numpy() * v,
            MASS_KG * 9.81 * np.sin(t.grade_rad.to_numpy()) * v,
            t.p_aux_w.to_numpy(), np.ones_like(v)])
        m = np.isfinite(X).all(axis=1)
        beta, *_ = np.linalg.lstsq(X[m], obs[m], rcond=None)
        out.append(100.0 * float(np.sqrt(np.mean((obs[m] - X[m] @ beta) ** 2))) / mabs)
    return float(np.median(out)) if out else float("nan")


def score(params, trips: list[pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for t in trips:
        sim = simulate_trip(params, t)
        obs = (t.v_batt_v * t.i_batt_a).to_numpy()
        dt = np.diff(t.t_s.to_numpy(), prepend=t.t_s.iloc[0])
        mabs = float(np.mean(np.abs(obs)))
        e_o = float(np.sum(obs * dt) / 3.6e6)
        e_s = float(np.sum(sim * dt) / 3.6e6)
        i_sim = np.divide(sim, t.v_batt_v.to_numpy(), out=np.zeros_like(sim),
                          where=t.v_batt_v.to_numpy() > 0)
        ah = float(np.sum(i_sim * dt) / 3600.0)
        soc_end = float(t.soc_frac.iloc[0]) - ah / params.battery.capacity_ah
        rows.append(dict(
            trip_id=t.trip_id.iloc[0],
            km=float(np.sum(t.v_mps.to_numpy() * dt) / 1000.0),
            oat=float(t.t_ambient_c.mean()),
            energy_obs_kwh=e_o, energy_sim_kwh=e_s,
            energy_err=abs(e_s - e_o) / abs(e_o) if e_o else np.nan,
            energy_signed=(e_s - e_o) / e_o if e_o else np.nan,
            soc_abs_error=abs(soc_end - float(t.soc_frac.iloc[-1])),
            rmse_frac=float(np.sqrt(np.mean((sim - obs) ** 2))) / mabs,
        ))
    return pd.DataFrame(rows)


def summarise(name: str, out: pd.DataFrame) -> dict:
    n = len(out)
    row = dict(
        arm=name,
        energy_median=out.energy_err.median(), energy_worst=out.energy_err.max(),
        energy_bias=out.energy_signed.median(),
        energy_within=int((out.energy_err <= ENERGY_REPORT).sum()),
        soc_median=out.soc_abs_error.median(), soc_worst=out.soc_abs_error.max(),
        soc_within=int((out.soc_abs_error <= SOC_LIMIT).sum()),
        rmse_median=out.rmse_frac.median(), n=n,
    )
    print(f"{name:22s} energy {row['energy_median']*100:5.1f}% median, "
          f"{row['energy_bias']*100:+6.1f}% bias, {row['energy_within']}/{n} within 5%"
          f"   |   SoC {row['soc_median']*100:5.2f} pp median, "
          f"{row['soc_within']}/{n} within 2 pp"
          f"   |   inst RMSE {row['rmse_median']*100:5.1f}%")
    return row


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/ved_canonical.pkl")
    ap.add_argument("--i3-params", default="data/i3_params.json")
    ap.add_argument("--splits", default="data/ved_splits.json")
    ap.add_argument("--fit-trips", type=int, default=10)
    args = ap.parse_args()

    df = pd.read_pickle(args.data)
    i3 = json.loads(Path(args.i3_params).read_text())
    ident = i3["identified"]
    grid = np.array(i3["motor_efficiency_grid"])

    split_path = Path(args.splits)
    if split_path.exists():
        sp = json.loads(split_path.read_text())
        split = Split(sp["train"], sp["val"], sp["test"])
    else:
        split = make_trip_splits(df, seed=20260830)
        split_path.write_text(json.dumps(
            {"seed": 20260830, "train": split.train, "val": split.val,
             "test": split.test}, indent=2))
    train, val, _ = apply_split(df, split)
    print(f"VED trips: {len(split.train)} train, {len(split.val)} val, "
          f"{len(split.test)} test (sealed)")

    base = measure_base_load(train)
    aux_channel = fit_auxiliary(train.t_ambient_c.to_numpy(),
                                train.p_aux_w.to_numpy())
    aux = replace(aux_channel, p_base_w=base)
    print(f"VED base load measured at rest: {base:.0f} W")
    print(f"VED auxiliary fit: k_heat {aux.k_heat_w_per_c:.1f}, "
          f"k_cool {aux.k_cool_w_per_c:.1f} W/C")

    val_trips = [val[val.trip_id == t].reset_index(drop=True)
                 for t in sorted(val.trip_id.unique())]

    print(f"\n{'':22s} {'energy':^46s}   {'terminal SoC':^30s}")
    arms = {}

    arms["A transfer"] = build_leaf(
        c_rr=ident["c_rr"], cd=ident["cd"], r0_ohm=ident["r0_ohm"],
        rot_mass_factor=ident["rot_mass_factor"], aux=aux, efficiency_grid=grid)
    arms["B measured chassis"] = build_leaf(
        c_rr=MEASURED_C_RR, cd=MEASURED_CD, r0_ohm=MEASURED_R0_OHM,
        rot_mass_factor=ident["rot_mass_factor"], aux=aux, efficiency_grid=grid,
        c_rr_source="MEASURED: Idaho National Laboratory coastdown [L1]",
        cd_source="MEASURED: Idaho National Laboratory coastdown [L1]")

    print(f"\nnoise floor on this data: {noise_floor(val_trips):.1f}% of mean |P|")
    print("  the best an unconstrained road-load fit can do per trip, so nothing")
    print("  of this model class beats it. The i3's floor, with that vehicle's own")
    print("  logged motor torque, was 7.0%. VED updates speed about once a second,")
    print("  so the inertial term carries more noise than the signal it sits in.")

    # Arm C: refit the chassis parameters on VED training trips. r0 is NOT
    # fitted: it was measured at 0.079 ohm from VED's own voltage response, and
    # G2 established that battery power is nearly insensitive to it, so a free
    # r0 has no gradient to follow and drifts to whichever bound is nearer.
    fit_ids = sorted(train.trip_id.unique())
    fit_ids = sorted(fit_ids, key=lambda t: -len(train[train.trip_id == t]))
    subsets = [train[train.trip_id == t].reset_index(drop=True)
               for t in fit_ids[: args.fit_trips]]

    def residuals(x):
        p = build_leaf(c_rr=x[0], cd=x[1], r0_ohm=MEASURED_R0_OHM,
                       rot_mass_factor=x[2], aux=aux, efficiency_grid=grid)
        return np.concatenate([
            (simulate_trip(p, t) - (t.v_batt_v * t.i_batt_a).to_numpy()) / 1000.0
            for t in subsets])

    print("\nre-identifying c_rr, cd and rot_mass_factor on VED training trips...")
    lo = np.array([0.004, 0.15, 0.0])
    hi = np.array([0.030, 0.45, 0.35])
    res = least_squares(residuals, np.array([MEASURED_C_RR, MEASURED_CD, 0.10]),
                        bounds=(lo, hi), x_scale=np.array([0.005, 0.1, 0.05]),
                        xtol=1e-10, ftol=1e-10)
    c_rr, cd, rot = (float(v) for v in res.x)
    r0 = MEASURED_R0_OHM
    pinned = [n for n, v, a, b in zip(("c_rr", "cd", "rot"), res.x, lo, hi)
              if abs(v - a) < 1e-9 or abs(v - b) < 1e-9]
    print(f"  c_rr {c_rr:.5f}   cd {cd:.5f}   rot {rot:.5f}   "
          f"(r0 held at the measured {r0:.3f})")
    print(f"  i3 identified   : {ident['c_rr']:.5f}, {ident['cd']:.5f}, "
          f"{ident['rot_mass_factor']:.5f}")
    print(f"  Leaf coastdown  : {MEASURED_C_RR:.5f}, {MEASURED_CD:.5f}")
    if pinned:
        print(f"  WARNING: pinned at a bound: {pinned}")
    arms["C re-identified"] = build_leaf(
        c_rr=c_rr, cd=cd, r0_ohm=r0, rot_mass_factor=rot, aux=aux,
        efficiency_grid=grid,
        c_rr_source="identified on VED training trips",
        cd_source="identified on VED training trips",
        rot_source="identified on VED training trips")

    print()
    rows, per_arm = [], {}
    for name, params in arms.items():
        out = score(params, val_trips)
        per_arm[name] = out
        rows.append(summarise(name, out))

    pd.DataFrame(rows).to_csv("docs/ved-generalisation.csv", index=False)
    pd.concat([o.assign(arm=k) for k, o in per_arm.items()]) \
        .to_csv("docs/ved-per-trip.csv", index=False)
    print("\nwrote docs/ved-generalisation.csv and docs/ved-per-trip.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
