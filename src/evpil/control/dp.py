"""Dynamic programming: the global optimum the controllers are scored against.

Without this number, "energy-efficient" is unanchored (spec 4.3). A controller
that saves 3% against a rule-based baseline has said nothing until someone
knows whether 3.2% or 30% was available.

**What is being optimised, and why that is the whole decision space.**

The inner loop owns tracking, and the plant's acceleration is a function of
commanded torque and grade alone. Neither the regeneration blend nor the
auxiliary derate appears in that function, so the speed trajectory is
*exactly* invariant to the outer action: the same cycle produces the same
torque sequence whatever the energy manager does. The discharge ceiling is the
one action that could change it, and only by starving the tracker of power it
needs, which the tracking constraint forbids. So the discharge ceiling is a
safety limiter, not an optimisation lever, and the DP holds it at its maximum.
That is a result about the action space rather than an assumption about it,
and it applies to the RL policy in exactly the same way.

What remains is two decisions per outer step: how much braking energy to send
to the machine, and how much auxiliary load to shed. The first is free. The
second is not -- shedding the cabin heater saves energy the same way driving
slower does -- so it is priced explicitly and reported at two prices rather
than smuggled into a headline number.

**Why the reported figure comes from the plant, not from the value function.**

The DP carries state of charge as its only state. The RC branch of the
Thevenin model has a 20 s time constant, comparable to the horizon over which
a decision matters, and carrying it as a second dimension would square the
grid. It is instead taken from a nominal forward run and treated as exogenous.
That makes the value function an approximation, so it is used only to derive a
policy; the number in the results table comes from running that policy through
the full plant. The gap between the two is reported as evidence about how good
the approximation is, rather than assumed to be small.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from evpil.control.cycles import Cycle
from evpil.control.pid import (
    PidGains, PidState, feedforward_torque_nm, pid_step,
)
from evpil.control.rule_ems import EmsAction
from evpil.control.sim import DEFAULT_GAINS, OUTER_DECIMATION, Observation
from evpil.plant.auxiliary import aux_power_w
from evpil.plant.battery import ocv_v, r0_at
from evpil.plant.motor import clamp_torque, electrical_power_w
from evpil.plant.params import VehicleParams
from evpil.plant.plant import Plant


@dataclass(frozen=True)
class DpSpec:
    soc_grid_n: int = 161
    soc_span: float = 0.30           # grid half-width about the initial SoC
    blends: tuple[float, ...] = (0.0, 0.25, 0.5, 0.75, 1.0)
    derates: tuple[float, ...] = (0.0, 0.15, 0.30)
    # Watts of traction energy a watt of shed auxiliary load is worth. 0 makes
    # cabin comfort free, which is the upper bound on what shedding can buy;
    # 1 makes it worth exactly as much as the energy it saves, under which no
    # rational optimiser sheds anything.
    comfort_price: float = 0.0
    # Two of the actions tie exactly, often. Shedding the auxiliary load at
    # comfort_price 1.0 is a wash by construction -- the saving and the charge
    # are the same number -- and the regeneration blend does nothing at all
    # while the vehicle is driving. Ties are then broken by whatever
    # floating-point noise the value-function interpolation carries, so the
    # optimiser sheds cabin heat at random and, worse, writes blend 0 into
    # every driving stage. The second one is not free: a stage whose *mean*
    # power is positive can still contain braking, and the plant then throws
    # that recovery away.
    #
    # This is a preference, not a price: a tenth of a watt against a load of
    # kilowatts, large enough to dominate the interpolation noise and far too
    # small to outvote a real difference. It resolves ties toward recovering
    # more and intervening less.
    tie_break_w: float = 0.1


@dataclass(frozen=True)
class DpSolution:
    cycle: str
    spec: DpSpec
    soc_grid: np.ndarray
    policy_blend: np.ndarray         # (n_stages, n_soc)
    policy_derate: np.ndarray        # (n_stages, n_soc)
    predicted_wh: float              # the value function's own estimate
    stage_dt_s: float


def machine_power_trajectory(
    params: VehicleParams,
    cycle: Cycle,
    *,
    gains: PidGains = DEFAULT_GAINS,
    soc0: float = 0.80,
    t_ambient_c: float = 12.0,
    t_batt_c: float = 20.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Replay the cycle once and return (p_elec_w, v_rc_v, soc_frac) per step.

    `p_elec_w` is the machine's electrical power at the inverter terminals
    before the regeneration split and before the auxiliary load: positive
    driving, negative generating. It is the quantity the outer action divides
    up, and by the invariance argument above it does not depend on that action.
    """
    plant = Plant(params)
    state = plant.reset(soc0, t_ambient_c, t_batt_c)
    pid = PidState()

    n = len(cycle.v_ref_mps)
    dt = cycle.dt_s
    a_ref = np.gradient(cycle.v_ref_mps, dt)

    p_elec = np.empty(n)
    v_rc = np.empty(n)
    soc = np.empty(n)

    for k in range(n):
        grade = float(cycle.grade_rad[k])
        ff = feedforward_torque_nm(
            params, v_ref_mps=float(cycle.v_ref_mps[k]),
            a_ref_mps2=float(a_ref[k]), grade_rad=grade,
        )
        omega = (state.v_mps / params.wheel_radius_m) * params.gear_ratio
        limit = abs(clamp_torque(params.motor, params.motor.torque_max_nm,
                                 omega)) or 1e-6
        out = pid_step(gains, pid, v_ref_mps=float(cycle.v_ref_mps[k]),
                       v_meas_mps=state.v_mps, torque_ff_nm=ff,
                       torque_limit_nm=limit, dt_s=dt)
        pid = out.state

        torque = clamp_torque(params.motor, out.torque_nm, omega)
        p_elec[k] = electrical_power_w(params.motor, torque, omega)
        v_rc[k] = state.battery.v_rc_v
        soc[k] = state.battery.soc_frac

        step = plant.step(
            state, torque_nm=out.torque_nm, regen_blend=1.0,
            p_limit_w=params.motor.power_max_w, grade_rad=grade,
            t_ambient_c=t_ambient_c, dt_s=dt, p_aux_w=None,
        )
        state = step.state

    return p_elec, v_rc, soc


def _stage_means(x: np.ndarray, decim: int) -> np.ndarray:
    """Mean of each consecutive block of `decim` samples, padding the tail."""
    n_stages = int(np.ceil(len(x) / decim))
    padded = np.full(n_stages * decim, x[-1], dtype=float)
    padded[: len(x)] = x
    return padded.reshape(n_stages, decim).mean(axis=1)


def solve(
    params: VehicleParams,
    cycle: Cycle,
    *,
    spec: DpSpec = DpSpec(),
    soc0: float = 0.80,
    t_ambient_c: float = 12.0,
    t_batt_c: float = 20.0,
    gains: PidGains = DEFAULT_GAINS,
) -> DpSolution:
    """Backward value iteration over state of charge."""
    p_elec, v_rc, _ = machine_power_trajectory(
        params, cycle, gains=gains, soc0=soc0, t_ambient_c=t_ambient_c,
        t_batt_c=t_batt_c,
    )

    dt_stage = cycle.dt_s * OUTER_DECIMATION
    p_stage = _stage_means(p_elec, OUTER_DECIMATION)
    v_rc_stage = _stage_means(v_rc, OUTER_DECIMATION)
    n_stages = len(p_stage)

    bp = params.battery
    soc_lo = max(bp.soc_min, soc0 - spec.soc_span)
    soc_hi = min(bp.soc_max, soc0 + 0.02)
    soc_grid = np.linspace(soc_lo, soc_hi, spec.soc_grid_n)

    ocv = np.interp(soc_grid, bp.ocv_soc_points, bp.ocv_volts)
    r0 = r0_at(bp, t_batt_c)
    p_aux_full = aux_power_w(params.aux, t_ambient_c)

    blends = np.asarray(spec.blends, dtype=float)
    derates = np.asarray(spec.derates, dtype=float)
    # (n_soc, n_blend, n_derate) grids, evaluated per stage.
    B = blends[None, :, None]
    D = derates[None, None, :]

    value = np.zeros(spec.soc_grid_n)
    pol_b = np.zeros((n_stages, spec.soc_grid_n), dtype=np.int8)
    pol_d = np.zeros((n_stages, spec.soc_grid_n), dtype=np.int8)

    q_ah_s = 3600.0 * bp.capacity_ah

    for k in range(n_stages - 1, -1, -1):
        emf = ocv - v_rc_stage[k]
        emf_col = emf[:, None, None]

        p_m = float(p_stage[k])
        if p_m < 0.0:
            ceiling = np.minimum(params.regen.power_limit_w,
                                 bp.i_charge_max_a * np.maximum(emf_col, 0.0))
            p_machine = np.maximum(B * p_m, -ceiling)
            p_machine = np.where(soc_grid[:, None, None] >= bp.soc_max,
                                 0.0, p_machine)
            p_machine = np.broadcast_to(p_machine, (spec.soc_grid_n,
                                                    len(blends), len(derates)))
        else:
            p_machine = np.full((spec.soc_grid_n, len(blends), len(derates)),
                                p_m)

        p_aux = p_aux_full * (1.0 - D)
        p_target = p_machine + p_aux

        # Exact terminal current, the same lower root the plant solves for.
        disc = emf_col ** 2 - 4.0 * r0 * p_target
        i = np.where(disc <= 0.0, emf_col / (2.0 * r0),
                     (emf_col - np.sqrt(np.maximum(disc, 0.0))) / (2.0 * r0))
        i = np.clip(i, -bp.i_charge_max_a, bp.i_discharge_max_a)
        i = np.where((i > 0.0) & (soc_grid[:, None, None] <= bp.soc_min), 0.0, i)
        i = np.where((i < 0.0) & (soc_grid[:, None, None] >= bp.soc_max), 0.0, i)

        v_term = emf_col - i * r0
        p_actual = v_term * i

        soc_next = np.clip(soc_grid[:, None, None] - i * dt_stage / q_ah_s,
                           bp.soc_min, bp.soc_max)

        comfort = spec.comfort_price * (p_aux_full - p_aux)
        stage_cost = (p_actual + comfort
                      + spec.tie_break_w * (D + (1.0 - B))) * dt_stage

        total = stage_cost + np.interp(soc_next, soc_grid, value)

        flat = total.reshape(spec.soc_grid_n, -1)
        best = np.argmin(flat, axis=1)
        value = flat[np.arange(spec.soc_grid_n), best]
        pol_b[k] = (best // len(derates)).astype(np.int8)
        pol_d[k] = (best % len(derates)).astype(np.int8)

    start = int(np.argmin(np.abs(soc_grid - soc0)))
    return DpSolution(
        cycle=cycle.name, spec=spec, soc_grid=soc_grid,
        policy_blend=blends[pol_b], policy_derate=derates[pol_d],
        predicted_wh=float(value[start] / 3600.0),
        stage_dt_s=dt_stage,
    )


def dp_policy(solution: DpSolution, p_limit_w: float):
    """Wrap a solved DP table as a policy the evaluation harness can run.

    The lookup is on the realised state of charge, not on the one the DP
    predicted, so the policy is a genuine feedback law rather than a replayed
    open-loop schedule. That matters under the injected disturbances of
    spec 6.5, where the realised trajectory leaves the predicted one.
    """
    dt_stage = solution.stage_dt_s
    n_stages = solution.policy_blend.shape[0]
    grid = solution.soc_grid
    step = (grid[-1] - grid[0]) / (len(grid) - 1)

    def _policy(obs: Observation) -> EmsAction:
        k = min(int(obs.t_s / dt_stage), n_stages - 1)
        # Nearest node, not the insertion point: searchsorted rounds one cell
        # upward every time, which biases the looked-up action toward a fuller
        # pack than the vehicle actually has.
        j = int(np.clip(round((obs.soc_frac - grid[0]) / step), 0, len(grid) - 1))
        return EmsAction(
            regen_blend=float(solution.policy_blend[k, j]),
            p_limit_w=float(p_limit_w),
            aux_derate=float(solution.policy_derate[k, j]),
        )

    return _policy
