import numpy as np
import pytest

from evpil.control.cycles import Cycle, load_cycle
from evpil.control.rule_ems import EmsAction, RuleParams, rule_action
from evpil.control.sim import fixed_policy, simulate


def short_cycle(n=3000, dt=0.01):
    """Thirty seconds of accelerate-cruise-brake, so a test is a second, not
    a minute, and still contains both a traction and a braking phase."""
    t = np.arange(n) * dt
    v = np.clip(np.minimum(2.0 * t, 2.0 * (t[-1] - t)), 0.0, 20.0)
    return Cycle(name="short", dt_s=dt, v_ref_mps=v, grade_rad=np.zeros(n))


def test_the_speed_trajectory_does_not_depend_on_the_energy_action(params):
    """The premise the whole DP formulation rests on. If regen blend or the
    auxiliary derate moved the vehicle, the optimiser could buy energy savings
    by driving differently and every result would be contaminated."""
    c = short_cycle()
    a = simulate(params, c, fixed_policy(EmsAction(0.0, 3e5, 0.0)),
                 keep_trace=True)
    b = simulate(params, c, fixed_policy(EmsAction(1.0, 3e5, 0.30)),
                 keep_trace=True)
    assert np.allclose(a.trace.v_mps, b.trace.v_mps, atol=1e-12)
    assert a.tracking_rmse_mps == pytest.approx(b.tracking_rmse_mps, rel=1e-12)


def test_regeneration_lowers_consumption_and_is_credited_as_recovery(params):
    c = short_cycle()
    off = simulate(params, c, fixed_policy(EmsAction(0.0, 3e5, 0.0)))
    on = simulate(params, c, fixed_policy(EmsAction(1.0, 3e5, 0.0)))
    assert on.energy_wh < off.energy_wh
    assert on.regen_wh > 0.0
    assert off.regen_wh == pytest.approx(0.0)


def test_energy_is_net_of_recovery_not_gross_draw(params):
    """`PlantState.energy_wh` integrates only positive battery power. Using it
    would credit a regenerating controller with recovering nothing."""
    c = short_cycle()
    r = simulate(params, c, fixed_policy(EmsAction(1.0, 3e5, 0.0)),
                 keep_trace=True)
    net = float(np.sum(r.trace.p_batt_w) * c.dt_s / 3600.0)
    assert r.energy_wh == pytest.approx(net, rel=1e-9)


def test_shedding_the_auxiliary_load_is_counted_in_watt_hours(params):
    c = short_cycle()
    r = simulate(params, c, fixed_policy(EmsAction(1.0, 3e5, 0.30)),
                 t_ambient_c=0.0)
    assert r.aux_shed_wh > 0.0
    none = simulate(params, c, fixed_policy(EmsAction(1.0, 3e5, 0.0)),
                    t_ambient_c=0.0)
    assert none.aux_shed_wh == pytest.approx(0.0)
    assert r.energy_wh < none.energy_wh


def test_a_wrong_feedforward_vehicle_degrades_tracking(params):
    from dataclasses import replace
    c = short_cycle()
    good = simulate(params, c, fixed_policy(EmsAction(1.0, 3e5, 0.0)))
    bad = simulate(params, c, fixed_policy(EmsAction(1.0, 3e5, 0.0)),
                   ff_params=replace(params, mass_kg=params.mass_kg * 1.5))
    assert bad.tracking_rmse_mps > good.tracking_rmse_mps


def test_the_outer_loop_is_called_at_a_tenth_of_the_inner_rate(params):
    calls = []

    def counting(obs):
        calls.append(obs.t_s)
        return rule_action(RuleParams(), soc_frac=obs.soc_frac, v_mps=obs.v_mps)

    c = short_cycle(n=1000)
    simulate(params, c, counting)
    # One priming call before the loop, then one every ten inner steps.
    assert len(calls) == 1 + 100
