import numpy as np
import pytest

from evpil.control.pid import (
    PidGains, PidState, feedforward_torque_nm, pid_step,
)
from evpil.control.sim import DEFAULT_GAINS

GAINS = DEFAULT_GAINS


def _run(gains, n, v_ref, v_meas_fn, ff=0.0, limit=250.0, dt=0.01):
    st = PidState()
    out = None
    for k in range(n):
        out = pid_step(gains, st, v_ref_mps=v_ref,
                       v_meas_mps=v_meas_fn(k, out), torque_ff_nm=ff,
                       torque_limit_nm=limit, dt_s=dt)
        st = out.state
    return out


def test_zero_error_and_zero_feedforward_commands_zero_torque():
    out = _run(GAINS, 50, 10.0, lambda k, o: 10.0)
    assert out.torque_nm == pytest.approx(0.0, abs=1e-9)
    assert out.state.integral_nm == pytest.approx(0.0, abs=1e-9)


def test_a_persistent_error_charges_the_integrator_in_the_right_direction():
    out = _run(GAINS, 100, 10.0, lambda k, o: 9.0)
    assert out.state.integral_nm > 0.0
    assert out.torque_nm > 0.0


def test_the_integrator_is_clamped_at_its_declared_limit():
    out = _run(GAINS, 5000, 30.0, lambda k, o: 0.0)
    assert abs(out.state.integral_nm) <= GAINS.i_limit_nm + 1e-9


def test_conditional_integration_stops_windup_against_a_saturated_output():
    """The failing alternative is integrating through a long saturation and
    then overshooting when the demand eases. The integrator must not grow once
    the output is already against its stop."""
    tight = PidGains(kp_nm_per_mps=120.0, ki_nm_per_mps_s=40.0,
                     kd_nm_s_per_mps=2.0, tau_d_s=0.05, i_limit_nm=250.0)
    st = PidState()
    integrals = []
    for _ in range(200):
        out = pid_step(tight, st, v_ref_mps=30.0, v_meas_mps=0.0,
                       torque_ff_nm=0.0, torque_limit_nm=5.0, dt_s=0.01)
        st = out.state
        integrals.append(st.integral_nm)
        assert out.saturated
    assert integrals[-1] == pytest.approx(integrals[10], abs=1e-9)


def test_the_output_never_leaves_the_actuator_bound():
    for v_meas in (-50.0, 0.0, 50.0):
        out = _run(GAINS, 300, 30.0, lambda k, o, v=v_meas: v, limit=180.0)
        assert -180.0 - 1e-9 <= out.torque_nm <= 180.0 + 1e-9


def test_the_derivative_filter_attenuates_step_to_step_noise():
    rng = np.random.default_rng(0)
    noisy = lambda k, o: 10.0 + rng.normal(0.0, 0.5)

    unfiltered = PidGains(0.0, 0.0, 1.0, tau_d_s=0.0)
    filtered = PidGains(0.0, 0.0, 1.0, tau_d_s=0.05)

    def spread(gains):
        st, vals = PidState(), []
        rng2 = np.random.default_rng(0)
        for _ in range(500):
            out = pid_step(gains, st, v_ref_mps=10.0,
                           v_meas_mps=10.0 + rng2.normal(0.0, 0.5),
                           torque_ff_nm=0.0, torque_limit_nm=1e6, dt_s=0.01)
            st = out.state
            vals.append(out.torque_nm)
        return float(np.std(vals))

    assert spread(filtered) < 0.4 * spread(unfiltered)


def test_the_feedforward_inverts_the_plants_own_road_load(params):
    """A feedforward that does not invert the plant leaves a standing error the
    integrator has to carry, which is exactly what the term exists to avoid."""
    from evpil.plant.longitudinal import road_load

    v, a, grade = 20.0, 0.5, 0.02
    tq = feedforward_torque_nm(params, v_ref_mps=v, a_ref_mps2=a,
                               grade_rad=grade)
    f_wheel = tq * params.gear_ratio * params.drivetrain_eta / params.wheel_radius_m
    want = road_load(v_mps=v, a_mps2=a, grade_rad=grade,
                     mass_kg=params.mass_kg, c_rr=params.c_rr, cd=params.cd,
                     frontal_area_m2=params.frontal_area_m2,
                     rot_mass_factor=params.rot_mass_factor).tractive_n
    assert f_wheel == pytest.approx(want, rel=1e-9)


def test_the_feedforward_is_negative_when_the_reference_decelerates(params):
    tq = feedforward_torque_nm(params, v_ref_mps=20.0, a_ref_mps2=-2.0,
                               grade_rad=0.0)
    assert tq < 0.0
