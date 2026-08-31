"""Gymnasium environment: the outer energy-management loop as an RL problem.

Week 7 is the ramp-up (risk R1): the environment, the reward and the wrapper
around the plant are built and checked now, so that week 8 spends its time on
convergence rather than on plumbing. Nothing here claims a trained policy.

Three properties are deliberate.

**The agent does not drive.** The inner PID tracks the cycle and the agent
never sees the torque command. An agent that could slow the vehicle down would
find that first, and every energy number afterwards would be worthless.

**The action is the same three-dimensional command the rule-based manager
emits**, so the arms differ in policy and in nothing else.

**Shedding the auxiliary load is priced in the reward.** The DP shows that
with comfort free the optimiser sheds the maximum on every step of every
cycle, which is not an energy-management result. The price is a stated
parameter, not a tuned one.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

try:
    import gymnasium as gym
    from gymnasium import spaces
except ModuleNotFoundError as exc:      # pragma: no cover - import guard
    raise ModuleNotFoundError(
        "gymnasium is required for evpil.control.env. "
        "pip install 'stable-baselines3>=2.3' 'gymnasium>=0.29'"
    ) from exc

from evpil.control.cycles import Cycle
from evpil.control.pid import (
    PidGains, PidState, feedforward_torque_nm, pid_step,
)
from evpil.control.sim import DEFAULT_GAINS, OUTER_DECIMATION
from evpil.plant.auxiliary import aux_power_w
from evpil.plant.motor import clamp_torque
from evpil.plant.params import VehicleParams
from evpil.plant.plant import Plant

OBS_NAMES: tuple[str, ...] = (
    "soc_frac", "v_mps", "a_mps2", "t_batt_c", "grade_rad",
    "tracking_error_mps", "forecast_mean_w", "forecast_max_w",
)
# Divisors that put each observation roughly in [-1, 1]. Fixed constants
# rather than a running normaliser, because the same numbers have to be
# compiled into the firmware when the actor is exported.
OBS_SCALE = np.array([1.0, 40.0, 5.0, 60.0, 0.1, 5.0, 50000.0, 80000.0],
                     dtype=np.float32)
OBS_CLIP = 10.0

# 3 s at the 10 ms inner period, matching the forecaster's horizon in spec 4.2.
FORECAST_STEPS = 300


def forecast_summary(
    cycle: Cycle, a_ref: np.ndarray, k: int, mass_kg: float,
    rot_mass_factor: float = 0.0,
) -> tuple[float, float]:
    """Mean and max of the next 3 s of reference-implied traction power.

    An oracle: it reads the cycle's own future. The trained forecaster
    replaces it once the actor is on the device, and reporting both is what
    separates "the preview helps" from "this particular forecaster helps".

    Shared by the training environment and by the evaluation adapter, because
    an agent evaluated on a differently-computed observation than it was
    trained on is being tested on a different problem.
    """
    end = min(k + FORECAST_STEPS, len(cycle.v_ref_mps))
    if k >= end:
        return 0.0, 0.0
    v = cycle.v_ref_mps[k:end]
    a = a_ref[k:end]
    p = mass_kg * (1.0 + rot_mass_factor) * a * v
    return float(p.mean()), float(p.max())


def scale_observation(raw: np.ndarray) -> np.ndarray:
    return np.clip(raw / OBS_SCALE, -OBS_CLIP, OBS_CLIP).astype(np.float32)


@dataclass(frozen=True)
class RewardWeights:
    energy_per_wh: float = 1.0
    tracking_per_m2s2: float = 5.0
    comfort_per_wh: float = 1.0        # price of shed auxiliary energy
    current_penalty: float = 2.0       # per ampere over the rated limit
    soc_penalty: float = 50.0          # per fraction below the floor


class EnergyManagementEnv(gym.Env):
    """One episode is one drive cycle, stepped at the 100 ms outer period."""

    metadata = {"render_modes": []}

    def __init__(
        self,
        params: VehicleParams,
        cycles: list[Cycle],
        *,
        gains: PidGains = DEFAULT_GAINS,
        weights: RewardWeights = RewardWeights(),
        soc0_range: tuple[float, float] = (0.55, 0.90),
        t_ambient_range: tuple[float, float] = (-5.0, 30.0),
        episode_steps: int = 600,
        use_forecast: bool = True,
        seed: int | None = None,
    ) -> None:
        super().__init__()
        if not cycles:
            raise ValueError("at least one cycle is required")
        self.params = params
        self.cycles = cycles
        self.gains = gains
        self.weights = weights
        self.soc0_range = soc0_range
        self.t_ambient_range = t_ambient_range
        self.episode_steps = episode_steps
        # Ablation A3 lives here: with this False the forecast channels are
        # held at zero and the agent has to manage without a preview.
        self.use_forecast = use_forecast

        self.plant = Plant(params)
        self._rng = np.random.default_rng(seed)

        self.action_space = spaces.Box(-1.0, 1.0, shape=(3,), dtype=np.float32)
        # Finite bounds, not infinities: OBS_SCALE already puts every channel
        # near unit range, and a declared bound is what the exported actor's
        # fixed-point input range will be derived from.
        self.observation_space = spaces.Box(
            -OBS_CLIP, OBS_CLIP, shape=(len(OBS_NAMES),), dtype=np.float32)

        self._p_limit_lo = 40000.0
        self._p_limit_hi = params.motor.power_max_w
        self._derate_max = 0.30

    # -- action mapping ----------------------------------------------------

    def decode_action(self, action: np.ndarray) -> tuple[float, float, float]:
        """[-1, 1]^3 to (regen_blend, p_limit_w, aux_derate).

        Affine, so the policy never has to learn a saturation to reach a
        boundary and the exported actor is one multiply-add per dimension.
        """
        a = np.clip(np.asarray(action, dtype=float), -1.0, 1.0)
        blend = 0.5 * (a[0] + 1.0)
        p_limit = self._p_limit_lo + 0.5 * (a[1] + 1.0) * (
            self._p_limit_hi - self._p_limit_lo)
        derate = 0.5 * (a[2] + 1.0) * self._derate_max
        return float(blend), float(p_limit), float(derate)

    # -- gym API -----------------------------------------------------------

    def reset(self, *, seed: int | None = None, options: dict | None = None):
        super().reset(seed=seed)
        if seed is not None:
            self._rng = np.random.default_rng(seed)

        self.cycle = self.cycles[self._rng.integers(len(self.cycles))]
        self._a_ref = np.gradient(self.cycle.v_ref_mps, self.cycle.dt_s)

        span = OUTER_DECIMATION * self.episode_steps
        last = max(1, len(self.cycle.v_ref_mps) - span)
        self._k0 = int(self._rng.integers(last))
        self._k = self._k0

        self.soc0 = float(self._rng.uniform(*self.soc0_range))
        self.t_ambient_c = float(self._rng.uniform(*self.t_ambient_range))
        self.state = self.plant.reset(self.soc0, self.t_ambient_c, 20.0)
        # Start at the reference speed rather than at rest: an episode that
        # begins mid-cycle at zero speed spends its first seconds on a
        # full-throttle catch-up the cycle never asked for, and the energy
        # spent there would be attributed to the policy.
        self.state = type(self.state)(
            v_mps=float(self.cycle.v_ref_mps[self._k0]),
            battery=self.state.battery, distance_m=0.0, energy_wh=0.0,
        )
        self.pid = PidState()
        self._a_meas = 0.0
        self._steps = 0
        return self._observe(), {}

    def _forecast(self) -> tuple[float, float]:
        if not self.use_forecast:
            return 0.0, 0.0
        return forecast_summary(self.cycle, self._a_ref, self._k,
                                self.params.mass_kg,
                                self.params.rot_mass_factor)

    def _observe(self) -> np.ndarray:
        f_mean, f_max = self._forecast()
        k = min(self._k, len(self.cycle.v_ref_mps) - 1)
        raw = np.array([
            self.state.battery.soc_frac, self.state.v_mps, self._a_meas,
            self.state.battery.t_batt_c, self.cycle.grade_rad[k],
            self.cycle.v_ref_mps[k] - self.state.v_mps, f_mean, f_max,
        ], dtype=np.float32)
        return scale_observation(raw)

    def step(self, action: np.ndarray):
        blend, p_limit, derate = self.decode_action(action)
        p = self.params
        dt = self.cycle.dt_s
        n = len(self.cycle.v_ref_mps)

        energy_ws = 0.0
        shed_ws = 0.0
        err_sq = 0.0
        over_current = 0.0

        for _ in range(OUTER_DECIMATION):
            k = min(self._k, n - 1)
            grade = float(self.cycle.grade_rad[k])
            v_ref = float(self.cycle.v_ref_mps[k])

            ff = feedforward_torque_nm(p, v_ref_mps=v_ref,
                                       a_ref_mps2=float(self._a_ref[k]),
                                       grade_rad=grade)
            omega = (self.state.v_mps / p.wheel_radius_m) * p.gear_ratio
            limit = abs(clamp_torque(p.motor, p.motor.torque_max_nm,
                                     omega)) or 1e-6
            out = pid_step(self.gains, self.pid, v_ref_mps=v_ref,
                           v_meas_mps=self.state.v_mps, torque_ff_nm=ff,
                           torque_limit_nm=limit, dt_s=dt)
            self.pid = out.state

            p_aux_full = aux_power_w(p.aux, self.t_ambient_c)
            p_aux = p_aux_full * (1.0 - derate)

            step = self.plant.step(
                self.state, torque_nm=out.torque_nm, regen_blend=blend,
                p_limit_w=p_limit, grade_rad=grade,
                t_ambient_c=self.t_ambient_c, dt_s=dt, p_aux_w=p_aux,
            )

            e = v_ref - self.state.v_mps
            err_sq += e * e
            energy_ws += step.p_batt_w * dt
            shed_ws += (p_aux_full - p_aux) * dt
            over_current += max(
                0.0, abs(step.i_batt_a) - p.battery.i_discharge_max_a) * dt
            self._a_meas = step.a_mps2
            self.state = step.state
            self._k += 1

        w = self.weights
        soc = self.state.battery.soc_frac
        reward = -(
            w.energy_per_wh * energy_ws / 3600.0
            + w.comfort_per_wh * shed_ws / 3600.0
            + w.tracking_per_m2s2 * err_sq / OUTER_DECIMATION
            + w.current_penalty * over_current
            + w.soc_penalty * max(0.0, p.battery.soc_min + 0.02 - soc)
        )

        self._steps += 1
        truncated = self._steps >= self.episode_steps or self._k >= n
        terminated = bool(soc <= p.battery.soc_min)

        info = {
            "energy_wh": energy_ws / 3600.0,
            "shed_wh": shed_ws / 3600.0,
            "tracking_rmse_mps": float(np.sqrt(err_sq / OUTER_DECIMATION)),
            "soc_frac": float(soc),
        }
        return self._observe(), float(reward), terminated, truncated, info
