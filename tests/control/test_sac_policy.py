import numpy as np
import pytest

pytest.importorskip("gymnasium")

from evpil.control.env import (
    OBS_NAMES, EnergyManagementEnv, forecast_summary, scale_observation,
)
from evpil.control.sac_policy import (
    decode_action, observation_vector,
)
from evpil.control.sim import Observation
from tests.control.test_sim import short_cycle


def test_the_evaluation_decoder_mirrors_the_training_one(params):
    """The adapter and the environment must map an action identically. If they
    drift, the policy is evaluated with different actuator ranges than it was
    trained with, and nothing in the numbers would show it."""
    env = EnergyManagementEnv(params, [short_cycle()], seed=0)
    hi = params.motor.power_max_w
    rng = np.random.default_rng(0)
    for _ in range(200):
        a = rng.uniform(-1.5, 1.5, size=3)
        blend, p_limit, derate = env.decode_action(a)
        got = decode_action(a, hi)
        assert got.regen_blend == pytest.approx(blend)
        assert got.p_limit_w == pytest.approx(p_limit)
        assert got.aux_derate == pytest.approx(derate)


def test_the_evaluation_observation_matches_the_training_one(params):
    """Same state, same vector. The adapter rebuilds the observation with the
    environment's own functions rather than a copy, and this pins that."""
    cycle = short_cycle()
    env = EnergyManagementEnv(params, [cycle], episode_steps=20, seed=0)
    obs_env, _ = env.reset(seed=4)

    k = env._k
    a_ref = np.gradient(cycle.v_ref_mps, cycle.dt_s)
    obs = Observation(
        t_s=k * cycle.dt_s, v_mps=env.state.v_mps, a_mps2=0.0,
        soc_frac=env.state.battery.soc_frac,
        t_batt_c=env.state.battery.t_batt_c,
        grade_rad=float(cycle.grade_rad[k]),
        tracking_error_mps=0.0, p_batt_w=0.0,
    )
    got = observation_vector(obs, cycle, a_ref, params, use_forecast=True)
    assert got == pytest.approx(obs_env, rel=1e-6, abs=1e-7)


def test_switching_the_forecast_off_zeroes_only_the_forecast_channels(params):
    cycle = short_cycle()
    a_ref = np.gradient(cycle.v_ref_mps, cycle.dt_s)
    obs = Observation(t_s=1.0, v_mps=12.0, a_mps2=0.4, soc_frac=0.7,
                      t_batt_c=20.0, grade_rad=0.0, tracking_error_mps=0.1,
                      p_batt_w=1000.0)
    on = observation_vector(obs, cycle, a_ref, params, use_forecast=True)
    off = observation_vector(obs, cycle, a_ref, params, use_forecast=False)
    i_mean = OBS_NAMES.index("forecast_mean_w")
    i_max = OBS_NAMES.index("forecast_max_w")
    assert off[i_mean] == 0.0 and off[i_max] == 0.0
    keep = [k for k in range(len(OBS_NAMES)) if k not in (i_mean, i_max)]
    assert np.allclose(on[keep], off[keep])


def test_the_forecast_looks_forward_and_runs_out_at_the_end(params):
    cycle = short_cycle()
    a_ref = np.gradient(cycle.v_ref_mps, cycle.dt_s)
    early = forecast_summary(cycle, a_ref, 100, params.mass_kg)
    assert early[1] >= early[0]                       # max is at least the mean
    # Past the last sample there is nothing to preview, and an empty slice
    # must not become a NaN that propagates into the policy input.
    past_end = forecast_summary(cycle, a_ref, len(cycle.v_ref_mps),
                                params.mass_kg)
    assert past_end == (0.0, 0.0)


def test_the_scaled_observation_is_clipped_not_wrapped():
    huge = np.full(len(OBS_NAMES), 1e9, dtype=np.float32)
    out = scale_observation(huge)
    assert np.all(np.isfinite(out))
    assert float(out.max()) == pytest.approx(10.0)
