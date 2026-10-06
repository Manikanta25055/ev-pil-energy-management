"""A first-order low-pass on measured speed, ahead of the speed loop.

The inner loop acts on every sample it is given. When the speed measurement is
noisy it answers the noise with torque, alternating drive and regeneration,
and the round trip through the motor and the pack is paid for in energy: at
ten times the noise floor the unfiltered loop uses 5.1% more on US06
(`docs/superpowers/specs/2026-10-06-decision-model-design.md`, section 2).

The filter is y += alpha * (x - y). Alpha 1.0 is no filter, and is handled as
an exact pass-through rather than by the arithmetic, because y + 1.0 * (x - y)
is not always x in floating point and "the default changes nothing" has to be
true to the bit. `firmware/main/control.c` carries the same function, and
`tests/control/test_c_parity.py` holds the two together.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SpeedFilterState:
    y_mps: float = 0.0
    primed: bool = False


def speed_filter_step(
    state: SpeedFilterState, v_meas_mps: float, alpha: float
) -> tuple[SpeedFilterState, float]:
    """Advance the filter by one sample and return the speed to control on.

    The first sample is taken as it comes. Starting the state at zero would
    hand the loop a step equal to the vehicle's speed whenever a run begins
    in motion.
    """
    if not 0.0 < alpha <= 1.0:
        raise ValueError(f"alpha must be in (0, 1], got {alpha!r}")
    if alpha >= 1.0 or not state.primed:
        y = v_meas_mps
    else:
        y = state.y_mps + alpha * (v_meas_mps - state.y_mps)
    return SpeedFilterState(y_mps=y, primed=True), y
