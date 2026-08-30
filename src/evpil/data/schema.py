"""The canonical signal schema every downstream component consumes.

One schema, one set of units. Source-specific column names and units are
normalised at load time so that nothing downstream needs to know which
dataset a row came from.
"""

from __future__ import annotations

import pandas as pd

CANONICAL_COLUMNS: tuple[str, ...] = (
    "t_s",           # seconds since trip start
    "v_mps",         # vehicle speed, metres per second
    "a_mps2",        # longitudinal acceleration, metres per second squared
    "soc_frac",      # state of charge, 0.0 to 1.0
    "i_batt_a",      # battery current, amperes, positive = discharge
    "v_batt_v",      # battery terminal voltage, volts
    "t_ambient_c",   # ambient temperature, degrees Celsius
    "t_batt_c",      # battery temperature, degrees Celsius
    "elevation_m",   # elevation above datum, metres
    "grade_rad",     # road grade angle, radians, positive = uphill
    "p_aux_w",       # auxiliary and HVAC electrical power, watts
)

CANONICAL_UNITS: dict[str, str] = {
    "t_s": "s", "v_mps": "m/s", "a_mps2": "m/s^2", "soc_frac": "-",
    "i_batt_a": "A", "v_batt_v": "V", "t_ambient_c": "degC",
    "t_batt_c": "degC", "elevation_m": "m", "grade_rad": "rad", "p_aux_w": "W",
}

# Sanity ranges. Deliberately generous: these catch unit-conversion mistakes
# and corrupt rows, not unusual-but-real driving.
_RANGES: dict[str, tuple[float, float]] = {
    "v_mps": (-1.0, 70.0),
    "a_mps2": (-150.0, 150.0),
    "soc_frac": (0.0, 1.0),
    "i_batt_a": (-600.0, 600.0),
    "v_batt_v": (200.0, 450.0),
    "t_ambient_c": (-40.0, 60.0),
    "t_batt_c": (-40.0, 80.0),
    "grade_rad": (-0.35, 0.35),
    "p_aux_w": (-1000.0, 12000.0),
}


class SchemaError(ValueError):
    """Raised when a DataFrame does not satisfy the canonical schema."""


def validate_frame(df: pd.DataFrame) -> None:
    missing = [c for c in CANONICAL_COLUMNS if c not in df.columns]
    if missing:
        raise SchemaError(f"missing columns: {missing}")

    for col in CANONICAL_COLUMNS:
        if df[col].isna().any():
            n = int(df[col].isna().sum())
            raise SchemaError(f"column {col!r} contains {n} NaN values")

    for col, (lo, hi) in _RANGES.items():
        vmin, vmax = float(df[col].min()), float(df[col].max())
        if vmin < lo or vmax > hi:
            raise SchemaError(
                f"column {col!r} out of range: [{vmin:.4g}, {vmax:.4g}] "
                f"outside [{lo}, {hi}]"
            )

    t = df["t_s"].to_numpy()
    if len(t) > 1 and not (t[1:] > t[:-1]).all():
        raise SchemaError("column 't_s' is not strictly monotonic increasing")
