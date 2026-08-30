import pandas as pd
import pytest
from evpil.data.i3_loader import load_all_trips, load_trip
from evpil.data.schema import CANONICAL_COLUMNS

MAPPING = {
    "Time [s]": "t_s",
    "Velocity [km/h]": "v_mps",
    "SoC [%]": "soc_frac",
    "Battery Current [A]": "i_batt_a",
    "Battery Voltage [V]": "v_batt_v",
    "Ambient Temperature [C]": "t_ambient_c",
    "Battery Temperature [C]": "t_batt_c",
    "Elevation [m]": "elevation_m",
    "Heating Power [W]": "p_aux_w",
}


@pytest.fixture
def raw_csv(tmp_path):
    """A file in the archive's *raw* form: km/h, percent SoC, no derived columns."""
    df = pd.DataFrame({
        "Time [s]": [0.0, 0.1, 0.2, 0.3, 0.4],
        "Velocity [km/h]": [0.0, 36.0, 72.0, 72.0, 36.0],
        "SoC [%]": [80.0, 79.9, 79.8, 79.7, 79.6],
        "Battery Current [A]": [0.0, 10.0, 20.0, 20.0, -5.0],
        "Battery Voltage [V]": [350.0, 349.0, 348.0, 348.0, 351.0],
        "Ambient Temperature [C]": [20.0] * 5,
        "Battery Temperature [C]": [25.0] * 5,
        "Elevation [m]": [100.0, 100.0, 100.5, 101.0, 101.0],
        "Heating Power [W]": [500.0] * 5,
    })
    p = tmp_path / "TripA01.csv"
    df.to_csv(p, index=False)
    return p


def test_load_trip_produces_canonical_columns(raw_csv):
    df = load_trip(raw_csv, MAPPING)
    assert tuple(df.columns[: len(CANONICAL_COLUMNS)]) == CANONICAL_COLUMNS


def test_velocity_converted_to_mps(raw_csv):
    df = load_trip(raw_csv, MAPPING)
    # 36 km/h == 10 m/s
    assert df["v_mps"].tolist() == pytest.approx([0.0, 10.0, 20.0, 20.0, 10.0])


def test_soc_converted_to_fraction(raw_csv):
    df = load_trip(raw_csv, MAPPING)
    assert df["soc_frac"].iloc[0] == pytest.approx(0.80)


def test_acceleration_derived_from_velocity(raw_csv):
    df = load_trip(raw_csv, MAPPING)
    # First sample is backfilled from the second; 0 -> 10 m/s over 0.1 s is 100 m/s^2.
    assert df["a_mps2"].iloc[1] == pytest.approx(100.0, rel=1e-6)
    assert df["a_mps2"].iloc[3] == pytest.approx(0.0, abs=1e-9)


def test_grade_derived_from_elevation(raw_csv):
    df = load_trip(raw_csv, MAPPING)
    # Sample 2: elevation rises 0.5 m while 20 m/s * 0.1 s = 2.0 m of road is
    # covered. v*dt is distance along the road surface, so sin(theta) = dz/ds
    # and theta = arcsin(0.25) = 0.25268026 rad.
    assert df["grade_rad"].iloc[2] == pytest.approx(0.25268026, rel=1e-5)


def test_grade_is_zero_when_stationary(raw_csv):
    df = load_trip(raw_csv, MAPPING)
    assert df["grade_rad"].iloc[0] == pytest.approx(0.0)


def test_load_all_trips_tags_trip_id(raw_csv):
    df = load_all_trips(raw_csv.parent, MAPPING)
    assert set(df["trip_id"].unique()) == {"TripA01"}
    assert len(df) == 5


# --- archive dialect ---------------------------------------------------------

from evpil.data.i3_loader import Dialect, load_trip as _load_trip  # noqa: E402


def _dialect_csv(tmp_path, **overrides):
    """A raw file in the i3 archive's own form: semicolon, cp1252, degrees."""
    data = {
        "Time [s]": [0.0, 0.1, 0.2, 0.3, 0.4],
        "Velocity [km/h]": [36.0, 36.0, 36.0, 36.0, 36.0],
        "SoC [%]": [80.0, 79.9, 79.8, 79.7, 79.6],
        "Battery Current [A]": [-20.0, -20.0, -20.0, -20.0, 5.0],
        "Battery Voltage [V]": [350.0] * 5,
        "Ambient Temperature [°C]": [5.0] * 5,
        "Battery Temperature [°C]": [10.0] * 5,
        "Elevation [m]": [100.0] * 5,
        "Heating Power CAN [kW]": [2.0] * 5,
        "AirCon Power [kW]": [0.5] * 5,
    }
    data.update(overrides)
    p = tmp_path / "TripB01.csv"
    pd.DataFrame(data).to_csv(p, sep=";", encoding="cp1252", index=False)
    return p


_ARCHIVE_MAP = {
    "Time [s]": "t_s", "Velocity [km/h]": "v_mps", "SoC [%]": "soc_frac",
    "Battery Current [A]": "i_batt_a", "Battery Voltage [V]": "v_batt_v",
    "Ambient Temperature [°C]": "t_ambient_c",
    "Battery Temperature [°C]": "t_batt_c", "Elevation [m]": "elevation_m",
}
_D = Dialect(sep=";", encoding="cp1252", negate=("i_batt_a",),
             sum_into=(("p_aux_w", ("Heating Power CAN [kW]",
                                    "AirCon Power [kW]"), 1000.0),),
             clip=(("p_aux_w", 0.0, 10000.0),), max_gap_samples=100,
             max_soc_step=0.01)


def test_dialect_reads_semicolons_and_cp1252(tmp_path):
    df = _load_trip(_dialect_csv(tmp_path), _ARCHIVE_MAP, _D)
    assert len(df) == 5
    assert df["t_ambient_c"].iloc[0] == pytest.approx(5.0)


def test_dialect_negates_battery_current(tmp_path):
    """The archive logs discharge negative; canonical is discharge positive."""
    df = _load_trip(_dialect_csv(tmp_path), _ARCHIVE_MAP, _D)
    assert df["i_batt_a"].iloc[0] == pytest.approx(20.0)
    assert df["i_batt_a"].iloc[4] == pytest.approx(-5.0)


def test_dialect_composes_aux_from_heater_and_aircon(tmp_path):
    df = _load_trip(_dialect_csv(tmp_path), _ARCHIVE_MAP, _D)
    assert df["p_aux_w"].iloc[0] == pytest.approx(2500.0)


def test_dialect_clips_an_aux_spike(tmp_path):
    p = _dialect_csv(tmp_path, **{"Heating Power CAN [kW]": [2.0, 40.0, 2.0, 2.0, 2.0]})
    df = _load_trip(p, _ARCHIVE_MAP, _D)
    assert df["p_aux_w"].max() == pytest.approx(10000.0)


def test_dialect_repairs_an_impossible_soc_step(tmp_path):
    """A 79.7 -> 0.0 drop in 0.1 s is a dropout, not a discharge."""
    p = _dialect_csv(tmp_path, **{"SoC [%]": [80.0, 79.9, 79.8, 79.7, 0.0]})
    df = _load_trip(p, _ARCHIVE_MAP, _D)
    assert df["soc_frac"].iloc[4] == pytest.approx(0.797)


def test_dialect_keeps_a_plausible_soc_step(tmp_path):
    p = _dialect_csv(tmp_path, **{"SoC [%]": [80.0, 79.9, 79.8, 79.7, 79.5]})
    df = _load_trip(p, _ARCHIVE_MAP, _D)
    assert df["soc_frac"].iloc[4] == pytest.approx(0.795)
