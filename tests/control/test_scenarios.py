"""The six PIL scenario axes are data, and this pins what they are.

Spec section 6.5 trimmed thirteen variations to six axes. A campaign that
silently grew a seventh, or quietly swapped a cycle, would still produce 36
runs and a plausible table, so the axes are asserted here rather than trusted.

The load-bearing property is the last test: within one axis, every level must
differ from the baseline in that axis's field and in nothing else. That is
what makes a result attributable to the axis it is filed under.
"""

from __future__ import annotations

from dataclasses import fields

import pytest

from evpil.control.scenarios import (
    AXES, BASELINE, NOISE_SIGMA, ScenarioLevel, levels_for, scenario_runs,
)

EXPECTED_AXES = {
    "driving_condition",
    "road_grade",
    "battery_state",
    "sensor_noise",
    "comm_delay",
    "driver_aggression",
}

# Which field each axis is entitled to move.
AXIS_FIELD = {
    "driving_condition": "cycle",
    "road_grade": "grade_offset_rad",
    "battery_state": "soc0",
    "sensor_noise": "noise_scale",
    "comm_delay": "comm_delay_s",
    "driver_aggression": "aggression",
}


def test_exactly_the_six_spec_axes():
    assert set(AXES) == EXPECTED_AXES


def test_three_levels_per_axis():
    for axis, levels in AXES.items():
        assert len(levels) == 3, f"{axis} has {len(levels)} levels"


def test_level_names_are_unique_within_an_axis():
    for axis, levels in AXES.items():
        names = [lv.level for lv in levels]
        assert len(set(names)) == 3, f"{axis}: {names}"


def test_every_level_declares_its_own_axis():
    for axis, levels in AXES.items():
        for lv in levels:
            assert lv.axis == axis


def test_baseline_is_us06_flat_and_undisturbed():
    assert BASELINE.cycle == "us06"
    assert BASELINE.grade_offset_rad == 0.0
    assert BASELINE.noise_scale == 1.0
    assert BASELINE.comm_delay_s == 0.0
    assert BASELINE.aggression == 1.0


def test_noise_floor_covers_every_measured_channel():
    # The state frame is eleven floats; v_ref and a_ref are the reference and
    # are not measured, so nine channels can carry sensor noise.
    assert set(NOISE_SIGMA) == {
        "v_mps", "a_mps2", "soc_frac", "i_batt_a", "v_batt_v",
        "t_ambient_c", "grade_rad", "p_aux_w", "t_batt_c",
    }
    assert all(s > 0.0 for s in NOISE_SIGMA.values())


def test_campaign_is_thirty_six_runs():
    runs = scenario_runs(controllers=("rule", "actor"), seeds=(0, 1, 2))
    assert len(runs) == 36
    assert len({(r.axis, r.level, r.controller, r.seed) for r in runs}) == 36


def test_each_axis_moves_exactly_one_field():
    ignored = {"axis", "level"}
    for axis, levels in AXES.items():
        owned = AXIS_FIELD[axis]
        for lv in levels:
            for f in fields(ScenarioLevel):
                if f.name in ignored or f.name == owned:
                    continue
                assert getattr(lv, f.name) == getattr(BASELINE, f.name), (
                    f"{axis}/{lv.level} moved {f.name}, which belongs to "
                    f"another axis; the result would not be attributable"
                )


def test_each_axis_actually_varies_its_own_field():
    for axis, levels in AXES.items():
        owned = AXIS_FIELD[axis]
        values = {getattr(lv, owned) for lv in levels}
        assert len(values) == 3, f"{axis} does not vary {owned}: {values}"


def test_levels_for_rejects_an_unknown_axis():
    with pytest.raises(KeyError):
        levels_for("tyre_pressure")
