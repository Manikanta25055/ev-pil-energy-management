"""How one dataset's raw files differ from a plain canonical CSV.

Every dataset this project reads gets a `Dialect`: a declaration of its
separator, encoding, header typos, sign conventions, absent channels and
smoothing windows. Declaring them as data rather than as branching code means
what was done to a raw file can be read in one place and audited against the
provenance notes, instead of being reconstructed from control flow.

The derivation that turns a mapped frame into the canonical schema lives here
too, so that acceleration and grade are computed the same way for every
dataset. A signal that means different things in different loaders is worse
than no signal.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from evpil.data.schema import CANONICAL_COLUMNS, validate_frame

KMH_TO_MPS = 1.0 / 3.6
PERCENT_TO_FRAC = 0.01


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

    # (canonical column, factor) applied right after the mapping, for source
    # units the canonical schema does not assume. Speed in km/h and SoC in
    # percent are handled for every dialect; this is for the rest.
    scale: tuple[tuple[str, float], ...] = ()

    # (canonical column, value) for channels the source simply does not carry.
    # A constant elevation yields a zero grade, which is the honest answer when
    # there is no elevation channel to derive one from.
    constant_columns: tuple[tuple[str, float], ...] = ()


DEFAULT_DIALECT = Dialect()


def read_raw(path: Path, dialect: Dialect) -> pd.DataFrame:
    """Read one raw file and repair its header, before any mapping is applied."""
    raw = pd.read_csv(path, sep=dialect.sep, encoding=dialect.encoding,
                      low_memory=False)
    fixes = dict(dialect.header_fixes)
    # Trailing spaces appear on some headers; strip before repairing so that a
    # fix keyed on the clean name still matches.
    raw.columns = [fixes.get(c.strip(), c.strip()) for c in raw.columns]
    # Duplicate headers exist in some archives (two columns differing only by a
    # trailing space). Keep the first; none are ones we map.
    return raw.loc[:, ~raw.columns.duplicated()]


def canonicalise(raw: pd.DataFrame, mapping: dict[str, str],
                 dialect: Dialect, *, validate: bool = True) -> pd.DataFrame:
    """Turn a raw frame into the canonical schema under `dialect`'s rules.

    `raw` must already have repaired headers. Source columns absent from
    `mapping` are dropped; canonical columns the source does not carry come
    from `dialect.constant_columns`.
    """
    unknown = [src for src in mapping if src not in raw.columns]
    if unknown:
        raise KeyError(f"mapping names absent from file: {unknown}")

    df = raw[list(mapping)].rename(columns=mapping).copy()
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    for target, value in dialect.constant_columns:
        df[target] = float(value)

    # Compose canonical signals that are spread across several source channels.
    for target, sources, factor in dialect.sum_into:
        missing = [s for s in sources if s not in raw.columns]
        if missing:
            raise KeyError(f"cannot compose {target!r}, missing: {missing}")
        parts = [pd.to_numeric(raw[s], errors="coerce").fillna(0.0) for s in sources]
        df[target] = sum(parts) * factor

    for col, factor in dialect.scale:
        df[col] = df[col] * factor

    # Unit normalisation every source shares: km/h and percent.
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

    df = _derive_motion(df, dialect)

    if "t_batt_c" not in df.columns:
        df["t_batt_c"] = df["t_ambient_c"]

    df = df[list(CANONICAL_COLUMNS)]
    if validate:
        validate_frame(df)
    return df


def _derive_motion(df: pd.DataFrame, dialect: Dialect) -> pd.DataFrame:
    """Acceleration and grade, derived rather than trusted from the source.

    Both are computed from the canonical speed so that they cannot disagree
    with it, which a logged accelerometer or grade channel is free to do.
    """
    t = df["t_s"].to_numpy()
    dt = np.diff(t, prepend=np.nan)
    v = df["v_mps"].to_numpy()

    # Acceleration by backward difference; the first sample is backfilled.
    a = pd.Series(np.diff(v, prepend=np.nan) / dt).bfill().fillna(0.0)
    # Bound BEFORE smoothing. A speed dropout can produce 54 m/s^2 in one
    # sample, and averaging that with its neighbours spreads one bad
    # measurement over the whole window instead of containing it. Clipping
    # first keeps a dropout local; the second clip after smoothing then only
    # has to hold a bound the average cannot exceed anyway.
    if dialect.max_accel_mps2 is not None:
        a = a.clip(-dialect.max_accel_mps2, dialect.max_accel_mps2)
    if dialect.accel_smooth_samples > 1:
        a = a.rolling(dialect.accel_smooth_samples, center=True,
                      min_periods=1).mean()
    a = a.to_numpy()
    if dialect.max_accel_mps2 is not None:
        a = np.clip(a, -dialect.max_accel_mps2, dialect.max_accel_mps2)
    df["a_mps2"] = a

    # Grade is vertical speed over road speed. Elevation is averaged over a
    # centred window first: differencing it sample to sample divides a
    # metre-scale step by a centimetre-scale distance.
    win = max(1, dialect.grade_window_samples)
    if win > 1:
        elev = (df["elevation_m"].rolling(win, center=True, min_periods=1)
                                 .mean().to_numpy())
        step = float(np.nanmedian(dt))
        dzdt = np.gradient(elev, step) if np.isfinite(step) and step > 0 else np.zeros_like(elev)
    else:
        dzdt = np.diff(df["elevation_m"].to_numpy(), prepend=np.nan) / dt
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(v >= dialect.grade_min_speed_mps,
                         dzdt / np.where(v > 0.0, v, np.nan), 0.0)
    ratio = np.clip(np.nan_to_num(ratio, nan=0.0, posinf=0.0, neginf=0.0), -1.0, 1.0)
    df["grade_rad"] = np.arcsin(ratio)
    return df
