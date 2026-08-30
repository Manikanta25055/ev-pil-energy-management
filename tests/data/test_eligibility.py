"""The eligibility rule must reject for the stated reason, not by accident."""

import numpy as np
import pandas as pd
import pytest

from evpil.data.eligibility import (
    MAX_HEATER_MAE_W, MAX_SOC_GAP_FRAC, MIN_HEATER_CORR, assess_all, assess_trip,
)

N = 400


def _raw(tmp_path, name="TripB01", *, soc=None, heat_can=None, heat_lin=None):
    """A synthetic file in the archive's raw form: semicolon, cp1252, degrees."""
    rng = np.random.default_rng(0)
    if soc is None:
        soc = np.linspace(80.0, 60.0, N)              # falls: discharging
    if heat_can is None:
        heat_can = np.abs(rng.normal(2.0, 0.3, N))    # kW
    if heat_lin is None:
        heat_lin = heat_can * 1000.0 + rng.normal(0, 20, N)   # W, agrees

    df = pd.DataFrame({
        "Time [s]": np.arange(N) * 0.1,
        "Velocity [km/h]": np.full(N, 50.0),
        "Elevation [m]": np.full(N, 500.0),
        "SoC [%]": soc,
        "Battery Current [A]": np.full(N, -40.0),
        "Battery Voltage [V]": np.full(N, 360.0),
        "Ambient Temperature [°C]": np.full(N, 5.0),
        "Battery Temperature [°C]": np.full(N, 10.0),
        "Heating Power CAN [kW]": heat_can,
        "Heating Power LIN [W]": heat_lin,
        "AirCon Power [kW]": np.zeros(N),
    })
    p = tmp_path / f"{name}.csv"
    df.to_csv(p, sep=";", encoding="cp1252", index=False)
    return p


def test_clean_trip_is_eligible(tmp_path):
    v = assess_trip(_raw(tmp_path))
    assert v.eligible, v.reason
    assert v.reason == "eligible"


def test_rejects_trip_with_soc_dropout(tmp_path):
    soc = np.linspace(80.0, 60.0, N)
    soc[100:200] = np.nan                       # 25% missing, well over the 1% bar
    v = assess_trip(_raw(tmp_path, soc=soc))
    assert not v.eligible
    assert "SoC missing" in v.reason
    assert v.soc_gap_frac > MAX_SOC_GAP_FRAC


def test_accepts_soc_gap_below_threshold(tmp_path):
    soc = np.linspace(80.0, 60.0, N)
    soc[:2] = np.nan                            # 0.5%, the real archive's head gap
    assert assess_trip(_raw(tmp_path, soc=soc)).eligible


def test_rejects_trip_containing_charging(tmp_path):
    v = assess_trip(_raw(tmp_path, soc=np.linspace(40.0, 70.0, N)))
    assert not v.eligible
    assert "charging" in v.reason
    assert v.soc_net_pp > 0


def test_rejects_heater_without_corroborating_channel(tmp_path):
    v = assess_trip(_raw(tmp_path, heat_lin=np.zeros(N)))
    assert not v.eligible
    assert "no independent LIN measurement" in v.reason


def test_rejects_uncorrelated_heater_channels(tmp_path):
    rng = np.random.default_rng(1)
    v = assess_trip(_raw(tmp_path, heat_lin=rng.uniform(0, 4000, N)))
    assert not v.eligible
    assert v.heater_corr < MIN_HEATER_CORR


def test_rejects_correlated_but_offset_heater_channels(tmp_path):
    """Perfectly correlated yet biased by 500 W: r passes, MAE must catch it."""
    can = np.linspace(0.5, 4.0, N)
    v = assess_trip(_raw(tmp_path, heat_can=can, heat_lin=can * 1000.0 + 500.0))
    assert not v.eligible
    assert v.heater_corr > MIN_HEATER_CORR
    assert v.heater_mae_w > MAX_HEATER_MAE_W
    assert "disagree" in v.reason


def test_assess_all_covers_every_trip_file(tmp_path):
    _raw(tmp_path, "TripB01")
    _raw(tmp_path, "TripB02", soc=np.linspace(40.0, 70.0, N))
    out = assess_all(tmp_path)
    assert len(out) == 2
    assert set(out.trip_id) == {"TripB01", "TripB02"}
    assert out.eligible.tolist() == [True, False]


def test_verdict_reports_a_reason_even_when_eligible(tmp_path):
    assert assess_trip(_raw(tmp_path)).reason
