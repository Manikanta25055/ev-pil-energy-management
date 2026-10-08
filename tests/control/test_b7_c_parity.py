"""B7 on the board must be the B7 that was evaluated.

The detector is written twice, in Python for the simulation and in C for the
chip. This drives both with the same samples and compares them step for
step: the estimate, the dead-reckoned speed, the offset estimate, and above
all the flag. A flag that goes up one step apart is a different detector.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from evpil.control.speed_estimators import (
    BiasAwareFaultKalman, BiasAwareSettings,
)
from tests.control.b7_drive import FAULTS, N, drive, run_c

# float32 on the chip against float64 here, as in test_c_parity.py.
REL = 2e-5
ABS = 2e-3


SEEN: set = set()


@pytest.mark.parametrize("seed,noise_x", [(0, 1.0), (3, 10.0), (5, 1.0)])
def test_the_c_b7_matches_the_python_one(params, tmp_path, seed, noise_x):
    v, a, tq = drive(seed, noise_x)
    got = run_c("b7", v, a, tq, tmp_path)
    assert got.shape[0] == N
    est = BiasAwareFaultKalman(params, q_mps=0.002, q_d_mps2=0.02)
    for n in range(N):
        want = est.step(v_meas_mps=v[n], a_meas_mps2=a[n],
                        torque_prev_nm=tq[n], grade_rad=0.0, dt_s=0.01)
        g_est, g_flag, g_alarms, g_clears, g_dr, g_b, g_test = got[n][:7]
        assert bool(g_flag) == est.flagged, f"flag at step {n}"
        assert int(g_alarms) == len(est.alarm_steps), f"alarms at step {n}"
        assert int(g_clears) == len(est.clear_steps), f"clears at step {n}"
        assert g_est == pytest.approx(want, rel=REL, abs=ABS), f"estimate, {n}"
        assert g_dr == pytest.approx(est._v_dr, rel=REL, abs=ABS), f"v_dr, {n}"
        assert g_b == pytest.approx(est.accel_offset_mps2, rel=REL, abs=ABS), \
            f"offset estimate at step {n}"
        if est.alarm_tests:
            assert int(g_test) == est.alarm_tests[-1], f"test at step {n}"

    # The drive has to exercise what it claims to: every fault flagged
    # within half a second and nothing raised on the healthy lead-in.
    assert not [s for s in est.alarm_steps if s < FAULTS[0][0]]
    for lo, hi, kind, _ in FAULTS:
        assert est.flag_history[lo + 50], f"{kind} at {lo} not flagged"
    assert 4 in est.alarm_tests
    SEEN.update(est.alarm_tests)
    SEEN.add(("cleared", bool(est.clear_steps)))


def test_the_drives_between_them_reach_every_branch():
    """One drive may spend its faults under a single long flag. Across the
    three, the step, gross and frozen tests have all raised it and it has
    been dropped again."""
    if not SEEN:
        pytest.skip("the parity drives did not run")
    assert {1, 2, 4} <= SEEN and ("cleared", True) in SEEN


def test_the_firmware_b7_settings_are_the_tuned_ones():
    """The thresholds are chosen by a script and typed into a header."""
    h = Path("firmware/main/control.h").read_text()
    s = BiasAwareSettings()

    def const(name):
        return float(re.search(rf"#define {name}\s+([0-9.]+)f?", h).group(1))

    for name, value in (
            ("B7_WINDOW", s.window), ("B7_T_LIMIT", s.t_limit),
            ("B7_GROSS_MPS", s.gross_mps), ("B7_GROSS_COUNT", s.gross_count),
            ("B7_FROZEN_COUNT", s.frozen_count),
            ("B7_CLEAR_COUNT", s.clear_count),
            ("B7_CLEAR_BAND_MPS", s.clear_band_mps), ("B7_TAU_S", s.tau_s),
            ("B7_TAU_B_S", s.tau_b_s), ("B7_STEP_HALF", s.step_half),
            ("B7_T_STEP", s.t_step),
            ("B7_STEP_SLOPE_MPS2", s.step_slope_mps2),
            ("B7_DR_SIGMA_MPS", s.dr_sigma_mps),
            ("B7_BAND_GROWTH_MPS2", s.band_growth_mps2)):
        assert const(name) == pytest.approx(value), name
