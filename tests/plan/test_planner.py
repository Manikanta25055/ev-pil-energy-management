import numpy as np
import pytest

from evpil.plan import learned
from evpil.plan.planner import (
    INF, backward, build_table, meet_arrival, plan_full, plan_receding,
)
from evpil.plan.route import (
    Route, planned_time_s, profile_to_cycle, route_from_cycle, violations,
)


def toy_route(n=121, limit=20.0, stops=(60,)):
    lim = np.full(n, limit)
    stop = np.zeros(n, dtype=bool)
    stop[[0, n - 1, *stops]] = True
    lim[stop] = 0.0
    dwell = np.where(stop, 2.0, 0.0)
    return Route("toy", 10.0, lim, stop, dwell, 2.0, -2.5,
                 duration_s=140.0, distance_m=(n - 1) * 10.0)


@pytest.fixture(scope="module")
def tab(params):
    return build_table(params, 10.0, 20.0)


def test_the_table_charges_for_speeding_up_and_pays_back_for_slowing(tab):
    i, j = 20, 21               # 10 m/s and 10.5 m/s
    assert tab.energy_j[i, j] > tab.energy_j[i, i] > tab.energy_j[j, i]
    assert tab.energy_j[j, i] < 0.0
    assert tab.dt_s[i, i] == pytest.approx(1.0)
    assert not tab.ok[0, 0]     # standing still gets nowhere
    assert not tab.ok[20, 30]   # 10 to 15 m/s in 10 m is beyond the motor


def test_the_planner_makes_every_stop_inside_the_bounds_and_on_time(tab):
    r = toy_route()
    v, lam, gap = meet_arrival(r, lambda l: plan_full(tab, r, l)[0])
    broken = violations(r, v)
    assert not any(broken.values()), broken
    assert v[60] == 0.0 and v[0] == 0.0 and v[-1] == 0.0
    assert abs(gap) <= r.arrival_tolerance_s
    assert planned_time_s(r, v) == pytest.approx(r.duration_s,
                                                 abs=r.arrival_tolerance_s)


def test_a_higher_price_on_time_is_a_faster_drive(tab):
    r = toy_route()
    slow = planned_time_s(r, plan_full(tab, r, 500.0)[0])
    fast = planned_time_s(r, plan_full(tab, r, 50000.0)[0])
    assert fast < slow


def test_the_full_plan_costs_no_more_than_a_short_horizon_one(tab):
    """On the planner's own cost, at one price: the whole-route optimum
    cannot lose to a planner that sees 300 m."""
    r = toy_route()
    lam = 4000.0

    def cost(v):
        i = np.rint(v / 0.5).astype(int)
        return float(sum(tab.energy_j[a, b] + lam * tab.dt_s[a, b]
                         for a, b in zip(i[:-1], i[1:])))

    full = plan_full(tab, r, lam)[0]
    short = plan_receding(tab, r, lam, horizon=30)
    assert cost(full) <= cost(short) + 1e-6


def test_the_true_cost_to_go_as_terminal_cost_recovers_the_full_plan(tab):
    """What the learned terminal cost is an approximation of. Given the
    exact one, the short horizon is the full planner."""
    r = toy_route()
    lam = 4000.0
    full, J, _ = plan_full(tab, r, lam)
    exact = lambda k, _lam: J[k]
    short = plan_receding(tab, r, lam, horizon=30, terminal=exact)
    assert np.array_equal(short, full)


def test_a_profile_becomes_a_trace_of_the_right_length_and_distance(tab):
    r = toy_route()
    v = plan_full(tab, r, 4000.0)[0]
    c = profile_to_cycle(r, v)
    assert np.sum(c.v_ref_mps) * c.dt_s == pytest.approx(r.distance_m, rel=1e-3)
    assert len(c.v_ref_mps) * c.dt_s == pytest.approx(
        planned_time_s(r, v) + 1.0, abs=0.2)


def test_the_student_is_held_to_the_stops_whatever_it_asks_for(tab):
    """A student that always asks for more speed is still stopped: the guard
    is arithmetic, not learned."""
    r = toy_route()
    greedy = learned.Mlp({"w0": np.zeros((4, 7)), "b0": np.zeros(4),
                          "w1": np.zeros((4, 4)), "b1": np.zeros(4),
                          "w2": np.zeros((1, 4)), "b2": np.array([5.0])})
    v = learned.plan_student(greedy, tab, r, 4000.0)
    broken = violations(r, v)
    assert broken["missed_stops"] == 0 and broken["over_limit_nodes"] == 0
    assert broken["over_brake_segments"] == 0


def test_a_cycle_obeys_the_route_made_from_it():
    r = route_from_cycle("hwfet")
    assert r.stop[0] and r.stop[-1]
    assert r.limit_mps.max() <= 27.0 and r.a_min_mps2 < 0.0 < r.a_max_mps2
    assert r.distance_m == pytest.approx(16510.0, abs=20.0)
