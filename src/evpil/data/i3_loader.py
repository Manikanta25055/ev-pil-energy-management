"""Load BMW i3 real-driving trips into the canonical schema.

The archive's own column names are recorded in docs/dataset-provenance.md and
supplied here as a mapping, so this module never hardcodes names it has not
seen. Derived signals (acceleration, grade) are computed here rather than
trusted from the source, since their definitions vary between datasets.

The archive also has quirks that a plain read_csv gets wrong: a semicolon
separator, cp1252 degree signs, a header typo, a battery-current sign
convention opposite to ours, and an auxiliary load split across two channels.
Those are declared as a `Dialect` -- data, not branching code -- so that what
was done to the raw file is auditable in one place.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from evpil.data.schema import CANONICAL_COLUMNS, validate_frame

KMH_TO_MPS = 1.0 / 3.6
PERCENT_TO_FRAC = 0.01

# Below this speed the horizontal distance per sample is too small for
# elevation differences to give a meaningful grade, so grade is set to zero.
_MIN_SPEED_FOR_GRADE_MPS = 0.5


@dataclass(frozen=True)
class Dialect:
    """How one archive's raw files differ from a plain canonical CSV.

    Every field defaults to "no adjustment", so the default Dialect reads an
    ordinary comma-separated file and changes nothing.
    """

    sep: str = ","
    encoding: str = "utf-8"

    # (wrong, right) header repairs, applied before the mapping is looked up.
    header_fixes: tuple[tuple[str, str], ...] = ()

    # Canonical columns whose source uses the opposite sign convention.
    negate: tuple[str, ...] = ()

    # (canonical target, source columns to sum, scale). Used where one
    # canonical signal is spread across several source channels.
    sum_into: tuple[tuple[str, tuple[str, ...], float], ...] = ()

    # (canonical column, low, high). Applied after unit conversion, to bound
    # known instrument glitches rather than to reshape real data.
    clip: tuple[tuple[str, float, float], ...] = ()

    # Longest run of missing samples that may be filled by interpolation.
    # Zero disables filling, so gaps surface as a SchemaError instead.
    max_gap_samples: int = 0

    # Centred window, in samples, over which elevation is averaged before it is
    # differentiated into a grade. 1 means differentiate the raw signal.
    grade_window_samples: int = 1

    # Speed below which grade is reported as zero. Grade is dz/ds, and ds is
    # speed times the sample interval, so a slow sample divides a real
    # elevation change by a near-zero distance.
    grade_min_speed_mps: float = 0.5

    # Bound on derived acceleration, in m/s^2. None leaves it unbounded. This
    # catches single-sample speed dropouts, not hard driving.
    max_accel_mps2: float | None = None

    # Centred window, in samples, over which derived acceleration is averaged.
    # 1 leaves the raw backward difference alone.
    accel_smooth_samples: int = 1

    # Largest physically possible change in SoC between two samples, as a
    # fraction. Samples that jump further are dropouts, not measurements, and
    # are replaced by NaN so the gap fill repairs them. None disables the test.
    max_soc_step: float | None = None


DEFAULT_DIALECT = Dialect()

# The BMW i3 archive (Steinstraeter et al., DOI 10.21227/6jr9-5235).
# Each quirk below was established by inspecting the real files; the evidence
# is recorded in docs/dataset-provenance.md.
I3_ARCHIVE = Dialect(
    sep=";",
    encoding="cp1252",
    # TripB38's velocity header carries three closing brackets.
    header_fixes=(("Velocity [km/h]]]", "Velocity [km/h]"),),
    # The archive logs discharge as NEGATIVE current; the canonical schema is
    # positive-is-discharge. Established from the sign of Motor Torque against
    # current (r = -0.9) and from SoC falling while current is negative.
    negate=("i_batt_a",),
    # Auxiliary electrical load is the cabin heater plus the AC compressor,
    # both reported in kW.
    sum_into=(("p_aux_w", ("Heating Power CAN [kW]", "AirCon Power [kW]"), 1000.0),),
    # The i3's PTC heater is ~6 kW and its compressor ~3 kW, so nothing above
    # 10 kW is real. TripB02 carries a single 40 kW spike.
    clip=(("p_aux_w", 0.0, 10000.0),),
    # Eligible trips have at most 13 missing SoC samples (1.3 s) at the head,
    # before the first SoC frame arrives on the bus.
    max_gap_samples=100,
    # Road gradient does not change meaningfully in 0.1 s, and differentiating
    # the raw 10 Hz elevation gives grades up to 90 degrees at low speed. A
    # 10.1 s centred window covers roughly 200 m at highway speed and holds
    # every eligible trip's grade under 0.30 rad, inside the schema's 0.35 rad
    # bound -- so the bound is a check, not a shaper. Widening to 20 s halves
    # the peak again, which would start erasing real short hills.
    grade_window_samples=101,
    grade_min_speed_mps=2.0,
    # The i3 reaches 100 km/h in 7.2 s (3.9 m/s^2) and cannot brake harder than
    # about 1 g, so 10 m/s^2 is beyond anything the vehicle does. Across the 33
    # eligible trips it touches 2 samples in one trip, where speed drops from
    # 9.8 m/s to 0 in a single 0.1 s step while battery current falls from
    # 140 A to 7 A: a bus dropout, not a manoeuvre.
    max_accel_mps2=10.0,
    # Differentiating a 10 Hz speed channel puts noise straight into the
    # inertial force, where 1270 kg turns 0.1 m/s^2 of it into 127 N. A 0.5 s
    # centred average is the window that best matches the archive's own logged
    # Motor Torque channel: it lifts agreement from r = 0.971 to r = 0.987 and
    # drops torque RMSE from 11.1 to 9.0 Nm. Wider windows (2 s, 5 s) make both
    # worse again, so this is a measured optimum rather than a taste.
    accel_smooth_samples=5,
    # At the 400 A peak the pack sees, a 60 Ah battery moves 0.0019 of SoC per
    # second, so 0.1 s cannot move it more than 0.0002. The channel is
    # quantised to 0.001 (0.1 pp), so 0.01 is 10 quantisation steps and still
    # 50x beyond anything physical. TripB14's final sample drops from 0.346 to
    # 0.000 in one step -- a dropout that the terminal-SoC criterion would
    # otherwise read as a 34 pp model error.
    max_soc_step=0.01,
)

# Source-to-canonical names for the i3 archive. Columns absent here are dropped.
# `p_aux_w` is absent on purpose: it is composed by the dialect's `sum_into`.
I3_MAPPING: dict[str, str] = {
    "Time [s]": "t_s",
    "Velocity [km/h]": "v_mps",
    "Elevation [m]": "elevation_m",
    "SoC [%]": "soc_frac",
    "Battery Current [A]": "i_batt_a",
    "Battery Voltage [V]": "v_batt_v",
    "Ambient Temperature [°C]": "t_ambient_c",
    "Battery Temperature [°C]": "t_batt_c",
}


def _read_raw(path: Path, dialect: Dialect) -> pd.DataFrame:
    raw = pd.read_csv(path, sep=dialect.sep, encoding=dialect.encoding,
                      low_memory=False)
    fixes = dict(dialect.header_fixes)
    # Trailing spaces appear on some headers; strip before repairing so that a
    # fix keyed on the clean name still matches.
    raw.columns = [fixes.get(c.strip(), c.strip()) for c in raw.columns]
    # Duplicate headers exist (two 'Temperature Vent right' columns differing
    # only by a trailing space). Keep the first; none are ones we map.
    return raw.loc[:, ~raw.columns.duplicated()]


def load_trip(
    path: Path,
    mapping: dict[str, str],
    dialect: Dialect = DEFAULT_DIALECT,
) -> pd.DataFrame:
    """Load one trip CSV and return it in the canonical schema.

    `mapping` maps source column names to canonical names. Source columns
    absent from the mapping are dropped. `dialect` declares the archive's
    quirks; the default assumes a plain comma-separated canonical file.
    """
    raw = _read_raw(Path(path), dialect)

    unknown = [src for src in mapping if src not in raw.columns]
    if unknown:
        raise KeyError(f"{Path(path).name}: mapping names absent from file: {unknown}")

    df = raw[list(mapping)].rename(columns=mapping).copy()
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Compose canonical signals that are spread across several source channels.
    for target, sources, scale in dialect.sum_into:
        missing = [s for s in sources if s not in raw.columns]
        if missing:
            raise KeyError(f"{Path(path).name}: cannot compose {target!r}, "
                           f"missing source columns: {missing}")
        parts = [pd.to_numeric(raw[s], errors="coerce").fillna(0.0) for s in sources]
        df[target] = sum(parts) * scale

    # Unit normalisation. The archive stores km/h and percent.
    df["v_mps"] = df["v_mps"] * KMH_TO_MPS
    df["soc_frac"] = df["soc_frac"] * PERCENT_TO_FRAC

    for col in dialect.negate:
        df[col] = -df[col]

    for col, lo, hi in dialect.clip:
        df[col] = df[col].clip(lo, hi)

    if dialect.max_soc_step is not None:
        step = df["soc_frac"].diff().abs()
        df.loc[step > dialect.max_soc_step, "soc_frac"] = np.nan

    # Short dropouts are interpolated; anything longer is left as NaN so that
    # validate_frame rejects the trip rather than inventing data for it.
    if dialect.max_gap_samples > 0:
        df = df.interpolate(limit=dialect.max_gap_samples,
                            limit_direction="both", limit_area=None)

    dt = np.diff(df["t_s"].to_numpy(), prepend=np.nan)

    # Acceleration by backward difference; the first sample is backfilled.
    dv = np.diff(df["v_mps"].to_numpy(), prepend=np.nan)
    a = dv / dt
    a = pd.Series(a).bfill().fillna(0.0)
    if dialect.accel_smooth_samples > 1:
        a = a.rolling(dialect.accel_smooth_samples, center=True, min_periods=1).mean()
    a = a.to_numpy()
    if dialect.max_accel_mps2 is not None:
        a = np.clip(a, -dialect.max_accel_mps2, dialect.max_accel_mps2)
    df["a_mps2"] = a

    # Grade is the ratio of vertical to along-road distance, which is the
    # vertical speed divided by the road speed. Elevation is averaged over a
    # centred window first: at 10 Hz the raw difference divides a metre-scale
    # elevation step by a centimetre-scale distance step.
    v = df["v_mps"].to_numpy()
    win = max(1, dialect.grade_window_samples)
    if win > 1:
        elev = (df["elevation_m"].rolling(win, center=True, min_periods=1)
                                 .mean().to_numpy())
        dzdt = np.gradient(elev, float(np.nanmedian(dt)))
    else:
        elev = df["elevation_m"].to_numpy()
        dzdt = np.diff(elev, prepend=np.nan) / dt
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(v >= dialect.grade_min_speed_mps,
                         dzdt / np.where(v > 0.0, v, np.nan), 0.0)
    ratio = np.clip(np.nan_to_num(ratio, nan=0.0, posinf=0.0, neginf=0.0), -1.0, 1.0)
    df["grade_rad"] = np.arcsin(ratio)

    if "t_batt_c" not in df.columns:
        df["t_batt_c"] = df["t_ambient_c"]

    df = df[list(CANONICAL_COLUMNS)]
    validate_frame(df)
    return df


def load_all_trips(
    root: Path,
    mapping: dict[str, str],
    dialect: Dialect = DEFAULT_DIALECT,
    trip_ids: list[str] | None = None,
) -> pd.DataFrame:
    """Load every CSV under `root`, tagging each with a `trip_id` from its stem.

    `trip_ids`, when given, restricts the load to those stems -- used to apply
    the eligibility rule without moving files around.
    """
    root = Path(root)
    paths = sorted(root.glob("*.csv"))
    if trip_ids is not None:
        wanted = set(trip_ids)
        paths = [p for p in paths if p.stem in wanted]
    if not paths:
        raise FileNotFoundError(f"no CSV files under {root}")

    frames = []
    for p in paths:
        trip = load_trip(p, mapping, dialect)
        trip["trip_id"] = p.stem
        frames.append(trip)

    return pd.concat(frames, ignore_index=True)
