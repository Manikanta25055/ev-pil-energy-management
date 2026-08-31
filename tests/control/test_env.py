import numpy as np
import pytest

gym = pytest.importorskip("gymnasium")

from evpil.control.cycles import Cycle
from evpil.control.env import OBS_NAMES, EnergyManagementEnv, RewardWeights
from tests.control.test_sim import short_cycle


@pytest.fixture
def env(params):
    return EnergyManagementEnv(params, [short_cycle()], episode_steps=50,
                               seed=0)


def test_it_satisfies_the_stable_baselines_contract(env):
    check_env = pytest.importorskip(
        "stable_baselines3.common.env_checker").check_env
    check_env(env)


def test_the_action_decoding_reaches_both_ends_of_every_range(env):
    lo = env.decode_action(np.array([-1.0, -1.0, -1.0]))
    hi = env.decode_action(np.array([1.0, 1.0, 1.0]))
    assert lo == pytest.approx((0.0, 40000.0, 0.0))
    assert hi[0] == pytest.approx(1.0)
    assert hi[2] == pytest.approx(0.30)
    mid = env.decode_action(np.array([0.0, 0.0, 0.0]))
    assert mid[0] == pytest.approx(0.5)


def test_out_of_range_actions_are_clipped_rather_than_extrapolated(env):
    assert env.decode_action(np.array([5.0, 5.0, 5.0])) == \
        pytest.approx(env.decode_action(np.array([1.0, 1.0, 1.0])))


def test_the_observation_stays_inside_its_declared_box(env):
    obs, _ = env.reset(seed=3)
    assert env.observation_space.contains(obs)
    for _ in range(50):
        obs, _, term, trunc, _ = env.step(env.action_space.sample())
        assert env.observation_space.contains(obs), obs
        if term or trunc:
            break


def test_the_agent_cannot_change_how_fast_the_vehicle_drives(params):
    """The property the whole reward design rests on. If the action moved the
    vehicle, the agent would learn to drive slower and call it efficiency."""
    speeds = []
    for a in (np.array([-1.0, 1.0, -1.0]), np.array([1.0, 1.0, 1.0])):
        e = EnergyManagementEnv(params, [short_cycle()], episode_steps=40,
                                seed=0)
        e.reset(seed=11)
        traj = []
        for _ in range(40):
            e.step(a)
            traj.append(e.state.v_mps)
        speeds.append(traj)
    assert np.allclose(speeds[0], speeds[1], atol=1e-12)


def test_shedding_the_cabin_load_is_charged_for_in_the_reward(params):
    """With comfort free the optimiser sheds the maximum on every step of
    every cycle, which is not an energy-management result."""
    priced = EnergyManagementEnv(params, [short_cycle()], episode_steps=20,
                                 weights=RewardWeights(comfort_per_wh=1.0),
                                 t_ambient_range=(-5.0, -5.0), seed=0)
    free = EnergyManagementEnv(params, [short_cycle()], episode_steps=20,
                               weights=RewardWeights(comfort_per_wh=0.0),
                               t_ambient_range=(-5.0, -5.0), seed=0)
    shed = np.array([1.0, 1.0, 1.0])
    rewards = []
    for e in (priced, free):
        e.reset(seed=5)
        total = 0.0
        for _ in range(20):
            _, r, *_ = e.step(shed)
            total += r
        rewards.append(total)
    assert rewards[0] < rewards[1]      # the same shedding costs more when priced


def test_the_forecast_channels_can_be_switched_off_for_ablation_a3(params):
    on = EnergyManagementEnv(params, [short_cycle()], episode_steps=10, seed=0)
    off = EnergyManagementEnv(params, [short_cycle()], episode_steps=10,
                              use_forecast=False, seed=0)
    o_on, _ = on.reset(seed=2)
    o_off, _ = off.reset(seed=2)
    i_mean = OBS_NAMES.index("forecast_mean_w")
    i_max = OBS_NAMES.index("forecast_max_w")
    assert o_off[i_mean] == 0.0 and o_off[i_max] == 0.0
    assert (o_on[i_mean], o_on[i_max]) != (0.0, 0.0)
    # Everything else must be identical, or the ablation would be comparing
    # two different problems rather than one problem with and without a preview.
    keep = [k for k in range(len(OBS_NAMES)) if k not in (i_mean, i_max)]
    assert np.allclose(o_on[keep], o_off[keep])
