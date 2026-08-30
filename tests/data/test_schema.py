import pandas as pd
import pytest
from evpil.data.schema import CANONICAL_COLUMNS, SchemaError, validate_frame


# A physically plausible row. An all-zeros frame would violate the validator's
# own v_batt_v range and t_s monotonicity rules, so it cannot serve as the
# "good" fixture.
_VALID_ROW = {
    "t_s": 0.0, "v_mps": 10.0, "a_mps2": 0.0, "soc_frac": 0.6,
    "i_batt_a": 20.0, "v_batt_v": 350.0, "t_ambient_c": 20.0,
    "t_batt_c": 25.0, "elevation_m": 100.0, "grade_rad": 0.0, "p_aux_w": 500.0,
}


def _good_frame(n: int = 5) -> pd.DataFrame:
    df = pd.DataFrame({c: [_VALID_ROW[c]] * n for c in CANONICAL_COLUMNS})
    df["t_s"] = [i * 0.1 for i in range(n)]   # must be strictly monotonic
    return df


def test_canonical_columns_are_stable():
    assert CANONICAL_COLUMNS == (
        "t_s", "v_mps", "a_mps2", "soc_frac", "i_batt_a", "v_batt_v",
        "t_ambient_c", "t_batt_c", "elevation_m", "grade_rad", "p_aux_w",
    )


def test_validate_accepts_good_frame():
    validate_frame(_good_frame())


def test_validate_rejects_missing_column():
    df = _good_frame().drop(columns=["soc_frac"])
    with pytest.raises(SchemaError, match="missing"):
        validate_frame(df)


def test_validate_rejects_nan():
    df = _good_frame()
    df.loc[2, "v_mps"] = float("nan")
    with pytest.raises(SchemaError, match="NaN"):
        validate_frame(df)


def test_validate_rejects_soc_out_of_range():
    df = _good_frame()
    df.loc[1, "soc_frac"] = 1.4
    with pytest.raises(SchemaError, match="soc_frac"):
        validate_frame(df)


def test_validate_rejects_non_monotonic_time():
    df = _good_frame()
    df["t_s"] = [0.0, 0.1, 0.05, 0.3, 0.4]
    with pytest.raises(SchemaError, match="monotonic"):
        validate_frame(df)
