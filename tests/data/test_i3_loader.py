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
