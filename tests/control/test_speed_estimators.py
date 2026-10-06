import numpy as np
import pytest

from evpil.control.cycles import Cycle
from evpil.control.rule_ems import EmsAction
from evpil.control.sim import fixed_policy, simulate
from evpil.control.speed_estimators import (
    FixedFilter, JitterMeter, KalmanSpeed, PassThrough, RegimeTable,
    VarianceThreshold,
)

POL = fixed_policy(EmsAction(1.0, 3e5, 0.0))
KW = dict(torque_prev_nm=0.0, grade_rad=0.0, dt_s=0.01)


def short_cycle(n=3000, dt=0.01):
    t = np.arange(n) * dt
    v = np.clip(np.minimum(2.0 * t, 2.0 * (t[-1] - t)), 0.0, 20.0)
    return Cycle(name="short", dt_s=dt, v_ref_mps=v, grade_rad=np.zeros(n))


def noisy_ramp(sigma, n=600, seed=0, accel=2.0):
    rng = np.random.default_rng(seed)
    return 10.0 + accel * 0.01 * np.arange(n) + rng.normal(0.0, sigma, n)


def test_pass_through_and_alpha_one_are_the_loop_as_shipped(params):
    c = short_cycle()
    base = simulate(params, c, POL, speed_noise_mps=0.1, seed=2)
    for est in (PassThrough(), FixedFilter(1.0)):
        r = simulate(params, c, POL, speed_noise_mps=0.1, seed=2,
                     speed_estimator=est)
        assert r.energy_wh == base.energy_wh
        assert r.tracking_rmse_mps == base.tracking_rmse_mps


def test_a_constant_noise_array_is_the_scalar(params):
    c = short_cycle()
    a = simulate(params, c, POL, speed_noise_mps=0.1, seed=2)
    b = simulate(params, c, POL, seed=2,
                 speed_noise_mps=np.full(len(c.v_ref_mps), 0.1))
    assert a.energy_wh == b.energy_wh


@pytest.mark.parametrize("sigma", [0.02, 0.06, 0.2, 0.5])
def test_the_jitter_meter_reads_the_noise_level_through_an_acceleration(sigma):
    m = JitterMeter(blocks=20)
    for v in noisy_ramp(sigma, n=2000):
        m.push(float(v))
    assert m.sigma_mps == pytest.approx(sigma, rel=0.15)


def test_the_jitter_meter_reads_near_zero_on_a_clean_hard_acceleration():
    m = JitterMeter()
    for v in noisy_ramp(0.0, accel=3.0):
        m.push(float(v))
    assert m.sigma_mps < 1e-6


def regime_after(sigma, n=600, seed=0):
    b2 = VarianceThreshold()
    for v in noisy_ramp(sigma, n=n, seed=seed):
        b2.step(v_meas_mps=float(v), **KW)
    return b2


@pytest.mark.parametrize("sigma,regime", [(0.0, 0), (0.02, 0), (0.06, 1),
                                          (0.2, 2), (0.5, 2)])
def test_the_threshold_arm_settles_in_the_regime_the_table_gives(sigma, regime):
    assert regime_after(sigma).regime == regime


def test_a_noise_level_sitting_on_a_bound_does_not_flap():
    b2 = regime_after(RegimeTable().bounds_mps[0], n=6000)
    h = b2.regime_history[50:]
    assert sum(a != b for a, b in zip(h, h[1:])) <= 2


def test_a_regime_change_waits_for_the_persistence_count():
    b2 = VarianceThreshold()
    for v in noisy_ramp(0.0, n=200):
        b2.step(v_meas_mps=float(v), **KW)
    start = len(b2.regime_history)
    for v in 14.0 + noisy_ramp(0.3, n=200, accel=0.0) - 10.0:
        b2.step(v_meas_mps=float(v), **KW)
    after = b2.regime_history[start:]
    first = next(i for i, r in enumerate(after) if r != 0)
    assert first >= RegimeTable().persist_blocks - 1
    assert after[-1] == 2


def test_the_kalman_estimate_is_closer_to_the_truth_than_the_measurement(params):
    # Coasting from 20 m/s with no torque: the truth follows the road load.
    rng = np.random.default_rng(0)
    ref = KalmanSpeed(params, q_mps=1e-9, r_mps=1e9)     # pure model
    kf = KalmanSpeed(params, q_mps=0.002, r_mps=0.2)
    ref.step(v_meas_mps=20.0, **KW)
    kf.step(v_meas_mps=20.0, **KW)
    err_meas, err_est = [], []
    for _ in range(1500):
        truth = ref.step(v_meas_mps=0.0, **KW)
        z = truth + rng.normal(0.0, 0.2)
        est = kf.step(v_meas_mps=z, **KW)
        err_meas.append(z - truth)
        err_est.append(est - truth)
    assert np.std(err_est[200:]) < 0.25 * np.std(err_meas[200:])


def test_the_adaptive_kalman_trusts_a_clean_measurement(params):
    # The model says the car should be coasting down; the measurement says it
    # is accelerating at 2 m/s^2, and carries no noise. A filter told to
    # expect 0.2 m/s of noise sides with the model and falls far behind; one
    # that measures the noise sides with the measurement.
    truth = noisy_ramp(0.0)
    fixed = KalmanSpeed(params, q_mps=0.002, r_mps=0.2)
    adapt = KalmanSpeed(params, q_mps=0.002, r_mps=0.2, adaptive=True)
    for v in truth:
        e_fixed = fixed.step(v_meas_mps=float(v), **KW) - v
        e_adapt = adapt.step(v_meas_mps=float(v), **KW) - v
    assert abs(e_adapt) < 0.1
    assert abs(e_fixed) > 10 * abs(e_adapt)


def test_no_estimator_can_lower_the_bill_without_following_the_cycle(params):
    """The week-10 lesson, kept as a property of this study's arms."""
    c = short_cycle()
    base = simulate(params, c, POL)
    for est in (FixedFilter(0.1), VarianceThreshold(),
                KalmanSpeed(params, q_mps=0.002, r_mps=0.06)):
        r = simulate(params, c, POL, speed_estimator=est)
        if r.energy_wh < base.energy_wh * 0.995:
            assert r.tracking_rmse_mps > 10 * base.tracking_rmse_mps


# --- the fault detector ----------------------------------------------------

from evpil.control.speed_estimators import FaultTolerantKalman, SpeedFault


def drive(params, fault, *, noise=0.02, seed=0, n=3000, noise_after=None):
    c = short_cycle(n=n)
    est = FaultTolerantKalman(params, q_mps=0.002)
    sig = noise
    if noise_after is not None:
        sig = np.where(np.arange(n) * c.dt_s < 12.0, noise, noise_after)
    r = simulate(params, c, POL, speed_noise_mps=sig, seed=seed,
                 speed_estimator=est, speed_fault=fault)
    return est, r


def test_clean_driving_raises_no_flag(params):
    for seed in range(3):
        est, _ = drive(params, None, seed=seed)
        assert est.alarm_steps == []


def test_a_tenfold_rise_in_noise_is_not_a_fault(params):
    est, _ = drive(params, None, noise_after=0.2)
    assert est.alarm_steps == []


@pytest.mark.parametrize("kind,mag", [("dropout", 0.0), ("stuck", 0.0),
                                      ("bias", 0.5), ("bias", -3.0)])
def test_each_fault_is_flagged_within_half_a_second(params, kind, mag):
    onset = 12.0
    est, _ = drive(params, SpeedFault(kind, onset, mag))
    assert est.alarm_steps, "never flagged"
    delay = est.alarm_steps[0] * 0.01 - onset
    assert 0.0 <= delay <= 0.5


def test_the_flag_keeps_the_loop_on_the_model_through_a_dropout(params):
    # Without the detector a reading of zero at 20 m/s is a 20 m/s error and
    # the loop floors the torque. With it the car hardly notices.
    c = short_cycle()
    fault = lambda: SpeedFault("dropout", 12.0, duration_s=3.0)
    bare = simulate(params, c, POL, speed_noise_mps=0.02,
                    speed_estimator=KalmanSpeed(params, q_mps=0.002,
                                                r_mps=0.02, adaptive=True),
                    speed_fault=fault())
    est, kept = drive(params, fault())
    assert kept.tracking_max_mps < 0.5
    assert bare.tracking_max_mps > 5 * kept.tracking_max_mps


def test_the_flag_drops_again_when_the_sensor_comes_back(params):
    est, _ = drive(params, SpeedFault("dropout", 12.0, duration_s=2.0))
    assert est.flag_history[1300] is True
    assert est.flag_history[-1] is False


# --- the disturbance state -------------------------------------------------

from dataclasses import replace as _replace


def test_the_disturbance_state_off_is_the_one_state_filter_exactly(params):
    a = KalmanSpeed(params, q_mps=0.002, r_mps=0.06)
    b = KalmanSpeed(params, q_mps=0.002, r_mps=0.06, q_d_mps2=0.0)
    for v in noisy_ramp(0.1):
        assert a.step(v_meas_mps=float(v), **KW) == b.step(v_meas_mps=float(v), **KW)


def test_the_disturbance_state_learns_what_the_model_has_wrong(params):
    # The same clean ramp the one-state filter falls behind on: the model says
    # coast, the car accelerates at 2 m/s^2. The second state should end up
    # holding most of that difference, and the estimate should stop lagging.
    truth = noisy_ramp(0.02, n=1500, seed=1)
    one = KalmanSpeed(params, q_mps=0.0005, r_mps=0.06)
    two = KalmanSpeed(params, q_mps=0.0005, r_mps=0.06, q_d_mps2=0.02)
    for v in truth:
        e1 = one.step(v_meas_mps=float(v), **KW) - v
        e2 = two.step(v_meas_mps=float(v), **KW) - v
    assert two._d > 1.5
    assert abs(e2) < 0.3 * abs(e1)


def test_a_heavier_car_no_longer_looks_like_a_faulty_sensor(params):
    c = short_cycle()
    heavy = _replace(params, mass_kg=params.mass_kg * 1.1)
    aware = FaultTolerantKalman(params, q_mps=0.002, q_d_mps2=0.02)
    r = simulate(heavy, c, POL, ff_params=params, speed_noise_mps=0.02,
                 speed_estimator=aware)
    assert len(aware.alarm_steps) == 0
    assert r.tracking_rmse_mps < 0.1
