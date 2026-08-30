"""Load BMW i3 real-driving trips into the canonical schema.

The archive's own column names are recorded in docs/dataset-provenance.md and
supplied here as a mapping, so this module never hardcodes names it has not
seen. Everything about how the archive differs from a plain canonical CSV
lives in the `I3_ARCHIVE` dialect below; the shared machinery that applies a
dialect is in evpil.data.dialect.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from evpil.data.dialect import (  # noqa: F401  (re-exported for callers)
    DEFAULT_DIALECT, KMH_TO_MPS, PERCENT_TO_FRAC, Dialect, canonicalise, read_raw,
)

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
    path = Path(path)
    try:
        return canonicalise(read_raw(path, dialect), mapping, dialect)
    except KeyError as exc:
        raise KeyError(f"{path.name}: {exc.args[0]}") from None


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
