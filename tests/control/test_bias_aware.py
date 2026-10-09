import numpy as np
import pytest

from evpil.control import accel_models as am
from evpil.control import sensor_eval as se
from evpil.control.cycles import Cycle
from evpil.control.rule_ems import EmsAction
from evpil.control.sim import fixed_policy, simulate
from evpil.control.speed_estimators import (
    BiasAwareFaultKalman, KalmanSpeed, KinematicFaultKalman, SpeedFault,
)

POL = fixed_policy(EmsAction(1.0, 3e5, 0.0))
Q, QD = 0.002, 0.02


def cruise(n=6000, dt=0.01):
    t = np.arange(n) * dt
    v = np.clip(2.0 * t, 0.0, 15.0) + 1.5 * np.sin(2 * np.pi * t / 20.0) * (t > 8)
    return Cycle(name="cruise", dt_s=dt, v_ref_mps=v, grade_rad=np.zeros(n))


def run(params, est, *, err=None, fault=None, seed=0, n=6000):
    return simulate(params, cruise(n), POL, speed_noise_mps=0.02,
                    accel_noise_mps2=0.05, seed=seed, speed_estimator=est,
                    speed_fault=fault, accel_error_mps2=err, keep_trace=True)


def test_the_wander_has_the_spread_and_memory_it_was_asked_for():
    w = am.wander(400_000, 0.01, sd_mps2=0.12, tau_s=10.0, seed=3)
    assert np.std(w) == pytest.approx(0.12, rel=0.1)
    lag = int(10.0 / 0.01)
    assert np.corrcoef(w[:-lag], w[lag:])[0, 1] == pytest.approx(
        np.exp(-1), abs=0.08)


def test_slope_gravity_is_gravity_along_the_road():
    assert am.slope_gravity(np.array([0.0, 0.05]))[1] == pytest.approx(
        9.81 * np.sin(0.05))


def test_an_acceleration_error_is_seen_by_the_estimator_only(params):
    """The plant and the energy manager do not read the corrupted channel:
    an estimator that ignores acceleration gives the same drive."""
    n = 3000
    a = run(params, KalmanSpeed(params, q_mps=Q, r_mps=0.02), n=n)
    b = run(params, KalmanSpeed(params, q_mps=Q, r_mps=0.02), n=n,
            err=am.offset(n, 0.5))
    assert a.energy_wh == b.energy_wh


def test_a_wrong_length_acceleration_error_is_refused(params):
    with pytest.raises(ValueError):
        run(params, KalmanSpeed(params, q_mps=Q, r_mps=0.02),
            err=np.zeros(10))


def test_b7_learns_a_standing_acceleration_offset(params):
    est = BiasAwareFaultKalman(params, q_mps=Q, q_d_mps2=QD)
    run(params, est, err=am.offset(6000, 0.17))
    assert est.accel_offset_mps2 == pytest.approx(0.17, abs=0.04)


def test_b7_is_quiet_where_b6_is_not(params):
    """The reason B7 exists: a healthy sensor beside an acceleration channel
    that wanders the way the logged one does."""
    err = am.wander(6000, 0.01, seed=1)
    b6 = KinematicFaultKalman(params, q_mps=Q, q_d_mps2=QD)
    b7 = BiasAwareFaultKalman(params, q_mps=Q, q_d_mps2=QD)
    run(params, b6, err=err)
    r7 = run(params, b7, err=err)
    assert len(b6.alarm_steps) > 0
    assert len(b7.alarm_steps) == 0
    assert r7.tracking_rmse_mps < 0.05


@pytest.mark.parametrize("kind,mag", [("stuck", 0.0), ("dropout", 0.0),
                                      ("bias", 0.5), ("bias", -0.5),
                                      ("bias", 3.0)])
def test_b7_flags_each_named_fault_in_time_beside_a_wandering_channel(
        params, kind, mag):
    est = BiasAwareFaultKalman(params, q_mps=Q, q_d_mps2=QD)
    run(params, est, err=am.wander(6000, 0.01, seed=2),
        fault=SpeedFault(kind, 30.0, mag, duration_s=5.0))
    after = [s for s in est.alarm_steps if s >= 3000]
    assert not [s for s in est.alarm_steps if s < 3000]
    assert after and (after[0] - 3000) * 0.01 <= 0.5


def test_b7_lets_a_recovered_sensor_back_in(params):
    est = BiasAwareFaultKalman(params, q_mps=Q, q_d_mps2=QD)
    run(params, est, fault=SpeedFault("dropout", 30.0, duration_s=5.0))
    assert est.flag_history[3400] and not est.flag_history[-1]


def test_the_registered_cases_do_not_overlap_between_splits():
    trips = [set(v) for v in se.SPLIT_TRIPS.values()]
    cycles = [set(v) for v in se.SPLIT_CYCLES.values()]
    for group in (trips, cycles):
        assert not (group[0] & group[1] or group[0] & group[2]
                    or group[1] & group[2])
    seeds = {s: {c.seed for c in se.fault_cases(s) + se.clean_cases(s)}
             for s in se.SPLIT_CYCLES}
    assert not (seeds["train"] & seeds["val"] or seeds["val"] & seeds["test"]
                or seeds["train"] & seeds["test"])


def test_the_sealed_i3_test_trips_are_not_among_the_replayed_ones():
    import json
    sealed = set(json.load(open("data/splits.json"))["test"])
    assert not sealed & {t for v in se.SPLIT_TRIPS.values() for t in v}


def test_the_verdict_fails_an_arm_that_misses_a_fault():
    f = [{"accel": "white", "mass": 1.0, "named": True, "noise_x": 1.0,
          "delay_s": d, "false_clear": False, "lingering": False,
          "clear_after_restore_s": 0.5, "false_alarms_before": 0,
          "peak_err_mps": 0.1} for d in (0.1, None)]
    c = [{"accel": "white", "mass": 1.0, "noise_x": 1.0, "hours": 1.0,
          "false_alarms": 0, "flagged_share": 0.0,
          "equivalent_wh_per_km": 100.0, "b5_equivalent_wh_per_km": 100.0,
          "tracking_rmse_mps": 0.01, "b5_tracking_rmse_mps": 0.01}]
    g = se.verdict(f, c)["by_accel"]["white, mass x1"]
    assert g["missed_or_late"] == 1 and g["passes"] is False
    f[1]["delay_s"] = 0.2
    assert se.verdict(f, c)["by_accel"]["white, mass x1"]["passes"] is True


def test_b8_detects_exactly_as_b7_does(params):
    """B8 changes the speed used while flagged, not when the flag goes up."""
    from evpil.control.speed_estimators import FusedFallbackKalman
    err = am.wander(6000, 0.01, seed=2)
    b7 = BiasAwareFaultKalman(params, q_mps=Q, q_d_mps2=QD)
    b8 = FusedFallbackKalman(params, q_mps=Q, q_d_mps2=QD)
    a = run(params, b7, err=err)
    b = run(params, b8, err=err)
    assert a.energy_wh == b.energy_wh          # no flag, same drive
    f = lambda: SpeedFault("dropout", 30.0, duration_s=5.0)
    b7, b8 = (BiasAwareFaultKalman(params, q_mps=Q, q_d_mps2=QD),
              FusedFallbackKalman(params, q_mps=Q, q_d_mps2=QD))
    run(params, b7, err=err, fault=f())
    run(params, b8, err=err, fault=f())
    assert b7.alarm_steps[0] == b8.alarm_steps[0]


def test_the_fused_speed_learns_both_errors_and_coasts_on_them(params):
    """A car heavier than the model and an offset accelerometer at once.
    With the speed reading the filter separates the two; without it, it
    stays close for five seconds."""
    from dataclasses import replace as dc_replace
    from evpil.control.speed_estimators import FusedSettings, FusedSpeed
    heavy = dc_replace(params, mass_kg=params.mass_kg * 1.1)
    fuse = FusedSpeed(params, FusedSettings())
    seen = {}

    class Tap:
        def __init__(self): self.k = 0
        def step(self, *, v_meas_mps, torque_prev_nm, grade_rad, dt_s,
                 a_meas_mps2=0.0):
            use = None if 3000 <= self.k < 3500 else v_meas_mps
            v = fuse.step(torque_prev_nm=torque_prev_nm, grade_rad=grade_rad,
                          dt_s=dt_s, a_meas_mps2=a_meas_mps2, v_meas_mps=use,
                          r_v2=0.02 ** 2)
            if self.k == 3499:
                seen["gap"] = abs(v - v_meas_mps)
            self.k += 1
            return v_meas_mps
    simulate(heavy, cruise(6000), POL, ff_params=params, speed_noise_mps=0.02,
             accel_noise_mps2=0.05, seed=0, speed_estimator=Tap(),
             accel_error_mps2=am.offset(6000, 0.17))
    assert fuse.x[2] == pytest.approx(0.17, abs=0.08)
    assert seen["gap"] < 0.5
