"""Load BMW i3 real-driving trips into the canonical schema.

The archive's own column names are recorded in docs/dataset-provenance.md and
supplied here as a mapping, so this module never hardcodes names it has not
seen. Derived signals (acceleration, grade) are computed here rather than
trusted from the source, since their definitions vary between datasets.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from evpil.data.schema import CANONICAL_COLUMNS, validate_frame

KMH_TO_MPS = 1.0 / 3.6
PERCENT_TO_FRAC = 0.01

# Below this speed the horizontal distance per sample is too small for
# elevation differences to give a meaningful grade, so grade is set to zero.
_MIN_SPEED_FOR_GRADE_MPS = 0.5


def load_trip(path: Path, mapping: dict[str, str]) -> pd.DataFrame:
    """Load one trip CSV and return it in the canonical schema.

    `mapping` maps source column names to canonical names. Source columns
    absent from the mapping are dropped.
    """
    raw = pd.read_csv(path)

    unknown = [src for src in mapping if src not in raw.columns]
    if unknown:
        raise KeyError(f"{path.name}: mapping names absent from file: {unknown}")

    df = raw[list(mapping)].rename(columns=mapping).copy()

    # Unit normalisation. The archive stores km/h and percent.
    df["v_mps"] = df["v_mps"] * KMH_TO_MPS
    df["soc_frac"] = df["soc_frac"] * PERCENT_TO_FRAC

    dt = np.diff(df["t_s"].to_numpy(), prepend=np.nan)

    # Acceleration by backward difference; the first sample is backfilled.
    dv = np.diff(df["v_mps"].to_numpy(), prepend=np.nan)
    a = dv / dt
    df["a_mps2"] = pd.Series(a).bfill().fillna(0.0).to_numpy()

    # Grade from elevation change over distance travelled in the same interval.
    dz = np.diff(df["elevation_m"].to_numpy(), prepend=np.nan)
    ds = df["v_mps"].to_numpy() * dt
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(df["v_mps"].to_numpy() >= _MIN_SPEED_FOR_GRADE_MPS,
                         dz / ds, 0.0)
    ratio = np.clip(np.nan_to_num(ratio, nan=0.0, posinf=0.0, neginf=0.0), -1.0, 1.0)
    df["grade_rad"] = np.arcsin(ratio)

    if "t_batt_c" not in df.columns:
        df["t_batt_c"] = df["t_ambient_c"]

    df = df[list(CANONICAL_COLUMNS)]
    validate_frame(df)
    return df


def load_all_trips(root: Path, mapping: dict[str, str]) -> pd.DataFrame:
    """Load every CSV under `root`, tagging each with a `trip_id` from its stem."""
    root = Path(root)
    paths = sorted(root.glob("*.csv"))
    if not paths:
        raise FileNotFoundError(f"no CSV files under {root}")

    frames = []
    for p in paths:
        trip = load_trip(p, mapping)
        trip["trip_id"] = p.stem
        frames.append(trip)

    return pd.concat(frames, ignore_index=True)
