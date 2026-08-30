# scripts/build_ved.py
"""Build the VED battery-electric subset and report what it contains.

VED is the external dataset for the cross-dataset generalisation claim. It has
no part in gate G2, which is decided on the i3 archive alone; running this
script does not change any G2 number.

Writes `data/ved_canonical.pkl`, `docs/ved-eligibility.csv` and prints the
summary that `docs/dataset-provenance.md` records.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from evpil.data.dem import DEM
from evpil.data.ved_eligibility import assess_all
from evpil.data.ved_loader import GRADE_BASELINE_M, extract_bev_subset, load_bev_trips
from evpil.plant.auxiliary import aux_power_w, fit_auxiliary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/raw/ved/csv")
    ap.add_argument("--cache", default="data/raw/ved/bev_raw.pkl")
    ap.add_argument("--out", default="data/ved_canonical.pkl")
    ap.add_argument("--dem", default="data/raw/dem/annarbor_3dep_13.npz",
                    help="run scripts/build_dem.py first; omit for zero grade")
    args = ap.parse_args()

    cache = Path(args.cache)
    if cache.exists():
        raw = pd.read_pickle(cache)
        print(f"read cached BEV subset: {len(raw)} rows")
    else:
        print("scanning the weekly files (about 3 GB, filtered as they are read)")
        raw = extract_bev_subset(Path(args.data), cache)
        print(f"extracted {len(raw)} BEV rows to {cache}")

    verdicts = assess_all(raw)
    verdicts.to_csv("docs/ved-eligibility.csv", index=False)
    eligible = sorted(verdicts.loc[verdicts.eligible, "trip_id"])
    print(f"\ntrips: {len(verdicts)}   eligible: {len(eligible)}")
    for reason, n in verdicts.loc[~verdicts.eligible, "reason"] \
            .str.replace(r"[\d.]+", "N", regex=True).value_counts().items():
        print(f"   {n:4d}  {reason}")

    dem = None
    if args.dem and Path(args.dem).exists():
        dem = DEM.load(args.dem)
        print(f"\nelevation from {args.dem}: {dem.elevation.shape[0]} x "
              f"{dem.elevation.shape[1]} at {dem.cell_size_m:.1f} m, {dem.crs}")
    else:
        print(f"\nno DEM at {args.dem}: elevation constant, grade zero. "
              f"Run scripts/build_dem.py to recover it.")

    df = load_bev_trips(Path(args.data), cache=cache, trip_ids=eligible, dem=dem)
    df.to_pickle(args.out)
    print(f"\ncanonical frame: {len(df)} rows, {df.trip_id.nunique()} trips "
          f"-> {args.out}")

    dt = df.groupby("trip_id").t_s.diff().dropna()
    per_trip = verdicts[verdicts.eligible]
    print(f"   sample interval : median {dt.median():.2f} s, "
          f"10th-90th {dt.quantile(.1):.2f}-{dt.quantile(.9):.2f} s")
    print(f"   distance        : {per_trip.distance_km.sum():.0f} km total, "
          f"median {per_trip.distance_km.median():.1f} km per trip")
    print(f"   ambient         : {df.t_ambient_c.min():.1f} to "
          f"{df.t_ambient_c.max():.1f} C")
    if dem is not None:
        g = df.grade_rad
        print(f"   elevation       : {df.elevation_m.min():.1f} to "
              f"{df.elevation_m.max():.1f} m")
        print(f"   grade           : sd {g.std():.4f} rad, 99th percentile "
              f"{g.abs().quantile(.99):.4f}, max {g.abs().max():.4f}, "
              f"measured over {GRADE_BASELINE_M:.0f} m of road")
        print(f"                     {100*(g.abs() > 0.10).mean():.3f}% steeper "
              f"than 10%, which is about the limit of a US road")

    # The reason VED is worth having beyond a second opinion: it contains the
    # warm half of the auxiliary model that the i3 eligible set does not.
    aux = fit_auxiliary(df.t_ambient_c.to_numpy(), df.p_aux_w.to_numpy())
    pred = np.array([aux_power_w(aux, t) for t in df.t_ambient_c.to_numpy()])
    obs = df.p_aux_w.to_numpy()
    r2 = 1.0 - ((obs - pred) ** 2).sum() / ((obs - obs.mean()) ** 2).sum()
    warm = float((df.t_ambient_c > aux.t_setpoint_c).mean())
    print(f"\nauxiliary fit on VED  (i3 eligible set for contrast in brackets)")
    print(f"   samples above the {aux.t_setpoint_c:.0f} C setpoint: "
          f"{warm*100:.1f}%   [0.0%]")
    print(f"   k_heat = {aux.k_heat_w_per_c:6.1f} W/C")
    print(f"   k_cool = {aux.k_cool_w_per_c:6.1f} W/C   [0.0, unidentified]")
    print(f"   R^2    = {r2:6.3f}          [0.047]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
