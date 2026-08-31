"""Inner control loop: PID on speed with a physics feedforward term.

This loop owns tracking and nothing else. It runs at 10 ms on core 0 of the
device and it is deterministic, bounded and stateless between trips. Spec 4.3
puts tracking here on purpose: if the energy optimiser could also decide how
fast to drive, every energy saving it reported would be contaminated by the
possibility that it simply drove slower.

The feedforward term is the whole reason this is a small controller. Asking a
PID alone to produce several hundred newton-metres of torque means running it
at a large proportional gain, which is exactly what makes a loop ring. Here
the nominal road load is computed from the reference itself, and the feedback
term only has to cover what the nominal model gets wrong.

The state is carried explicitly rather than held in the object so that this
mirrors the C implementation in firmware/main/control.c step for step. The
firmware is the version that gets measured; a Python controller that quietly
does something different would invalidate every PIL result.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from evpil.plant.longitudinal import road_load
from evpil.plant.params import VehicleParams


@dataclass(frozen=True)
class PidGains:
    kp_nm_per_mps: float
    ki_nm_per_mps_s: float
    kd_nm_s_per_mps: float
    tau_d_s: float = 0.05          # derivative low-pass; 0 disables the filter
    i_limit_nm: float = 250.0      # integrator clamp, in torque units


@dataclass(frozen=True)
class PidState:
    integral_nm: float = 0.0
    d_filt_nm: float = 0.0
    e_prev_mps: float = 0.0


@dataclass(frozen=True)
class PidOutput:
    state: PidState
    torque_nm: float
    torque_ff_nm: float
    torque_fb_nm: float
    error_mps: float
    saturated: bool


def feedforward_torque_nm(
    params: VehicleParams,
    *,
    v_ref_mps: float,
    a_ref_mps2: float,
    grade_rad: float,
) -> float:
    """Motor torque that the nominal model says the reference demands.

    Uses the same road-load function the plant uses, which is a deliberate
    choice with a known consequence: on the host the feedforward is exact, so
    the feedback term only ever corrects the plant's saturations and the
    integrator's own lag. That flatters the tracking numbers relative to a
    vehicle, where the model is wrong. It is the right baseline anyway --
    every controller under comparison gets the same feedforward, so the
    comparison is unaffected, and the model error a real vehicle would add is
    injected deliberately as a scenario (spec 6.5) rather than left implicit.
    """
    p = params
    load = road_load(
        v_mps=v_ref_mps, a_mps2=a_ref_mps2, grade_rad=grade_rad,
        mass_kg=p.mass_kg, c_rr=p.c_rr, cd=p.cd,
        frontal_area_m2=p.frontal_area_m2, rot_mass_factor=p.rot_mass_factor,
    )
    f_wheel = load.tractive_n

    # Invert the same drivetrain convention the plant applies in its forward
    # direction, so a zero-error reference produces a zero-error torque.
    if f_wheel >= 0.0:
        return f_wheel * p.wheel_radius_m / (p.gear_ratio * p.drivetrain_eta)
    return f_wheel * p.wheel_radius_m * p.drivetrain_eta / p.gear_ratio


def pid_step(
    gains: PidGains,
    state: PidState,
    *,
    v_ref_mps: float,
    v_meas_mps: float,
    torque_ff_nm: float,
    torque_limit_nm: float,
    dt_s: float,
) -> PidOutput:
    """One inner-loop step. `torque_limit_nm` is the symmetric actuator bound.

    Anti-windup is conditional integration: the integrator is advanced only
    when doing so does not push a saturated output further into its stop. The
    alternative, integrating always and clamping the output, leaves the
    integrator charged through a long saturation -- a full-throttle US06
    acceleration -- and the loop then overshoots when the demand eases. Back
    calculation would work too and needs a tracking gain to tune; this needs
    none.
    """
    e = v_ref_mps - v_meas_mps

    # Filtered derivative on the error. An unfiltered one differentiates the
    # reference's own corners, and a resampled cycle has one every 10 ms.
    d_raw = (e - state.e_prev_mps) / dt_s if dt_s > 0.0 else 0.0
    if gains.tau_d_s > 0.0:
        alpha = dt_s / (gains.tau_d_s + dt_s)
        d_filt = state.d_filt_nm + alpha * (d_raw - state.d_filt_nm)
    else:
        d_filt = d_raw

    integral = state.integral_nm + gains.ki_nm_per_mps_s * e * dt_s
    integral = float(np.clip(integral, -gains.i_limit_nm, gains.i_limit_nm))

    fb = gains.kp_nm_per_mps * e + integral + gains.kd_nm_s_per_mps * d_filt
    raw = torque_ff_nm + fb
    torque = float(np.clip(raw, -torque_limit_nm, torque_limit_nm))
    saturated = raw != torque

    # Conditional integration: undo this step's accumulation when the output
    # is already against the stop it would be driven further into.
    if saturated and (raw - torque) * e > 0.0:
        integral = state.integral_nm

    fb = gains.kp_nm_per_mps * e + integral + gains.kd_nm_s_per_mps * d_filt
    raw = torque_ff_nm + fb
    torque = float(np.clip(raw, -torque_limit_nm, torque_limit_nm))

    return PidOutput(
        state=PidState(integral_nm=integral, d_filt_nm=d_filt, e_prev_mps=e),
        torque_nm=torque,
        torque_ff_nm=torque_ff_nm,
        torque_fb_nm=fb,
        error_mps=e,
        saturated=saturated,
    )
