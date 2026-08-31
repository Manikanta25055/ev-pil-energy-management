import numpy as np
import pytest

from evpil.control import cycles


def _needs_cycles():
    if not cycles.available():
        pytest.skip("driving cycles not downloaded; run scripts/build_cycles.py")


def test_the_published_cycles_match_their_documented_distances():
    """Each regulatory cycle has a published distance. Wrong units, a dropped
    tail or a misread column would all show up here and nowhere else."""
    _needs_cycles()
    expected_km = {"udds": 11.99, "hwfet": 16.51, "us06": 12.89,
                   "ftp75": 17.77, "wltc3b": 23.27}
    for name, km in expected_km.items():
        t_s, v = cycles.load_raw(name)
        assert np.trapezoid(v, t_s) / 1000.0 == pytest.approx(km, abs=0.05)


def test_resampling_preserves_distance_and_peak_speed():
    _needs_cycles()
    t_s, v = cycles.load_raw("udds")
    raw_km = np.trapezoid(v, t_s) / 1000.0

    c = cycles.load_cycle("udds", dt_s=0.01)
    assert c.dt_s == 0.01
    assert c.distance_m / 1000.0 == pytest.approx(raw_km, rel=1e-3)
    assert c.v_ref_mps.max() == pytest.approx(v.max(), rel=1e-6)


def test_resampling_interpolates_rather_than_holding():
    """A zero-order hold would put a step between every published sample, which
    asks the tracker for an unbounded acceleration once a second."""
    _needs_cycles()
    c = cycles.load_cycle("us06", dt_s=0.01)
    a = np.diff(c.v_ref_mps) / c.dt_s
    assert np.abs(a).max() < 6.0        # m/s^2; a hold would be enormous


def test_grade_profiles_have_the_shapes_they_claim():
    n, dt = 1000, 0.01
    assert np.all(cycles.grade_profile(n, dt, "flat") == 0.0)

    sine = cycles.grade_profile(n, dt, "sine", 0.05, period_s=10.0)
    assert sine.max() == pytest.approx(0.05, rel=1e-2)
    # A full number of periods returns to the starting elevation, so a sine
    # profile does not quietly add or remove potential energy from a trip.
    assert sine.mean() == pytest.approx(0.0, abs=1e-3)

    ramp = cycles.grade_profile(n, dt, "ramp", 0.04)
    assert set(np.unique(np.round(ramp, 6))) == {-0.04, 0.04}

    with pytest.raises(ValueError, match="unknown grade profile"):
        cycles.grade_profile(n, dt, "spiral")


def test_a_missing_cycle_says_how_to_get_it(tmp_path):
    with pytest.raises(FileNotFoundError, match="build_cycles"):
        cycles.load_raw("nonesuch", cycle_dir=tmp_path)
