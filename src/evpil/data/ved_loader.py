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

from pathlib import Path

import numpy as np
import pandas as pd

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
# elevation_m: VED logs latitude and longitude but no elevation, so it is set
#   to a constant and the derived grade is therefore zero everywhere. The
#   consequence is stated rather than hidden: on a trip that returns near its
#   starting elevation the grade term contributes little NET energy, because
#   what is spent climbing is partly recovered descending, but INSTANTANEOUS
#   power on any real hill is wrong. Ann Arbor is not flat. Recovering grade
#   needs the GPS trace map-matched against a digital elevation model, which is
#   a separate piece of work with its own data licence; `elevation_column`
#   below is the hook for it.
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
    dialect: Dialect = VED_DIALECT,
) -> pd.DataFrame:
    """Return the BEV trips in the canonical schema, tagged with `trip_id`.

    `cache`, when it exists, is read instead of rescanning the weekly files.
    `trip_ids` restricts the result, which is how the eligibility rule is
    applied without rewriting anything on disk.
    """
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
        frame = canonicalise(block, VED_MAPPING, dialect)
        frame["trip_id"] = tid
        frames.append(frame)

    if not frames:
        raise ValueError("no trips selected")
    return pd.concat(frames, ignore_index=True)


def raw_trips(raw: pd.DataFrame):
    """Iterate (trip_id, block) over a raw BEV frame, sorted in time."""
    for (veh, trip), block in raw.groupby(["VehId", "Trip"], sort=True):
        yield _trip_id(veh, trip), block.sort_values("Timestamp(ms)")
