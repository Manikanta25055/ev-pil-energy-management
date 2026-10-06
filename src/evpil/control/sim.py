"""Closed-loop evaluation harness: plant, inner PID, outer energy manager.

The two rates are the ones the firmware runs (spec 4.4): the inner loop every
10 ms, the outer every 100 ms. Simulating both at 10 ms would make the host
results better than the device can be, and the point of this harness is to
predict what the device will do, not to flatter it.

A controller is anything that answers `action(observation) -> EmsAction`. The
rule-based manager, a fixed action, and later the SAC policy all satisfy that,
so the arms in the results table differ only in that one function.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable, Protocol

import numpy as np

from evpil.control.cycles import Cycle
from evpil.control.pid import (
    PidGains, PidState, feedforward_torque_nm, pid_step,
)
from evpil.control.rule_ems import EmsAction
from evpil.control.speed_filter import SpeedFilterState, speed_filter_step
from evpil.plant.auxiliary import aux_power_w
from evpil.plant.motor import clamp_torque
from evpil.plant.params import VehicleParams
from evpil.plant.plant import Plant, PlantState

OUTER_DECIMATION = 10          # 100 ms outer loop against a 10 ms inner loop


@dataclass(frozen=True)
class Observation:
    """What the outer loop sees. The forecast slot is filled in from W8."""
    t_s: float
    v_mps: float
    a_mps2: float
    soc_frac: float
    t_batt_c: float
    grade_rad: float
    tracking_error_mps: float
    p_batt_w: float
    forecast_mean_w: float = 0.0
    forecast_max_w: float = 0.0


class Policy(Protocol):
    def __call__(self, obs: Observation) -> EmsAction: ...


@dataclass(frozen=True)
class Trace:
    t_s: np.ndarray
    v_ref_mps: np.ndarray
    v_mps: np.ndarray
    torque_nm: np.ndarray
    p_batt_w: np.ndarray
    i_batt_a: np.ndarray
    soc_frac: np.ndarray
    p_regen_w: np.ndarray
    p_aux_w: np.ndarray
    regen_blend: np.ndarray
    p_limit_w: np.ndarray
    aux_derate: np.ndarray


@dataclass(frozen=True)
class Result:
    cycle: str
    tracking_rmse_mps: float
    tracking_max_mps: float
    energy_wh: float
    distance_km: float
    wh_per_km: float
    soc_start: float
    soc_end: float
    peak_current_a: float
    regen_wh: float
    aux_shed_wh: float
    trace: Trace | None = None

    @property
    def equivalent_wh(self) -> float:
        """Energy with shed cabin load charged back at what it saved.

        The comparable scalar across arms. Raw consumption is not: a
        controller that turns the heating down in a Munich winter shows a
        lower number without having managed any energy, in the same way a
        controller that drove slower would. Charging the shed load back at
        price 1.0 is the same convention the DP's comfort-priced arm uses and
        the same one the reinforcement-learning reward uses, so the three are
        on one scale.

        Report this beside raw consumption, never instead of it -- the gap
        between them is how much comfort an arm spent.
        """
        return self.energy_wh + self.aux_shed_wh

    @property
    def equivalent_wh_per_km(self) -> float:
        return (self.equivalent_wh / self.distance_km
                if self.distance_km > 0 else float("nan"))

    def summary(self) -> dict:
        d = {k: v for k, v in self.__dict__.items() if k != "trace"}
        d["equivalent_wh"] = self.equivalent_wh
        d["equivalent_wh_per_km"] = self.equivalent_wh_per_km
        return d


DEFAULT_GAINS = PidGains(
    kp_nm_per_mps=120.0, ki_nm_per_mps_s=40.0, kd_nm_s_per_mps=2.0,
    tau_d_s=0.05, i_limit_nm=250.0,
)


def simulate(
    params: VehicleParams,
    cycle: Cycle,
    policy: Policy,
    *,
    gains: PidGains = DEFAULT_GAINS,
    soc0: float = 0.80,
    t_ambient_c: float = 12.0,
    t_batt_c: float = 20.0,
    keep_trace: bool = False,
    ff_params: VehicleParams | None = None,
    ff_knows_grade: bool = True,
    speed_noise_mps: float = 0.0,
    delay_steps: int = 0,
    seed: int = 0,
    speed_filter_alpha: float = 1.0,
    speed_estimator=None,
) -> Result:
    """Run one cycle closed-loop and return its control metrics.

    `speed_noise_mps` and `delay_steps` are the sensor-noise and
    communication-delay scenarios of spec 6.5, injected here so that the host
    study and the device study perturb the same quantities. A delay of one
    outer step is what the pipelined firmware loop already carries.

    `speed_filter_alpha` low-passes the measured speed before the speed loop
    sees it (`evpil.control.speed_filter`). The default of 1.0 is no filter
    and leaves every result bit for bit as it was.

    `speed_estimator` is the general form of the same thing: any object with
    the `step` method of `evpil.control.speed_estimators.SpeedEstimator`. It
    is given the measurement, the torque commanded on the previous step and
    the grade, never the true speed. When it is passed the alpha is unused.

    `speed_noise_mps` may also be an array with one value per step, for a
    noise level that changes during the cycle.
    """
    rng = np.random.default_rng(seed)
    # The feedforward may be computed from a deliberately wrong vehicle. With
    # `ff_params` left as the plant's own parameters the nominal model is
    # exact and the feedback term has almost nothing to do, which is why the
    # tracking errors on a clean run are microscopic and should not be quoted
    # as evidence that the PID is well tuned. Passing a perturbed vehicle is
    # what tests the loop.
    ff_params = params if ff_params is None else ff_params
    plant = Plant(params)
    state: PlantState = plant.reset(soc0, t_ambient_c, t_batt_c)
    pid = PidState()

    n = len(cycle.v_ref_mps)
    dt = cycle.dt_s
    v_ref = cycle.v_ref_mps
    a_ref = np.gradient(v_ref, dt)

    action = policy(Observation(
        t_s=0.0, v_mps=0.0, a_mps2=0.0, soc_frac=soc0, t_batt_c=t_batt_c,
        grade_rad=float(cycle.grade_rad[0]), tracking_error_mps=0.0,
        p_batt_w=0.0,
    ))

    hist: dict[str, list[float]] = {k: [] for k in (
        "v", "torque", "p_batt", "i_batt", "soc", "p_regen", "p_aux",
        "blend", "p_limit", "derate")}
    delay_buf: list[float] = [0.0] * max(0, delay_steps)
    v_filt = SpeedFilterState()

    err_sq = 0.0
    err_max = 0.0
    peak_i = 0.0
    regen_ws = 0.0
    net_ws = 0.0
    aux_shed_ws = 0.0
    a_meas = 0.0
    p_batt_prev = 0.0
    torque_prev = 0.0
    noise_k = None
    if not np.isscalar(speed_noise_mps):
        noise_k = np.asarray(speed_noise_mps, dtype=float)
        if noise_k.shape != (n,):
            raise ValueError(
                f"speed_noise_mps has shape {noise_k.shape}, cycle has {n} steps")

    for k in range(n):
        v_true = state.v_mps
        sigma = float(noise_k[k]) if noise_k is not None else speed_noise_mps
        v_meas = v_true + (rng.normal(0.0, sigma) if sigma > 0.0 else 0.0)
        if delay_steps > 0:
            delay_buf.append(v_meas)
            v_meas = delay_buf.pop(0)
        grade = float(cycle.grade_rad[k])
        if speed_estimator is not None:
            v_meas = float(speed_estimator.step(
                v_meas_mps=v_meas, torque_prev_nm=torque_prev,
                grade_rad=grade if ff_knows_grade else 0.0, dt_s=dt))
        else:
            v_filt, v_meas = speed_filter_step(v_filt, v_meas,
                                               speed_filter_alpha)

        if k % OUTER_DECIMATION == 0:
            action = policy(Observation(
                t_s=k * dt, v_mps=v_true, a_mps2=a_meas,
                soc_frac=state.battery.soc_frac,
                t_batt_c=state.battery.t_batt_c, grade_rad=grade,
                tracking_error_mps=float(v_ref[k] - v_true),
                p_batt_w=p_batt_prev,
            ))

        ff = feedforward_torque_nm(
            ff_params, v_ref_mps=float(v_ref[k]), a_ref_mps2=float(a_ref[k]),
            grade_rad=grade if ff_knows_grade else 0.0,
        )
        omega = (v_true / params.wheel_radius_m) * params.gear_ratio
        limit = abs(clamp_torque(params.motor, params.motor.torque_max_nm,
                                 omega)) or 1e-6
        out = pid_step(gains, pid, v_ref_mps=float(v_ref[k]),
                       v_meas_mps=v_meas, torque_ff_nm=ff,
                       torque_limit_nm=limit, dt_s=dt)
        pid = out.state
        torque_prev = out.torque_nm

        p_aux_full = aux_power_w(params.aux, t_ambient_c)
        p_aux = p_aux_full * (1.0 - action.aux_derate)
        aux_shed_ws += (p_aux_full - p_aux) * dt

        step = plant.step(
            state, torque_nm=out.torque_nm, regen_blend=action.regen_blend,
            p_limit_w=action.p_limit_w, grade_rad=grade,
            t_ambient_c=t_ambient_c, dt_s=dt, p_aux_w=p_aux,
        )

        e = float(v_ref[k]) - v_true
        err_sq += e * e
        err_max = max(err_max, abs(e))
        peak_i = max(peak_i, abs(step.i_batt_a))
        regen_ws += max(0.0, -step.p_regen_w) * dt
        net_ws += step.p_batt_w * dt
        a_meas = step.a_mps2
        p_batt_prev = step.p_batt_w

        if keep_trace:
            hist["v"].append(v_true)
            hist["torque"].append(out.torque_nm)
            hist["p_batt"].append(step.p_batt_w)
            hist["i_batt"].append(step.i_batt_a)
            hist["soc"].append(state.battery.soc_frac)
            hist["p_regen"].append(step.p_regen_w)
            hist["p_aux"].append(step.p_aux_w)
            hist["blend"].append(action.regen_blend)
            hist["p_limit"].append(action.p_limit_w)
            hist["derate"].append(action.aux_derate)

        state = step.state

    distance_km = state.distance_m / 1000.0
    # Net energy out of the pack: the integral of battery power, so recovered
    # energy is already subtracted. `PlantState.energy_wh` integrates only the
    # positive part, which is gross draw rather than consumption, and using it
    # here would credit a controller with recovering nothing.
    energy_wh = net_ws / 3600.0

    trace = None
    if keep_trace:
        trace = Trace(
            t_s=np.arange(n) * dt, v_ref_mps=v_ref,
            v_mps=np.array(hist["v"]), torque_nm=np.array(hist["torque"]),
            p_batt_w=np.array(hist["p_batt"]),
            i_batt_a=np.array(hist["i_batt"]),
            soc_frac=np.array(hist["soc"]),
            p_regen_w=np.array(hist["p_regen"]),
            p_aux_w=np.array(hist["p_aux"]),
            regen_blend=np.array(hist["blend"]),
            p_limit_w=np.array(hist["p_limit"]),
            aux_derate=np.array(hist["derate"]),
        )

    return Result(
        cycle=cycle.name,
        tracking_rmse_mps=float(np.sqrt(err_sq / n)),
        tracking_max_mps=float(err_max),
        energy_wh=float(energy_wh),
        distance_km=float(distance_km),
        wh_per_km=float(energy_wh / distance_km) if distance_km > 0 else float("nan"),
        soc_start=float(soc0),
        soc_end=float(state.battery.soc_frac),
        peak_current_a=float(peak_i),
        regen_wh=float(regen_ws / 3600.0),
        aux_shed_wh=float(aux_shed_ws / 3600.0),
        trace=trace,
    )


def fixed_policy(action: EmsAction) -> Policy:
    """A constant action, for reference arms and for ablation controls."""
    def _policy(obs: Observation) -> EmsAction:
        return action
    return _policy
