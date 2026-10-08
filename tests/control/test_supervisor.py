import numpy as np
import pytest

from evpil.control import accel_models as am
from evpil.control.cycles import Cycle
from evpil.control.rule_ems import EmsAction
from evpil.control.sim import fixed_policy, simulate
from evpil.control.speed_estimators import BiasAwareFaultKalman, SpeedFault
from evpil.control.supervisor import (
    Advice, Channel, FixedReviewer, N_FEATURES, Policy, RuleMonitor,
    Snapshot, Supervisor,
)
from evpil.control.tiny_rnn import TinyReviewer

POL = fixed_policy(EmsAction(1.0, 3e5, 0.0))
Q, QD = 0.002, 0.02


def cruise(n=6000, dt=0.01):
    t = np.arange(n) * dt
    v = np.clip(2.0 * t, 0.0, 15.0) + 1.5 * np.sin(2 * np.pi * t / 20.0) * (t > 8)
    return Cycle(name="cruise", dt_s=dt, v_ref_mps=v, grade_rad=np.zeros(n))


def run(params, est, *, err=None, fault=None, n=6000):
    return simulate(params, cruise(n), POL, speed_noise_mps=0.02,
                    accel_noise_mps2=0.05, seed=0, speed_estimator=est,
                    speed_fault=fault, accel_error_mps2=err, keep_trace=True)


def b7(params):
    return BiasAwareFaultKalman(params, q_mps=Q, q_d_mps2=QD)


def test_a_supervisor_with_no_reviewer_is_b7(params):
    fault = lambda: SpeedFault("bias", 30.0, 0.5, duration_s=5.0)
    err = am.wander(6000, 0.01, seed=4)
    alone = b7(params)
    a = run(params, alone, err=err, fault=fault())
    sup = Supervisor(b7(params), record=True)
    b = run(params, sup, err=err, fault=fault())
    assert a.energy_wh == b.energy_wh
    assert alone.flag_history == sup.flag_history
    assert len(sup.snapshots) == 600
    assert len(sup.snapshots[0].x) == N_FEATURES


def test_a_reviewer_that_says_fault_holds_the_flag_but_not_for_ever(params):
    """The hold is bounded: a reviewer stuck on 'fault' cannot keep a
    healthy sensor out past max_hold_s."""
    always = FixedReviewer((0.0, 1.0, 0.0, 0.0), "fault")
    sup = Supervisor(b7(params), fast=(always, Channel()),
                     policy=Policy(max_hold_s=3.0, use_vigilance=False))
    run(params, sup, fault=SpeedFault("bias", 30.0, 0.5, duration_s=2.0))
    flags = np.array(sup.flag_history)
    assert flags[3050:3300].all()          # held through and past the fault
    assert not flags[-1]                   # and let go
    assert sup.applied["hold"] > 0


def test_advice_older_than_its_expiry_is_not_used(params):
    always = FixedReviewer((0.0, 1.0, 0.0, 0.0), "fault")
    late = Supervisor(b7(params), slow=(always, Channel(delay_s=3.0)),
                      policy=Policy(expiry_s=1.5))
    alone = b7(params)
    fault = lambda: SpeedFault("bias", 30.0, 0.5, duration_s=5.0)
    a = run(params, alone, fault=fault())
    b = run(params, late, fault=fault())
    assert late.applied["expired"] > 0
    assert late.applied["hold"] == 0 and late.applied["vigilant"] == 0
    assert a.energy_wh == b.energy_wh


def test_an_outage_leaves_the_detector_running_alone(params):
    always = FixedReviewer((0.0, 1.0, 0.0, 0.0), "fault")
    ch = Channel(delay_s=0.15, outages=((0.0, 1e9),))
    sup = Supervisor(b7(params), slow=(always, ch))
    alone = b7(params)
    fault = lambda: SpeedFault("dropout", 30.0, duration_s=5.0)
    a = run(params, alone, fault=fault())
    b = run(params, sup, fault=fault())
    assert ch.lost == ch.sent > 0
    assert a.energy_wh == b.energy_wh


def test_a_channel_carries_one_request_at_a_time():
    ch = Channel(delay_s=0.5)
    adv = Advice(0, 0, (1.0, 0.0, 0.0, 0.0))
    ch.send(0.0, adv)
    ch.send(0.1, adv)
    assert ch.sent == 1 and ch.busy == 1
    assert ch.arrived(0.4) == [] and ch.arrived(0.5) == [adv]


def test_the_monitor_tells_a_sensor_offset_from_a_drifting_reference():
    m = RuleMonitor()
    base = dict(gap_sd=0.02, nu_sd=0.02, log_sigma=np.log10(0.02) + 2.0,
                accel_offset=0.0, frozen_share=0.0, flagged=1.0,
                flag_seconds=0.2, v_meas=0.5, torque=0.1)
    def snap(gap, nu):
        x = dict(base, gap_mean=gap, nu_mean=nu, gap_minus_nu=gap - nu)
        from evpil.control.supervisor import FEATURES
        return Snapshot(0, 0.0, 1, tuple(x[k] for k in FEATURES))
    for _ in range(3):
        p = m.review(snap(0.5, 0.5))       # away from both references
    assert p[1] + p[3] == pytest.approx(1.0)
    m.reset()
    for _ in range(3):
        p = m.review(snap(0.5, 0.0))       # only the dead reckoning has moved
    assert p[1] + p[3] == pytest.approx(0.0)
    assert p[2] + p[3] == pytest.approx(1.0)


@pytest.mark.parametrize("kind", ["gru", "fastgrnn"])
def test_the_numpy_cells_match_torch(kind):
    torch = pytest.importorskip("torch")
    from scripts.train_reviewer import Net
    torch.manual_seed(1)
    net = Net(kind, 16)
    x = torch.randn(1, 50, N_FEATURES)
    want = net(x)[0].detach().numpy()
    model = TinyReviewer(net.export())
    got = np.array([model.logits(x[0, t].numpy()) for t in range(50)])
    assert np.allclose(got, want, atol=1e-5)


def test_a_blend_of_zero_is_the_dead_reckoning_and_one_is_the_model(params):
    """A3: while flagged the loop may control on a weighted mix of the two
    fallback speeds. The ends of the range are the two speeds it had."""
    fault = lambda: SpeedFault("dropout", 30.0, duration_s=5.0)
    err = am.wander(6000, 0.01, seed=4)
    plain, zero, one, model = b7(params), b7(params), b7(params), b7(params)
    zero.fallback_blend, one.fallback_blend = 0.0, 1.0
    model.fallback_model = True
    a = run(params, plain, err=err, fault=fault())
    b = run(params, zero, err=err, fault=fault())
    c = run(params, one, err=err, fault=fault())
    d = run(params, model, err=err, fault=fault())
    assert a.energy_wh == b.energy_wh
    assert c.energy_wh == d.energy_wh
    assert a.energy_wh != c.energy_wh


def test_a_fixed_blend_needs_no_reviewer(params):
    sup = Supervisor(b7(params), policy=Policy(blend_fixed=0.5))
    half = b7(params)
    half.fallback_blend = 0.5
    fault = lambda: SpeedFault("stuck", 30.0, duration_s=5.0)
    a = run(params, sup, fault=fault())
    b = run(params, half, fault=fault())
    assert a.energy_wh == b.energy_wh


def test_a_reviewer_sets_the_blend_from_its_channel_diagnosis(params):
    degraded = FixedReviewer((0.0, 0.0, 1.0, 0.0), "accel")
    sup = Supervisor(b7(params), fast=(degraded, Channel()),
                     policy=Policy(fallback="blend", use_hold=False,
                                   use_release=False, use_vigilance=False))
    run(params, sup, fault=SpeedFault("stuck", 30.0, duration_s=5.0))
    assert sup.blend_seen and max(sup.blend_seen) == 1.0
