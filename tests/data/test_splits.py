import numpy as np
import pandas as pd
import pytest
from evpil.data.splits import Split, apply_split, assert_no_trip_overlap, make_trip_splits


def _df(n_trips: int = 20, rows: int = 50) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    parts = []
    for i in range(n_trips):
        parts.append(pd.DataFrame({
            "trip_id": [f"T{i:02d}"] * rows,
            "t_s": np.arange(rows) * 0.1,
            "t_ambient_c": [float(rng.integers(-5, 35))] * rows,
            "v_mps": rng.normal(15, 3, rows),
        }))
    return pd.concat(parts, ignore_index=True)


def test_split_covers_every_trip_exactly_once():
    df = _df()
    s = make_trip_splits(df, seed=42)
    allocated = s.train + s.val + s.test
    assert sorted(allocated) == sorted(df.trip_id.unique())
    assert len(allocated) == len(set(allocated))


def test_split_is_deterministic_for_a_seed():
    df = _df()
    assert make_trip_splits(df, seed=7) == make_trip_splits(df, seed=7)


def test_different_seeds_give_different_splits():
    df = _df()
    assert make_trip_splits(df, seed=1) != make_trip_splits(df, seed=2)


def test_split_respects_requested_fractions():
    df = _df(n_trips=20)
    s = make_trip_splits(df, seed=0, val_frac=0.2, test_frac=0.2)
    assert len(s.val) == 4
    assert len(s.test) == 4
    assert len(s.train) == 12


def test_apply_split_yields_disjoint_row_sets():
    df = _df()
    s = make_trip_splits(df, seed=3)
    tr, va, te = apply_split(df, s)

    assert set(tr.trip_id) & set(va.trip_id) == set()
    assert set(tr.trip_id) & set(te.trip_id) == set()
    assert set(va.trip_id) & set(te.trip_id) == set()
    assert len(tr) + len(va) + len(te) == len(df)


def test_overlap_assertion_catches_a_bad_split():
    bad = Split(train=["A", "B"], val=["B"], test=["C"])
    with pytest.raises(AssertionError, match="overlap"):
        assert_no_trip_overlap(bad)


def test_stratification_spreads_temperature_across_splits():
    df = _df(n_trips=30)
    s = make_trip_splits(df, seed=11)

    def mean_temp(trips):
        return df[df.trip_id.isin(trips)].t_ambient_c.mean()

    # Stratified sampling should keep split means near the overall mean.
    overall = df.t_ambient_c.mean()
    for trips in (s.train, s.val, s.test):
        assert abs(mean_temp(trips) - overall) < 8.0
