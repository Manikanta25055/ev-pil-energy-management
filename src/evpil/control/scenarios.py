"""The six scenario axes of the PIL campaign, as data.

Spec section 6.5 trimmed the original plan's thirteen variations to six axes,
"retaining full robustness coverage at roughly half the runs". This module is
that table made executable, so the campaign script contains no scenario
knowledge of its own and the axes can be asserted by a test rather than read
out of a loop body.

**One axis moves at a time.** Every level inherits `BASELINE` and overrides a
single field. That is what makes a number attributable: if the actor's
tracking degrades under `comm_delay/severe`, the communication delay is the
only thing that changed. A scenario that varied two fields at once would
produce a result no one could assign a cause to, and a campaign of 36 such
runs would look thorough while answering nothing.

**Three levels, not three repeats.** Each axis is swept across three levels
and each level is run at its own RNG seed. The seed drives the sensor-noise
realisation, which is present in every scenario at a base floor rather than
only on the noise axis -- real measurements are never clean, and an otherwise
deterministic plant would return bit-identical results for three "seeds" and
report a standard deviation of exactly zero.

The noise floor is applied to measured channels only. `v_ref_mps` and
`a_ref_mps2` are the reference the controller is tracking, not a measurement
of anything, and perturbing them would be changing the drive cycle rather than
corrupting a sensor.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

# Per-channel one-sigma sensor noise at `noise_scale` 1.0, in the units the
# state frame carries. These are a plausible instrumentation floor for a
# vehicle bus rather than a measurement of this rig: the campaign varies the
# multiplier and reports against it, so the absolute figures set the zero of
# the sweep and are not themselves a claim.
NOISE_SIGMA: dict[str, float] = {
    "v_mps": 0.02,
    "a_mps2": 0.05,
    "soc_frac": 0.001,
    "i_batt_a": 0.50,
    "v_batt_v": 0.50,
    "t_ambient_c": 0.20,
    "grade_rad": 0.0005,
    "p_aux_w": 5.0,
    "t_batt_c": 0.20,
}


@dataclass(frozen=True)
class ScenarioLevel:
    """One point on one axis. Everything not named by the axis is BASELINE."""

    axis: str
    level: str
    cycle: str
    grade_offset_rad: float
    soc0: float
    noise_scale: float
    comm_delay_s: float
    aggression: float


# US06 is the aggressive cycle the control split reports on (spec 5.2), so it
# is the fixed background for every axis except the one that varies the cycle.
BASELINE = ScenarioLevel(
    axis="baseline",
    level="baseline",
    cycle="us06",
    grade_offset_rad=0.0,
    soc0=0.80,
    noise_scale=1.0,
    comm_delay_s=0.0,
    aggression=1.0,
)


def _level(axis: str, level: str, **override) -> ScenarioLevel:
    return replace(BASELINE, axis=axis, level=level, **override)


AXES: dict[str, tuple[ScenarioLevel, ...]] = {
    # Urban, highway, stop-and-go, via cycle choice. UDDS is the urban trace
    # with the stop-and-go content; HWFET is the steady highway one; US06 is
    # the aggressive mixed cycle and is also the baseline.
    "driving_condition": (
        _level("driving_condition", "urban", cycle="udds"),
        _level("driving_condition", "highway", cycle="hwfet"),
        _level("driving_condition", "aggressive_mixed", cycle="us06"),
    ),
    # A sweep from uphill through downhill, as a constant offset added to the
    # cycle's own grade profile. 0.03 rad is about 3%, a sustained motorway
    # gradient rather than a mountain pass.
    "road_grade": (
        _level("road_grade", "uphill", grade_offset_rad=0.03),
        _level("road_grade", "flat", grade_offset_rad=0.0),
        _level("road_grade", "downhill", grade_offset_rad=-0.03),
    ),
    # High, medium and low bands. The low band sits under the rule manager's
    # `soc_aux_shed_start` of 0.15 by the end of an aggressive cycle, which is
    # where the two controllers have the most room to disagree.
    "battery_state": (
        _level("battery_state", "high", soc0=0.85),
        _level("battery_state", "medium", soc0=0.55),
        _level("battery_state", "low", soc0=0.25),
    ),
    # A multiplier on NOISE_SIGMA. 1.0 is the floor every other scenario also
    # carries, so this axis starts where the rest of the campaign sits.
    "sensor_noise": (
        _level("sensor_noise", "floor", noise_scale=1.0),
        _level("sensor_noise", "elevated", noise_scale=3.0),
        _level("sensor_noise", "severe", noise_scale=10.0),
    ),
    # Latency injected on the host's reply. 10 ms is one control period, so
    # the board acts on a state one step old; 30 ms is three, which is inside
    # the staleness limit and therefore a degradation rather than a fault.
    # The blackout that crosses that limit is ablation A4's subject, not this
    # campaign's.
    "comm_delay": (
        _level("comm_delay", "none", comm_delay_s=0.0),
        _level("comm_delay", "one_period", comm_delay_s=0.010),
        _level("comm_delay", "three_periods", comm_delay_s=0.030),
    ),
    # Driver aggression as a time-scaling of the reference: the same speeds in
    # the same order, reached sooner. Accelerations scale with the factor and
    # the cycle finishes earlier, which is what "aggressive acceleration and
    # sudden braking" means for a trajectory-following controller. Scaling the
    # speeds instead would be a different cycle, not a different driver.
    "driver_aggression": (
        _level("driver_aggression", "normal", aggression=1.0),
        _level("driver_aggression", "brisk", aggression=1.25),
        _level("driver_aggression", "aggressive", aggression=1.50),
    ),
}


@dataclass(frozen=True)
class CampaignRun:
    """One cell of the campaign: an axis level, a controller, a seed."""

    axis: str
    level: str
    controller: str
    seed: int
    scenario: ScenarioLevel


def levels_for(axis: str) -> tuple[ScenarioLevel, ...]:
    """The three levels of one axis. Raises KeyError on an unknown axis."""
    return AXES[axis]


def scenario_runs(
    *,
    controllers: tuple[str, ...] = ("rule", "actor"),
    seeds: tuple[int, ...] = (0, 1, 2),
) -> tuple[CampaignRun, ...]:
    """The campaign, ordered controller-outermost.

    The order is not cosmetic. Selecting the controller is a rebuild and a
    reflash, because the firmware picks it at compile time on the presence of
    `sac_actor_weights.h`; there is no command frame that switches it. Running
    controller-outermost costs two flashes for the campaign instead of
    eighteen, and keeps every run of one arm on one image.

    Seed `i` is paired with level `i` so that all three levels of an axis are
    covered by the three runs, and each carries its own noise realisation.
    """
    runs: list[CampaignRun] = []
    for controller in controllers:
        for axis, levels in AXES.items():
            for seed, level in zip(seeds, levels, strict=True):
                runs.append(CampaignRun(
                    axis=axis,
                    level=level.level,
                    controller=controller,
                    seed=seed,
                    scenario=level,
                ))
    return tuple(runs)
