"""The VED eligibility rule must reject for the stated reason, not by accident."""

import numpy as np
import pandas as pd
import pytest

from evpil.data.ved_eligibility import (
    MAX_GAP_S, MIN_DURATION_S, MIN_SAMPLES, assess_all, assess_trip,
    eligible_trip_ids,
)
from evpil.data.ved_loader import raw_trips

N = 500
DT_MS = 400


def _block(veh_id=10, trip=1, n=N, **overrides):
    data = {
        "VehId": np.full(n, veh_id),
        "Trip": np.full(n, trip),
        "Timestamp(ms)": np.arange(n) * DT_MS,
        "Vehicle Speed[km/h]": np.full(n, 36.0),
        "OAT[DegC]": np.full(n, 12.0),
        "HV Battery SOC[%]": np.linspace(80.0, 70.0, n),
    }
    data.update(overrides)
    return pd.DataFrame(data)


def _verdict(**overrides):
    return assess_trip("VED_10_1", _block(**overrides))


def test_clean_trip_is_eligible():
    v = _verdict()
    assert v.eligible, v.reason
    assert v.reason == "eligible"


def test_rejects_a_trip_with_too_few_samples():
    v = _verdict(n=MIN_SAMPLES - 1)
    assert not v.eligible
    assert "samples" in v.reason


def test_rejects_a_trip_that_is_too_short():
    """120 samples at 400 ms is 47.6 s, under the 120 s floor."""
    v = _verdict(n=120)
    assert not v.eligible
    assert "lasts" in v.reason
    assert v.duration_s < MIN_DURATION_S


def test_rejects_a_trip_containing_a_long_logging_gap():
    ts = np.arange(N) * DT_MS
    ts[150:] += int((MAX_GAP_S + 30) * 1000)     # a minute of nothing
    v = _verdict(**{"Timestamp(ms)": ts})
    assert not v.eligible
    assert "gap" in v.reason
    assert v.max_gap_s > MAX_GAP_S


def test_accepts_a_gap_below_the_threshold():
    ts = np.arange(N) * DT_MS
    ts[150:] += int((MAX_GAP_S - 10) * 1000)
    assert _verdict(**{"Timestamp(ms)": ts}).eligible


def test_rejects_a_trip_that_barely_moves():
    v = _verdict(**{"Vehicle Speed[km/h]": np.full(N, 0.5)})
    assert not v.eligible
    assert "km" in v.reason


def test_rejects_a_trip_containing_charging():
    v = _verdict(**{"HV Battery SOC[%]": np.linspace(40.0, 70.0, N)})
    assert not v.eligible
    assert "charging" in v.reason
    assert v.soc_net_pp > 0


def test_reports_measured_quantities_even_when_rejecting():
    v = _verdict(n=MIN_SAMPLES - 1)
    assert v.n == MIN_SAMPLES - 1
    assert np.isfinite(v.distance_km)
    assert np.isfinite(v.mean_oat_c)


def test_assess_all_covers_every_trip():
    raw = pd.concat([_block(trip=1), _block(trip=2, n=10)], ignore_index=True)
    out = assess_all(raw)
    assert len(out) == 2
    assert out.set_index("trip_id").eligible.to_dict() == {
        "VED_10_1": True, "VED_10_2": False}


def test_eligible_trip_ids_returns_only_the_survivors():
    raw = pd.concat([_block(trip=1), _block(trip=2, n=10)], ignore_index=True)
    assert eligible_trip_ids(raw) == ["VED_10_1"]
