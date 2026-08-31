"""Outer loop, conventional arm: a rule-based energy manager.

This is the baseline the RL controller has to beat, and it is also the
guaranteed-working fallback if SAC does not converge (risk R1). It is
deliberately the kind of controller that ships: a handful of thresholds on
state of charge, speed and battery temperature, each of which a calibration
engineer could defend in a sentence.

It produces the same three-dimensional action the SAC policy will produce, so
the two are interchangeable at the interface and the comparison is of policies
rather than of plumbing:

    regen_blend      fraction of available braking sent to the machine, [0, 1]
    p_limit_w        discharge power ceiling, watts
    aux_derate       fraction of the auxiliary load shed, [0, 1]

The rules are stated as constants with reasons, not tuned. Tuning the baseline
against the test cycle would be the mirror image of the leakage this project
exists to avoid: the proposed method would then be compared against a baseline
that had seen data the method had not.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class RuleParams:
    # Regeneration is withheld as the pack fills. Charging a nearly full pack
    # is where charge acceptance collapses and where the plant's own current
    # limit would bind anyway, so the rule anticipates the limit rather than
    # letting the limit be hit.
    soc_regen_taper_start: float = 0.85
    soc_regen_off: float = 0.94          # matches BatteryParams.soc_max
    regen_blend_max: float = 1.0

    # Below this speed the machine's regeneration torque is small and blending
    # it with friction braking is what makes stops feel unpredictable. Real
    # vehicles fade regen out before standstill; so does this.
    v_regen_fade_mps: float = 2.0

    # Discharge ceiling. Full power is available in the normal band and is
    # withdrawn as the pack empties, which is the behaviour a driver of any
    # production EV would recognise.
    p_limit_max_w: float = 125000.0
    p_limit_min_w: float = 40000.0
    soc_derate_start: float = 0.20
    soc_derate_end: float = 0.07         # matches BatteryParams.soc_min

    # Auxiliary shedding is the last resort and is bounded: the HVAC load is a
    # cabin comfort function, and a controller that saves energy by switching
    # the heating off in winter has not saved anything a driver would accept.
    aux_derate_max: float = 0.30
    soc_aux_shed_start: float = 0.15


@dataclass(frozen=True)
class EmsAction:
    regen_blend: float
    p_limit_w: float
    aux_derate: float


def _taper(x: float, x_full: float, x_zero: float) -> float:
    """1 above `x_full`, 0 below `x_zero`, linear between. Order-agnostic."""
    if x_full == x_zero:
        return 1.0 if x >= x_full else 0.0
    return float(np.clip((x - x_zero) / (x_full - x_zero), 0.0, 1.0))


def rule_action(
    params: RuleParams,
    *,
    soc_frac: float,
    v_mps: float,
) -> EmsAction:
    """The baseline policy. A pure function of the state, by design.

    No memory means no mode to get stuck in, which is the property that makes
    this arm trustworthy as a fallback: whatever state the vehicle reaches,
    the command is defined and bounded.
    """
    blend = params.regen_blend_max
    blend *= 1.0 - _taper(soc_frac, params.soc_regen_off,
                          params.soc_regen_taper_start)
    blend *= _taper(v_mps, params.v_regen_fade_mps, 0.0)

    span = params.p_limit_max_w - params.p_limit_min_w
    p_limit = params.p_limit_min_w + span * _taper(
        soc_frac, params.soc_derate_start, params.soc_derate_end)

    aux_derate = params.aux_derate_max * (
        1.0 - _taper(soc_frac, params.soc_aux_shed_start,
                     params.soc_derate_end))

    return EmsAction(
        regen_blend=float(np.clip(blend, 0.0, 1.0)),
        p_limit_w=float(p_limit),
        aux_derate=float(np.clip(aux_derate, 0.0, 1.0)),
    )
