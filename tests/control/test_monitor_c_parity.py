"""The on-chip supervisor must be the one that was evaluated.

Architecture A2 with the rule monitor: B7, the block summary, the monitor's
vote and the four settings it may change, in C, against
evpil.control.supervisor.Supervisor with a RuleMonitor on a channel with no
delay. Compared step for step, including what the supervisor did to B7.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from evpil.control.speed_estimators import BiasAwareFaultKalman
from evpil.control.supervisor import Channel, Policy, RuleMonitor, Supervisor
from tests.control.b7_drive import N, drive, run_c

REL = 2e-5
ABS = 2e-3


@pytest.mark.parametrize("seed,noise_x", [(0, 1.0), (3, 10.0), (5, 1.0)])
def test_the_c_supervisor_matches_the_python_one(params, tmp_path, seed,
                                                 noise_x):
    v, a, tq = drive(seed, noise_x)
    got = run_c("sup", v, a, tq, tmp_path)
    assert got.shape[0] == N
    base = BiasAwareFaultKalman(params, q_mps=0.002, q_d_mps2=0.02)
    sup = Supervisor(base, fast=(RuleMonitor(), Channel()))
    held = switched = 0
    for n in range(N):
        want = sup.step(v_meas_mps=v[n], a_meas_mps2=a[n],
                        torque_prev_nm=tq[n], grade_rad=0.0, dt_s=0.01)
        (g_est, g_flag, g_alarms, g_clears, g_dr, g_b, _, g_hold, g_w,
         g_vig, g_epoch) = got[n]
        assert bool(g_flag) == base.flagged, f"flag at step {n}"
        assert int(g_alarms) == len(base.alarm_steps), f"alarms at step {n}"
        assert int(g_clears) == len(base.clear_steps), f"clears at step {n}"
        assert bool(g_hold) == base.hold_release, f"hold at step {n}"
        assert g_w == (1.0 if base.fallback_model else 0.0), f"fallback, {n}"
        assert g_vig == pytest.approx(base.vigilance), f"vigilance, {n}"
        assert int(g_epoch) == sup._epoch, f"flag epoch at step {n}"
        assert g_est == pytest.approx(want, rel=REL, abs=ABS), f"estimate, {n}"
        assert g_dr == pytest.approx(base._v_dr, rel=REL, abs=ABS), f"v_dr, {n}"
        held += base.hold_release
        switched += base.fallback_model
    # The supervisor has to have done something for the comparison to mean
    # anything: a hold in every drive.
    assert held > 0
    assert sup.applied["hold"] == held


def test_the_firmware_supervisor_settings_are_the_evaluated_ones():
    h = Path("firmware/main/control.h").read_text()
    p, m = Policy(), RuleMonitor()

    def const(name):
        return float(re.search(rf"#define {name}\s+([0-9.]+)f?", h).group(1))

    for name, value in (
            ("SUP_P_HOLD", p.p_hold), ("SUP_P_RELEASE", p.p_release),
            ("SUP_P_ACCEL", p.p_accel), ("SUP_P_VIGILANT", p.p_vigilant),
            ("SUP_VIGILANCE", p.vigilance), ("SUP_EXPIRY_S", p.expiry_s),
            ("SUP_MAX_HOLD_S", p.max_hold_s),
            ("SUP_MIN_FLAG_S", p.min_flag_s), ("SUP_MEMORY", m.memory),
            ("MON_OFF_MPS", m.off), ("MON_SPLIT_MPS", m.split),
            ("MON_OFFSET_MPS2", m.b_lim)):
        assert const(name) == pytest.approx(value), name

    # The step counts the C side uses in place of the two running sums:
    # the number of 10 ms additions for which the sum is still below each.
    def steps_below(limit):
        t, n = 0.0, 0
        while t < limit:
            t += 0.01
            n += 1
        return n

    assert const("SUP_MIN_FLAG_STEPS") == steps_below(p.min_flag_s)
    assert const("SUP_MAX_HOLD_STEPS") == steps_below(p.max_hold_s)
