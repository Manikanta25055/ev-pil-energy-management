"""Load the battery-electric subset of VED into the canonical schema.

VED (Oh, LeBlanc and Peng, IEEE T-ITS 2020) is the project's second, external
dataset. Its job is the cross-dataset generalisation claim, not gate G2: a
model identified and validated on one vehicle, one logger and one country
answers "does it fit?" but not "does it transfer?".

Three things about VED differ from the i3 archive in ways that matter, and all
three are established by reading the files rather than the documentation:

  - The fleet is 383 vehicles, of which THREE are battery-electric
    (2013 Nissan Leaf, VehId 10, 455 and 541). Everything else is gasoline or
    hybrid and carries no usable high-voltage channel.
  - The data is organised as 54 weekly files covering the whole fleet, not one
    file per trip, so a trip is a (VehId, Trip) pair inside them.
  - Two canonical channels are simply absent: there is no elevation and no
    battery temperature. See ABSENT CHANNELS below for what that costs.

The repository README documents the ambient column as
`Outside Air Temperature[DegC]`. The files call it `OAT[DegC]`. The mapping
below uses what the files say.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from evpil.data.dem import DEM
from evpil.data.dialect import Dialect, canonicalise

# The three battery-electric vehicles, read off VED_Static_Data_PHEV&EV.xlsx
# where EngineType == "EV". All three are 3500 lb class, 2013 Nissan Leaf.
BEV_VEH_IDS: tuple[int, ...] = (10, 455, 541)

# Only these columns are read from the weekly files. The rest describe engines
# this project does not model, and skipping them keeps a 3 GB scan affordable.
SOURCE_COLUMNS: tuple[str, ...] = (
    "DayNum", "VehId", "Trip", "Timestamp(ms)",
    "Latitude[deg]", "Longitude[deg]", "Vehicle Speed[km/h]", "OAT[DegC]",
    "Air Conditioning Power[Watts]", "Heater Power[Watts]",
    "HV Battery Current[A]", "HV Battery SOC[%]", "HV Battery Voltage[V]",
)

VED_MAPPING: dict[str, str] = {
    "Timestamp(ms)": "t_s",
    "Vehicle Speed[km/h]": "v_mps",
    "HV Battery SOC[%]": "soc_frac",
    "HV Battery Current[A]": "i_batt_a",
    "HV Battery Voltage[V]": "v_batt_v",
    "OAT[DegC]": "t_ambient_c",
}

# ---------------------------------------------------------------------------
# ABSENT CHANNELS
#
# elevation_m: VED logs latitude and longitude but no elevation. Passing a
#   `DEM` to `load_bev_trips` recovers it by sampling a digital elevation
#   model at each GPS fix, which is the supported path and what
#   `VED_DEM_DIALECT` is for. Without one the loader falls back to a constant
#   elevation and therefore a zero gradient, and the consequence is stated
#   rather than hidden: on a trip returning near its starting elevation the
#   grade term costs little NET energy, since climbing is partly recovered
#   descending, but instantaneous power on any real hill is wrong.
#
# t_batt_c: no battery temperature channel. The canonical loader falls back to
#   ambient, which is right at key-on and increasingly wrong as the pack
#   self-heats.
# ---------------------------------------------------------------------------

VED_DIALECT = Dialect(
    # Timestamps are milliseconds from the start of the trip.
    scale=(("t_s", 1e-3),),
    # Discharge is logged negative, the same convention as the i3 archive and
    # the opposite of the canonical schema. Established three ways on the BEV
    # rows: mean current while driving above 30 km/h is -20.3 A, mean current
    # at rest is -3.5 A, and the pooled correlation between per-sample SoC
    # change and current is +0.30, so positive current is the charging
    # direction.
    negate=("i_batt_a",),
    # Auxiliary load is the cabin heater plus the AC compressor. Both are
    # already in watts here, unlike the i3 archive's kilowatts, so the factor
    # is 1. `Air Conditioning Power[kW]` exists in the header but is empty on
    # every BEV row; the watts column is the populated one.
    sum_into=(("p_aux_w", ("Air Conditioning Power[Watts]",
                           "Heater Power[Watts]"), 1.0),),
    # Observed maxima are 3100 W of AC and 4250 W of heater. Nothing above
    # 8 kW is a Leaf's cabin load.
    clip=(("p_aux_w", 0.0, 8000.0),),
    constant_columns=(("elevation_m", 0.0),),
    # No elevation means no grade to smooth, so the window is inert. Left at 1
    # so that supplying a real elevation column does not silently inherit a
    # window tuned for a 10 Hz archive.
    grade_window_samples=1,
    # The logger's interval is not just coarser than the i3's, it is
    # IRREGULAR: a median of 400 ms, but 39% of samples arrive less than
    # 250 ms apart and another third about a second apart. Differencing speed
    # across a short, jittery step is what injects the noise, not the coarse
    # rate. It shows in the data directly: 3.6% of samples taken less than
    # 250 ms apart exceed 5 m/s^2, against 0.04% of those about a second
    # apart. A 2013 Leaf reaches 100 km/h in about 11.5 s, so 2.4 m/s^2 is
    # what sustained acceleration looks like and 5 m/s^2 is already hard
    # braking.
    #
    # A 3-sample centred average removes 98.5% of that implausible tail
    # (1.80% of samples above 5 m/s^2 falls to 0.027%) and brings the spread
    # to 0.85 m/s^2, close to the i3 archive's 0.66. Widening to 5 or 7
    # samples buys almost nothing beyond that (0.009%, 0.004%) while going on
    # shrinking real dynamics, so 3 is the knee rather than the floor.
    accel_smooth_samples=3,
    # The same physical bound used for the i3: beyond anything a car does.
    max_accel_mps2=10.0,
    # The Leaf's SoC channel is coarse. Steps of about 1 pp between samples are
    # ordinary quantisation here, and a 16 s gap can carry a genuine 2 pp
    # change, so this only catches gross jumps. Continuity is enforced by the
    # gap test in `assess_trip` instead.
    max_soc_step=0.05,
    max_gap_samples=20,
)


# Used when a DEM supplies elevation. Everything else matches VED_DIALECT.
#
# The 200 m gradient baseline is measured, not assumed. Elevation comes from a
# 10.3 m DEM sampled at GPS fixes, and at urban speeds consecutive samples are
# about 4 m apart, so a per-sample difference asks the DEM for detail it does
# not have. Sweeping the baseline over the eligible trips gives:
#
#     baseline     grade sd     p99 |grade|     max      above 0.10 rad
#        20 m       0.0565        0.2312      1.5708 (vertical)   5.19%
#        50 m       0.0325        0.1219      0.4404              1.89%
#       100 m       0.0258        0.0823      0.2467              0.28%
#     * 200 m       0.0206        0.0587      0.1479              0.05%
#       300 m       0.0181        0.0504      0.0997              0.00%
#       500 m       0.0152        0.0430      0.0649              0.00%
#
# US roads are designed to about 8% and rarely exceed 10%, so 200 m is the
# shortest baseline that puts essentially the whole distribution inside what a
# road can be, which is the same test used to pick the i3 archive's window.
# 300 m would clip the tail entirely, at the cost of erasing short real hills:
# Ann Arbor's relief runs roughly 100 m over 1 to 2 km, and a baseline that
# long starts averaging one side of the Huron valley against the other.
GRADE_BASELINE_M = 200.0

VED_DEM_DIALECT = replace(
    VED_DIALECT, constant_columns=(), grade_distance_m=GRADE_BASELINE_M,
)


def _trip_id(veh_id: int, trip: int) -> str:
    return f"VED_{int(veh_id)}_{int(trip)}"


def extract_bev_subset(root: Path, cache: Path | None = None) -> pd.DataFrame:
    """Scan the weekly files and return only the battery-electric rows.

    The weekly files total about 3 GB across the whole fleet, so they are read
    in chunks and filtered as they go rather than concatenated first.
    """
    root = Path(root)
    paths = sorted(root.glob("*.csv"))
    if not paths:
        raise FileNotFoundError(f"no weekly CSV files under {root}")

    keep = []
    for path in paths:
        for chunk in pd.read_csv(path, usecols=list(SOURCE_COLUMNS),
                                 chunksize=500_000, low_memory=False):
            rows = chunk[chunk["VehId"].isin(BEV_VEH_IDS)]
            if len(rows):
                keep.append(rows)
    if not keep:
        raise ValueError(f"no rows for vehicles {BEV_VEH_IDS} under {root}")

    out = pd.concat(keep, ignore_index=True)
    if cache is not None:
        out.to_pickle(cache)
    return out


def load_bev_trips(
    root: Path,
    cache: Path | None = None,
    trip_ids: list[str] | None = None,
    dialect: Dialect | None = None,
    dem: DEM | None = None,
) -> pd.DataFrame:
    """Return the BEV trips in the canonical schema, tagged with `trip_id`.

    `cache`, when it exists, is read instead of rescanning the weekly files.
    `trip_ids` restricts the result, which is how the eligibility rule is
    applied without rewriting anything on disk.

    `dem`, when given, supplies the elevation VED does not log, sampled at each
    GPS fix, and the gradient is then measured over `GRADE_BASELINE_M` of road.
    Without it elevation is constant and the gradient is zero everywhere.
    """
    if dialect is None:
        dialect = VED_DEM_DIALECT if dem is not None else VED_DIALECT
    root = Path(root)
    if cache is not None and Path(cache).exists():
        raw = pd.read_pickle(cache)
    else:
        raw = extract_bev_subset(root, cache)

    wanted = None if trip_ids is None else set(trip_ids)
    frames = []
    for (veh, trip), block in raw.groupby(["VehId", "Trip"], sort=True):
        tid = _trip_id(veh, trip)
        if wanted is not None and tid not in wanted:
            continue
        block = block.sort_values("Timestamp(ms)").reset_index(drop=True)
        # Timestamps run from the start of the trip, but rebasing costs nothing
        # and makes t_s mean the same thing it means for every other dataset.
        block = block.assign(**{
            "Timestamp(ms)": block["Timestamp(ms)"]
                             - block["Timestamp(ms)"].iloc[0]})
        mapping = dict(VED_MAPPING)
        if dem is not None:
            block = block.assign(_dem_elevation_m=dem.sample(
                block["Latitude[deg]"].to_numpy(),
                block["Longitude[deg]"].to_numpy()))
            mapping["_dem_elevation_m"] = "elevation_m"
        frame = canonicalise(block, mapping, dialect)
        frame["trip_id"] = tid
        frames.append(frame)

    if not frames:
        raise ValueError("no trips selected")
    return pd.concat(frames, ignore_index=True)


def raw_trips(raw: pd.DataFrame):
    """Iterate (trip_id, block) over a raw BEV frame, sorted in time."""
    for (veh, trip), block in raw.groupby(["VehId", "Trip"], sort=True):
        yield _trip_id(veh, trip), block.sort_values("Timestamp(ms)")
