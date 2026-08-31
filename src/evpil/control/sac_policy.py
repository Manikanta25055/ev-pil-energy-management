"""Run a trained actor as a policy inside the evaluation harness.

The training environment steps 300-sample windows; the results table is whole
cycles through `evpil.control.sim.simulate`, the same harness every other arm
is scored in. This adapter is what lets one policy be scored by both, and it
rebuilds the observation with the environment's own functions rather than a
copy of them. An agent evaluated on a differently-computed observation than it
was trained on is being tested on a different problem, and the difference is
invisible in the numbers.
"""

from __future__ import annotations

import numpy as np

from evpil.control.actor import Actor
from evpil.control.cycles import Cycle
from evpil.control.env import (
    OBS_NAMES, forecast_summary, scale_observation,
)
from evpil.control.rule_ems import EmsAction
from evpil.control.sim import Observation
from evpil.plant.params import VehicleParams

P_LIMIT_LO_W = 40000.0


def decode_action(action: np.ndarray, p_limit_hi_w: float,
                  derate_max: float = 0.30) -> EmsAction:
    """Mirror of EnergyManagementEnv.decode_action, on the evaluation side."""
    a = np.clip(np.asarray(action, dtype=float), -1.0, 1.0)
    return EmsAction(
        regen_blend=float(0.5 * (a[0] + 1.0)),
        p_limit_w=float(P_LIMIT_LO_W
                        + 0.5 * (a[1] + 1.0) * (p_limit_hi_w - P_LIMIT_LO_W)),
        aux_derate=float(0.5 * (a[2] + 1.0) * derate_max),
    )


def observation_vector(
    obs: Observation, cycle: Cycle, a_ref: np.ndarray, params: VehicleParams,
    *, use_forecast: bool,
) -> np.ndarray:
    k = min(int(round(obs.t_s / cycle.dt_s)), len(cycle.v_ref_mps) - 1)
    if use_forecast:
        f_mean, f_max = forecast_summary(cycle, a_ref, k, params.mass_kg,
                                         params.rot_mass_factor)
    else:
        f_mean, f_max = 0.0, 0.0

    raw = np.array([
        obs.soc_frac, obs.v_mps, obs.a_mps2, obs.t_batt_c,
        float(cycle.grade_rad[k]), float(cycle.v_ref_mps[k]) - obs.v_mps,
        f_mean, f_max,
    ], dtype=np.float32)
    assert len(raw) == len(OBS_NAMES)
    return scale_observation(raw)


def actor_policy(actor: Actor, cycle: Cycle, params: VehicleParams, *,
                 use_forecast: bool = True):
    """Wrap an exported actor as a policy `simulate` can call."""
    a_ref = np.gradient(cycle.v_ref_mps, cycle.dt_s)
    p_limit_hi = params.motor.power_max_w

    def _policy(obs: Observation) -> EmsAction:
        x = observation_vector(obs, cycle, a_ref, params,
                               use_forecast=use_forecast)
        return decode_action(actor.forward(x), p_limit_hi)

    return _policy
