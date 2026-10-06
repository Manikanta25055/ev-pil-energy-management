import numpy as np
import pytest

from evpil.control.cycles import Cycle
from evpil.control.rule_ems import EmsAction
from evpil.control.sim import fixed_policy, simulate
from evpil.control.speed_filter import SpeedFilterState, speed_filter_step


def short_cycle(n=3000, dt=0.01):
    t = np.arange(n) * dt
    v = np.clip(np.minimum(2.0 * t, 2.0 * (t[-1] - t)), 0.0, 20.0)
    return Cycle(name="short", dt_s=dt, v_ref_mps=v, grade_rad=np.zeros(n))


def run(xs, alpha):
    st, out = SpeedFilterState(), []
    for x in xs:
        st, y = speed_filter_step(st, x, alpha)
        out.append(y)
    return out


def test_alpha_one_is_the_measurement_itself_bit_for_bit():
    xs = [0.1, 17.123456789, -3.0, 1e-9, 40.0]
    assert run(xs, 1.0) == xs


def test_the_first_sample_primes_the_filter():
    # Starting from zero would hand the speed loop a 30 m/s error on the
    # first step of a run that begins at speed.
    assert run([30.0], 0.1) == [30.0]


def test_a_step_settles_at_the_rate_alpha_sets():
    ys = run([0.0] + [1.0] * 50, 0.1)
    assert ys[1] == pytest.approx(0.1)
    assert ys[2] == pytest.approx(0.19)
    assert ys[-1] == pytest.approx(1.0 - 0.9 ** 50)


def test_alpha_outside_zero_to_one_is_refused():
    for bad in (0.0, -0.1, 1.5, float("nan")):
        with pytest.raises(ValueError):
            speed_filter_step(SpeedFilterState(), 1.0, bad)


def test_the_default_leaves_a_simulation_untouched(params):
    c = short_cycle()
    pol = fixed_policy(EmsAction(1.0, 3e5, 0.0))
    a = simulate(params, c, pol, speed_noise_mps=0.2, seed=3, keep_trace=True)
    b = simulate(params, c, pol, speed_noise_mps=0.2, seed=3, keep_trace=True,
                 speed_filter_alpha=1.0)
    assert np.array_equal(a.trace.v_mps, b.trace.v_mps)
    assert a.energy_wh == b.energy_wh


def test_filtering_a_noisy_speed_calms_the_torque(params):
    # What the filter is for: the loop stops chasing the noise, so the torque
    # command moves less from one step to the next.
    c = short_cycle()
    pol = fixed_policy(EmsAction(1.0, 3e5, 0.0))
    raw = simulate(params, c, pol, speed_noise_mps=0.2, seed=3, keep_trace=True)
    flt = simulate(params, c, pol, speed_noise_mps=0.2, seed=3, keep_trace=True,
                   speed_filter_alpha=0.1)
    rough = lambda r: float(np.mean(np.abs(np.diff(r.trace.torque_nm))))
    assert rough(flt) < 0.5 * rough(raw)
