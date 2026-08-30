import numpy as np
import pytest
from evpil.data.guards import (
    LeakageError,
    assert_disjoint_groups,
    audit_features,
    shuffled_label_control,
)


def test_audit_passes_for_clean_feature_set():
    audit_features(
        feature_cols=["v_mps", "a_mps2", "soc_frac"],
        target_col="p_batt_w",
        forbidden={"p_batt_w": ["v_batt_v", "i_batt_a"]},
    )


def test_audit_rejects_target_as_its_own_feature():
    with pytest.raises(LeakageError, match="target"):
        audit_features(
            feature_cols=["v_mps", "p_batt_w"],
            target_col="p_batt_w",
            forbidden={},
        )


def test_audit_rejects_declared_derived_feature():
    """This is exactly defect D5: Range was a feature and Range came from speed."""
    with pytest.raises(LeakageError, match="i_batt_a"):
        audit_features(
            feature_cols=["v_mps", "i_batt_a"],
            target_col="p_batt_w",
            forbidden={"p_batt_w": ["v_batt_v", "i_batt_a"]},
        )


def test_shuffled_label_control_collapses_for_an_honest_model():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(400, 4))
    y = X @ np.array([1.0, -2.0, 0.5, 3.0])

    def fit_fn(Xtr, ytr, Xte):
        coef, *_ = np.linalg.lstsq(Xtr, ytr, rcond=None)
        return Xte @ coef

    r2 = shuffled_label_control(fit_fn, X, y, seed=0)
    assert r2 < 0.1, f"shuffled-label R2 was {r2:.3f}; expected near zero"


def test_shuffled_label_control_would_detect_leakage():
    """Sanity check on the R2 computation itself.

    A fit_fn with oracle access to the shuffled holdout targets must score near
    1.0. If it did not, the control could not detect leakage when it mattered.
    """
    rng = np.random.default_rng(1)
    X = rng.normal(size=(200, 3))
    y = rng.normal(size=200)

    # Reproduce the guard's internal shuffle (same seed) to obtain y_te.
    y_shuffled = np.array(y, copy=True)
    np.random.default_rng(0).shuffle(y_shuffled)
    y_te = y_shuffled[-50:]          # holdout_frac 0.25 of 200 rows

    def oracle_fit(Xtr, ytr, Xte):
        return y_te

    r2 = shuffled_label_control(oracle_fit, X, y, seed=0)
    assert r2 > 0.99, "an oracle model must score high, or the control is blind"


def test_disjoint_groups_passes_when_no_trip_is_shared():
    assert_disjoint_groups(
        train=["TripB01", "TripB02"], val=["TripB03"], test=["TripB05"]
    )


def test_disjoint_groups_names_the_trip_and_both_splits_it_landed_in():
    with pytest.raises(LeakageError, match="'TripB03' in both 'train' and 'val'"):
        assert_disjoint_groups(
            train=["TripB01", "TripB03"], val=["TripB03"], test=["TripB05"]
        )


def test_disjoint_groups_tolerates_repeats_within_one_split():
    # Windowed tensors carry one group label per window, so a trip appears
    # thousands of times inside its own split. That is not a collision.
    assert_disjoint_groups(train=["TripB01"] * 500, val=["TripB03"] * 200)
