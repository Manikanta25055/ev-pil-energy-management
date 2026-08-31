import numpy as np
import pytest

from evpil.control import dp as dpm
from evpil.control.rule_ems import EmsAction, RuleParams, rule_action
from evpil.control.sim import fixed_policy, simulate
from tests.control.test_sim import short_cycle

OPEN_W = 3e5        # a discharge ceiling that never binds


def solve_short(params, price=1.0, **kw):
    return dpm.solve(params, short_cycle(),
                     spec=dpm.DpSpec(soc_grid_n=41, comfort_price=price),
                     **kw)


def test_the_machine_power_trajectory_is_the_same_whatever_the_action(params):
    """The DP precomputes this trajectory once for every action. If it were
    action-dependent, the whole formulation would be wrong rather than
    approximate."""
    c = short_cycle()
    p_elec, _, _ = dpm.machine_power_trajectory(params, c)
    a = simulate(params, c, fixed_policy(EmsAction(0.0, OPEN_W, 0.0)),
                 keep_trace=True)
    b = simulate(params, c, fixed_policy(EmsAction(1.0, OPEN_W, 0.30)),
                 keep_trace=True)
    assert np.allclose(a.trace.torque_nm, b.trace.torque_nm, atol=1e-12)
    assert len(p_elec) == len(c.v_ref_mps)
    assert p_elec.min() < 0.0 and p_elec.max() > 0.0     # braking and driving


def test_the_optimum_is_at_least_as_good_as_every_fixed_action(params):
    """The definition of an optimum, checked rather than assumed. A DP that
    loses to a constant action has a sign error or a stale value function."""
    c = short_cycle()
    sol = solve_short(params)
    best = simulate(params, c, dpm.dp_policy(sol, OPEN_W))
    for blend in (0.0, 0.25, 0.5, 0.75, 1.0):
        fixed = simulate(params, c, fixed_policy(EmsAction(blend, OPEN_W, 0.0)))
        assert best.energy_wh <= fixed.energy_wh + 1e-6


def test_the_optimum_is_at_least_as_good_as_the_rule_manager(params):
    c = short_cycle()
    sol = solve_short(params)
    best = simulate(params, c, dpm.dp_policy(sol, OPEN_W))
    rules = RuleParams()
    rule = simulate(params, c, lambda o: rule_action(
        rules, soc_frac=o.soc_frac, v_mps=o.v_mps))
    assert best.energy_wh <= rule.energy_wh + 1e-6


def test_the_value_function_agrees_with_the_plant_it_approximates(params):
    """The DP treats the RC branch as exogenous and averages machine power
    over a stage, so its own estimate is an approximation. This bounds it.

    The bound is 3% rather than a fraction of a percent because this synthetic
    cycle brakes hard enough to saturate the charge-current limit inside a
    single 100 ms stage, and averaging power before applying a clamp is not the
    same as applying the clamp ten times. On the published cycles, where power
    moves far less within a stage, the two agree to better than a tenth of a
    percent -- the measured figures are in docs/week7-control-baselines.csv.
    That is exactly why the reported optimum is the plant's number and not the
    value function's."""
    c = short_cycle()
    sol = solve_short(params)
    realised = simulate(params, c, dpm.dp_policy(sol, OPEN_W))
    assert sol.predicted_wh == pytest.approx(realised.energy_wh, rel=0.03)


def test_free_comfort_sheds_and_priced_comfort_barely_does(params):
    """The result that stops 'shed the heater' being reported as an energy
    management achievement."""
    c = short_cycle()
    cold = {"t_ambient_c": 0.0}      # the DP and the plant must agree on the
                                     # weather, or the policy is optimal for a
                                     # different day than the one simulated
    free = simulate(params, c, dpm.dp_policy(
        solve_short(params, price=0.0, **cold), OPEN_W), **cold)
    priced = simulate(params, c, dpm.dp_policy(
        solve_short(params, price=1.0, **cold), OPEN_W), **cold)
    assert free.aux_shed_wh > 5.0 * max(priced.aux_shed_wh, 1e-6)


def test_the_policy_lookup_takes_the_nearest_grid_node(params):
    sol = solve_short(params)
    grid = sol.soc_grid
    policy = dpm.dp_policy(sol, OPEN_W)

    from evpil.control.sim import Observation
    just_below = grid[5] - 0.4 * (grid[1] - grid[0])
    obs = Observation(t_s=0.0, v_mps=10.0, a_mps2=0.0, soc_frac=just_below,
                      t_batt_c=20.0, grade_rad=0.0, tracking_error_mps=0.0,
                      p_batt_w=0.0)
    at_node = Observation(**{**obs.__dict__, "soc_frac": float(grid[5])})
    assert policy(obs) == policy(at_node)


def test_the_policy_is_a_feedback_law_not_a_replayed_schedule(params):
    """It must answer for a state of charge the DP never predicted, because
    under the injected disturbances of spec 6.5 the vehicle leaves the
    predicted trajectory."""
    from evpil.control.sim import Observation
    sol = solve_short(params)
    policy = dpm.dp_policy(sol, OPEN_W)
    for soc in (0.0, 0.5, 1.0):
        a = policy(Observation(t_s=5.0, v_mps=10.0, a_mps2=0.0, soc_frac=soc,
                               t_batt_c=20.0, grade_rad=0.0,
                               tracking_error_mps=0.0, p_batt_w=0.0))
        assert 0.0 <= a.regen_blend <= 1.0
