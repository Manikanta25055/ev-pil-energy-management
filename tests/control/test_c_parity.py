"""The firmware controller must be the controller the simulations used.

protocol.c is kept in step with protocol.py by shared byte vectors. The same
discipline applies here for a stronger reason: a frame format that differs
between the two ends fails loudly, and a controller that differs quietly
produces plausible numbers that are not the ones the paper's simulation
results describe.

The C side prints; the reference values are computed here. Duplicating the
expected numbers in the C file would mean maintaining them twice, which is how
two implementations drift while both of their tests keep passing.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from evpil.control.pid import PidState, feedforward_torque_nm, pid_step
from evpil.control.rule_ems import RuleParams, rule_action
from evpil.control.sim import DEFAULT_GAINS
from evpil.control.speed_estimators import KalmanSpeed, KinematicFaultKalman
from evpil.control.speed_filter import SpeedFilterState, speed_filter_step
from evpil.plant.motor import clamp_torque

HOST_TEST = Path("firmware/host_test")

# float32 arithmetic on the device against float64 here. The tolerance is set
# by that difference and nothing else; anything larger is a real divergence.
REL = 2e-5
ABS = 2e-3


@pytest.fixture(scope="module")
def dump():
    if shutil.which("cc") is None:
        pytest.skip("no C compiler available")
    if not (HOST_TEST / "test_control.c").exists():
        pytest.skip("firmware host test not present")
    subprocess.run(["make", "test_control"], cwd=HOST_TEST, check=True,
                   capture_output=True)
    out = subprocess.run([str(HOST_TEST / "test_control")], check=True,
                         capture_output=True, text=True).stdout

    rows: dict[str, list[list[float]]] = {"ff": [], "lim": [], "pid": [],
                                          "filt": [], "kf": [], "b6": [], "rule": []}
    for line in out.splitlines():
        if line.startswith("#"):
            continue
        tag, *rest = line.split()
        rows[tag].append([float(x) for x in rest])
    return rows


def test_the_c_feedforward_matches_the_python_one(params, dump):
    assert dump["ff"], "no feedforward rows in the dump"
    for v_ref, a_ref, grade, got in dump["ff"]:
        want = feedforward_torque_nm(params, v_ref_mps=v_ref,
                                     a_ref_mps2=a_ref, grade_rad=grade)
        assert got == pytest.approx(want, rel=REL, abs=ABS), \
            f"feedforward at v={v_ref} a={a_ref} grade={grade}"


def test_the_c_torque_limit_matches_the_python_one(params, dump):
    for omega, got in dump["lim"]:
        want = abs(clamp_torque(params.motor, params.motor.torque_max_nm,
                                omega))
        assert got == pytest.approx(want, rel=REL, abs=ABS), \
            f"torque limit at omega={omega}"


def test_the_c_pid_matches_the_python_one_step_for_step(params, dump):
    """Step for step, not just at the end: a divergence that cancels out by
    the last sample is still a different controller."""
    st = PidState()
    assert len(dump["pid"]) == 200
    for n, v_ref, v_meas, got_tq, got_int in dump["pid"]:
        limit = 250.0 if n < 150 else 8.0
        out = pid_step(DEFAULT_GAINS, st, v_ref_mps=v_ref, v_meas_mps=v_meas,
                       torque_ff_nm=3.5, torque_limit_nm=limit, dt_s=0.01)
        st = out.state
        assert got_tq == pytest.approx(out.torque_nm, rel=REL, abs=ABS), \
            f"torque at step {int(n)}"
        assert got_int == pytest.approx(st.integral_nm, rel=REL, abs=ABS), \
            f"integrator at step {int(n)}"


def test_the_c_speed_filter_matches_the_python_one_step_for_step(dump):
    assert len(dump["filt"]) == 6 * 120
    st = SpeedFilterState()
    for alpha, n, v, got in dump["filt"]:
        if n == 0:
            st = SpeedFilterState()
        # Python refuses an alpha outside (0, 1]; the firmware cannot raise
        # and falls back to no filter. Both are checked: the refusal in
        # test_speed_filter.py, the fallback here.
        st, want = speed_filter_step(st, v, alpha if 0.0 < alpha <= 1.0 else 1.0)
        assert got == pytest.approx(want, rel=REL, abs=ABS), \
            f"filter at alpha={alpha} step {int(n)}"


def test_the_c_speed_filter_at_alpha_one_returns_its_input_exactly(dump):
    rows = [r for r in dump["filt"] if r[0] == 1.0]
    assert rows and all(v == got for _, _, v, got in rows)


def test_the_firmware_defaults_to_no_speed_filter():
    """Every gate and campaign so far was measured on the unfiltered loop. A
    default that drifted would change all of them without a rebuild flag
    anywhere saying so."""
    text = Path("firmware/main/tasks.h").read_text()
    assert "#define SPEED_FILTER_ALPHA 1.0f" in text
    tasks = Path("firmware/main/tasks.c").read_text()
    assert "s_speed_alpha = SPEED_FILTER_ALPHA" in tasks
    assert "control_speed_filter_step(&s_speed_filt, v_meas" in tasks


def _python_kalman(params, mode):
    if mode == 0:
        return KalmanSpeed(params, q_mps=0.0005, r_mps=0.06)
    return KalmanSpeed(params, q_mps=0.002, r_mps=0.02, adaptive=True,
                       q_d_mps2=0.02 if mode == 2 else 0.0)


@pytest.mark.parametrize("mode", [0, 1, 2])
def test_the_c_kalman_speed_estimate_matches_the_python_one(params, dump, mode):
    """Fixed (B3), adaptive (B3a) and two-state (B5), step for step, with the
    noise level the adaptive ones read off the jitter and the unknown
    acceleration the two-state one learns."""
    rows = [r for r in dump["kf"] if r[0] == mode]
    assert len(rows) == 600
    kf = _python_kalman(params, mode)
    seen_sigma, seen_d = [], []
    for _, n, v, tq, grade, got, got_sigma, got_d in rows:
        want = kf.step(v_meas_mps=v, torque_prev_nm=tq, grade_rad=grade,
                       dt_s=0.01)
        assert got == pytest.approx(want, rel=REL, abs=ABS), \
            f"estimate, mode {mode}, step {int(n)}"
        if mode:
            assert got_sigma == pytest.approx(kf._meter.sigma_mps,
                                              rel=1e-3, abs=1e-5), \
                f"noise level at step {int(n)}"
        assert got_d == pytest.approx(kf._d, rel=2e-3, abs=2e-3), \
            f"unknown acceleration at step {int(n)}"
        seen_sigma.append(got_sigma)
        seen_d.append(got_d)
    if mode:
        # The dump has to make the adaptive arm adapt, or this would pass
        # with the meter disconnected.
        assert max(seen_sigma[400:]) > 5 * max(seen_sigma[100:290])
    if mode == 2:
        # And the second state has to have something to learn.
        assert max(abs(d) for d in seen_d) > 0.2
    else:
        assert all(d == 0.0 for d in seen_d)


def test_the_c_fault_detector_matches_the_python_one(params, dump):
    """B6, step for step: the estimate, the dead-reckoned speed, and above all
    the flag. A flag that goes up one step apart on the two sides is a
    different detector."""
    rows = dump["b6"]
    assert len(rows) == 1700
    est = KinematicFaultKalman(params, q_mps=0.002, q_d_mps2=0.02)
    flags = []
    for n, v, a, tq, got, got_flag, got_alarms, got_dr, got_test in rows:
        want = est.step(v_meas_mps=v, a_meas_mps2=a, torque_prev_nm=tq,
                        grade_rad=0.0, dt_s=0.01)
        assert bool(got_flag) == est.flagged, f"flag at step {int(n)}"
        assert int(got_alarms) == len(est.alarm_steps), \
            f"alarm count at step {int(n)}"
        assert got == pytest.approx(want, rel=REL, abs=ABS), \
            f"estimate at step {int(n)}"
        assert got_dr == pytest.approx(est._v_dr, rel=REL, abs=ABS), \
            f"dead-reckoned speed at step {int(n)}"
        if est.alarm_tests:
            assert int(got_test) == est.alarm_tests[-1], \
                f"which test raised the flag, at step {int(n)}"
        flags.append(bool(got_flag))

    # The dump has to exercise what it claims to: three faults, each caught
    # within half a second, none raised on healthy samples, each cleared.
    onsets = (400, 800, 1200)
    assert [s for s in est.alarm_steps] and len(est.alarm_steps) == 3
    for onset, alarm in zip(onsets, est.alarm_steps):
        assert 0 <= alarm - onset <= 50, f"fault at {onset} flagged at {alarm}"
    assert not any(flags[:400])
    assert not flags[790] and not flags[1190] and not flags[-1]
    # An offset is caught by the mean test, a dropout by the gross test and a
    # frozen reading by the frozen test: all three paths are exercised.
    assert est.alarm_tests == [3, 1, 2]


def test_the_firmware_kalman_settings_are_the_tuned_ones():
    """The settings are chosen by a script and typed into a header. This is
    the check that the typing was done, and redone if the tuning is rerun."""
    import json
    import re
    tuned = json.loads(Path("docs/week11-speed-arms-tuned.json").read_text())
    h = Path("firmware/main/tasks.h").read_text()

    def const(name):
        return float(re.search(rf"#define {name}\s+([0-9.]+)f", h).group(1))

    assert const("KALMAN_FIXED_Q_MPS") == tuned["b3"]["q_mps"]
    assert const("KALMAN_FIXED_R_MPS") == tuned["b3"]["r_mps"]
    assert const("KALMAN_ADAPT_Q_MPS") == tuned["b3a"]["q_mps"]
    assert const("KALMAN_QD_MPS2") == tuned["b5"]["q_d_mps2"]
    assert tuned["b5"]["q_mps"] == tuned["b3a"]["q_mps"]
    assert "#define SPEED_KALMAN 0" in h, "the Kalman estimate must be opt-in"


def test_the_c_rule_manager_matches_the_python_one(params, dump):
    rules = RuleParams()
    for soc, v, blend, p_limit, derate in dump["rule"]:
        want = rule_action(rules, soc_frac=soc, v_mps=v)
        assert blend == pytest.approx(want.regen_blend, rel=REL, abs=ABS)
        assert p_limit == pytest.approx(want.p_limit_w, rel=REL, abs=1.0)
        assert derate == pytest.approx(want.aux_derate, rel=REL, abs=ABS)


def test_the_compiled_vehicle_constants_match_the_identified_ones(params):
    """The firmware compiles the vehicle in rather than receiving it over the
    link. That is the right call for a controller that has to run on its own,
    and it means the constants can go stale silently."""
    text = (Path("firmware/main/control.c")).read_text()
    for name, value in (("mass_kg", params.mass_kg),
                        ("c_rr", params.c_rr),
                        ("cd", params.cd),
                        ("frontal_area_m2", params.frontal_area_m2),
                        ("wheel_radius_m", params.wheel_radius_m),
                        ("gear_ratio", params.gear_ratio),
                        ("drivetrain_eta", params.drivetrain_eta),
                        ("rot_mass_factor", params.rot_mass_factor),
                        ("torque_max_nm", params.motor.torque_max_nm),
                        ("power_max_w", params.motor.power_max_w)):
        line = next((l for l in text.splitlines()
                     if l.strip().startswith(f".{name} =")), None)
        assert line is not None, f"{name} not found in firmware/main/control.c"
        literal = line.split("=")[1].strip().rstrip(",").rstrip("f")
        literal = literal.split("/*")[0].strip().rstrip(",").rstrip("f")
        assert float(literal) == pytest.approx(value, rel=1e-6), \
            f"{name}: firmware has {literal}, identification has {value}"
