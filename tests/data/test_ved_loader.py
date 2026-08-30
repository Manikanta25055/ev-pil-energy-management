"""VED loader: the archive's quirks must be handled, not assumed away."""

import numpy as np
import pandas as pd
import pytest

from evpil.data.schema import CANONICAL_COLUMNS
from evpil.data.ved_loader import (
    BEV_VEH_IDS, SOURCE_COLUMNS, VED_DIALECT, VED_MAPPING, extract_bev_subset,
    load_bev_trips, raw_trips,
)

N = 300
DT_MS = 400


def _block(veh_id=10, trip=1, n=N, **overrides):
    """One synthetic trip in VED's raw form: ms timestamps, km/h, watts."""
    data = {
        "DayNum": np.linspace(1.0, 1.1, n),
        "VehId": np.full(n, veh_id),
        "Trip": np.full(n, trip),
        "Timestamp(ms)": np.arange(n) * DT_MS,
        "Latitude[deg]": np.full(n, 42.28),
        "Longitude[deg]": np.full(n, -83.74),
        "Vehicle Speed[km/h]": np.full(n, 36.0),
        "OAT[DegC]": np.full(n, 12.0),
        "Air Conditioning Power[Watts]": np.full(n, 300.0),
        "Heater Power[Watts]": np.full(n, 700.0),
        "HV Battery Current[A]": np.full(n, -40.0),
        "HV Battery SOC[%]": np.linspace(80.0, 70.0, n),
        "HV Battery Voltage[V]": np.full(n, 380.0),
    }
    data.update(overrides)
    return pd.DataFrame(data)


def _weekly(tmp_path, *blocks, name="VED_171101_week.csv"):
    root = tmp_path / "csv"
    root.mkdir(exist_ok=True)
    pd.concat(blocks, ignore_index=True).to_csv(root / name, index=False)
    return root


def test_only_the_three_bev_vehicles_are_kept(tmp_path):
    """383 vehicles are logged; 3 of them are battery-electric."""
    root = _weekly(tmp_path, _block(veh_id=10), _block(veh_id=77),
                   _block(veh_id=455, trip=2))
    raw = extract_bev_subset(root)
    assert sorted(raw.VehId.unique()) == [10, 455]
    assert 77 not in raw.VehId.values


def test_bev_ids_come_from_the_static_sheet():
    assert BEV_VEH_IDS == (10, 455, 541)


def test_source_columns_exclude_the_engine_channels():
    """A 3 GB fleet-wide scan should not carry fuel trims it never uses."""
    assert not any("Fuel Trim" in c for c in SOURCE_COLUMNS)
    assert "OAT[DegC]" in SOURCE_COLUMNS


def test_mapping_uses_the_files_name_not_the_readme_name():
    """The repository README calls it 'Outside Air Temperature[DegC]'."""
    assert "OAT[DegC]" in VED_MAPPING
    assert "Outside Air Temperature[DegC]" not in VED_MAPPING


def test_load_produces_the_canonical_columns(tmp_path):
    root = _weekly(tmp_path, _block())
    df = load_bev_trips(root)
    assert tuple(df.columns[: len(CANONICAL_COLUMNS)]) == CANONICAL_COLUMNS
    assert "trip_id" in df.columns


def test_timestamps_become_seconds_from_trip_start(tmp_path):
    df = load_bev_trips(_weekly(tmp_path, _block()))
    assert df["t_s"].iloc[0] == pytest.approx(0.0)
    assert df["t_s"].iloc[1] == pytest.approx(DT_MS / 1000.0)


def test_battery_current_is_negated(tmp_path):
    """VED logs discharge negative; the canonical schema is discharge positive."""
    df = load_bev_trips(_weekly(tmp_path, _block()))
    assert df["i_batt_a"].iloc[0] == pytest.approx(40.0)
    assert (df["v_batt_v"] * df["i_batt_a"]).iloc[0] > 0     # discharging


def test_aux_sums_heater_and_air_conditioning_in_watts(tmp_path):
    """Both channels are already watts here, unlike the i3 archive's kilowatts."""
    df = load_bev_trips(_weekly(tmp_path, _block()))
    assert df["p_aux_w"].iloc[0] == pytest.approx(1000.0)


def test_absent_elevation_gives_zero_grade(tmp_path):
    df = load_bev_trips(_weekly(tmp_path, _block()))
    assert (df["elevation_m"] == 0.0).all()
    assert (df["grade_rad"] == 0.0).all()


def test_absent_battery_temperature_falls_back_to_ambient(tmp_path):
    df = load_bev_trips(_weekly(tmp_path, _block()))
    assert df["t_batt_c"].equals(df["t_ambient_c"])


def test_speed_converted_to_mps(tmp_path):
    df = load_bev_trips(_weekly(tmp_path, _block()))
    assert df["v_mps"].iloc[0] == pytest.approx(10.0)


def test_soc_converted_to_fraction(tmp_path):
    df = load_bev_trips(_weekly(tmp_path, _block()))
    assert df["soc_frac"].iloc[0] == pytest.approx(0.80)


def test_trip_id_identifies_vehicle_and_trip(tmp_path):
    root = _weekly(tmp_path, _block(veh_id=10, trip=3),
                   _block(veh_id=455, trip=9))
    df = load_bev_trips(root)
    assert set(df.trip_id.unique()) == {"VED_10_3", "VED_455_9"}


def test_trips_are_kept_separate(tmp_path):
    """Two trips must not be concatenated into one time series."""
    root = _weekly(tmp_path, _block(veh_id=10, trip=1),
                   _block(veh_id=10, trip=2))
    df = load_bev_trips(root)
    for _, g in df.groupby("trip_id"):
        assert g["t_s"].iloc[0] == pytest.approx(0.0)
        assert g["t_s"].is_monotonic_increasing


def test_trip_ids_filter_the_load(tmp_path):
    root = _weekly(tmp_path, _block(veh_id=10, trip=1),
                   _block(veh_id=455, trip=1))
    df = load_bev_trips(root, trip_ids=["VED_455_1"])
    assert set(df.trip_id.unique()) == {"VED_455_1"}


def test_a_speed_dropout_cannot_smear_across_neighbours(tmp_path):
    """One bad sample is bounded before smoothing, so it stays local."""
    v = np.full(N, 36.0)
    v[150] = 0.0                     # 10 m/s lost in 0.4 s: a dropout
    df = load_bev_trips(_weekly(tmp_path, _block(**{"Vehicle Speed[km/h]": v})))
    a = df["a_mps2"].to_numpy()
    assert np.abs(a).max() <= VED_DIALECT.max_accel_mps2 + 1e-9
    assert np.abs(a[:140]).max() == pytest.approx(0.0, abs=1e-9)


def test_aux_spike_is_clipped(tmp_path):
    heat = np.full(N, 700.0)
    heat[10] = 90_000.0
    df = load_bev_trips(_weekly(tmp_path, _block(**{"Heater Power[Watts]": heat})))
    assert df["p_aux_w"].max() == pytest.approx(8000.0)


def test_cache_is_written_and_reused(tmp_path):
    root = _weekly(tmp_path, _block())
    cache = tmp_path / "bev.pkl"
    load_bev_trips(root, cache=cache)
    assert cache.exists()
    # Remove the source; the cached subset must still load.
    for f in root.glob("*.csv"):
        f.unlink()
    assert len(load_bev_trips(root, cache=cache)) == N


def test_missing_weekly_files_raise(tmp_path):
    (tmp_path / "csv").mkdir()
    with pytest.raises(FileNotFoundError):
        extract_bev_subset(tmp_path / "csv")


def test_raw_trips_yields_sorted_blocks(tmp_path):
    b = _block()
    shuffled = b.sample(frac=1.0, random_state=0)
    pairs = list(raw_trips(shuffled))
    assert len(pairs) == 1
    tid, block = pairs[0]
    assert tid == "VED_10_1"
    assert block["Timestamp(ms)"].is_monotonic_increasing


# --- DEM-supplied elevation --------------------------------------------------

from evpil.data.dem import DEM  # noqa: E402
from evpil.data.ved_loader import GRADE_BASELINE_M, VED_DEM_DIALECT  # noqa: E402


LAT_REF = 42.25          # where the synthetic trips start
M_PER_DEG_LAT = 111_320.0


def _ramp_dem(slope=0.0, base=250.0):
    """A DEM over the test coordinates that rises `slope` metres per metre north.

    `slope=0.02` is a 2% climb for a vehicle driving north, so a trip heading
    north across it must come back with a grade of arcsin(0.02).
    """
    lat_n, lon_n = 400, 400
    lat_step, lon_step = -0.001, 0.001
    north, west = 42.40, -83.90
    lats = north + np.arange(lat_n) * lat_step
    z = base + (lats - LAT_REF) * M_PER_DEG_LAT * slope
    grid = np.repeat(z[:, None], lon_n, axis=1)
    return DEM(elevation=grid, west=west, north=north,
               lon_step=lon_step, lat_step=lat_step)


def test_dem_supplies_the_elevation_ved_does_not_log(tmp_path):
    df = load_bev_trips(_weekly(tmp_path, _block()), dem=_ramp_dem())
    assert df["elevation_m"].iloc[0] == pytest.approx(250.0, abs=1e-6)
    assert not (df["elevation_m"] == 0.0).all()


def test_without_a_dem_elevation_stays_constant_and_grade_zero(tmp_path):
    df = load_bev_trips(_weekly(tmp_path, _block()))
    assert (df["elevation_m"] == 0.0).all()
    assert (df["grade_rad"] == 0.0).all()


def test_flat_terrain_still_gives_zero_grade_with_a_dem(tmp_path):
    df = load_bev_trips(_weekly(tmp_path, _block()), dem=_ramp_dem())
    assert df["grade_rad"].abs().max() == pytest.approx(0.0, abs=1e-9)


def test_a_climb_produces_a_positive_grade(tmp_path):
    """Drive north up a 2% slope; the derived gradient must find it."""
    n = 1200
    # 10 m/s north for 480 s covers 4.8 km, well past the 200 m baseline.
    lat = 42.25 + np.arange(n) * (10.0 * (DT_MS / 1000.0)) / 111_320.0
    block = _block(n=n, **{"Latitude[deg]": lat,
                           "Vehicle Speed[km/h]": np.full(n, 36.0)})
    df = load_bev_trips(_weekly(tmp_path, block), dem=_ramp_dem(slope=0.02))
    mid = df["grade_rad"].iloc[n // 3: 2 * n // 3]
    assert mid.mean() == pytest.approx(np.arcsin(0.02), rel=0.05)


def test_a_descent_produces_a_negative_grade(tmp_path):
    n = 1200
    lat = 42.25 + np.arange(n) * (10.0 * (DT_MS / 1000.0)) / 111_320.0
    block = _block(n=n, **{"Latitude[deg]": lat})
    df = load_bev_trips(_weekly(tmp_path, block), dem=_ramp_dem(slope=-0.02))
    assert df["grade_rad"].iloc[n // 3: 2 * n // 3].mean() < -0.015


def test_grade_uses_a_distance_baseline_not_a_sample_window():
    assert VED_DEM_DIALECT.grade_distance_m == GRADE_BASELINE_M
    assert VED_DEM_DIALECT.constant_columns == ()


def test_a_stationary_vehicle_does_not_advance_the_grade_baseline(tmp_path):
    """Distance comes from speed, so GPS jitter at a standstill cannot move it."""
    n = 600
    v = np.full(n, 36.0)
    v[200:400] = 0.0                      # parked in the middle of the trip
    lat = 42.25 + np.cumsum(v / 3.6 * (DT_MS / 1000.0)) / 111_320.0
    block = _block(n=n, **{"Vehicle Speed[km/h]": v, "Latitude[deg]": lat})
    df = load_bev_trips(_weekly(tmp_path, block), dem=_ramp_dem(slope=0.02))
    stopped = df["grade_rad"].iloc[210:390]
    assert np.isfinite(stopped).all()
    assert stopped.abs().max() < 0.35      # never leaves the schema's bound
