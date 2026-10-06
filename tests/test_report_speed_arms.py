"""The speed-arm report refuses a run filed under the wrong arm, and computes
its verdicts from the cells rather than from anything typed in."""

import copy

import pytest

from scripts.report_speed_arms import ARMS, CELLS, summarise, validate_arm


def arm_file(arm, energy, rmse=0.01, alarms=0):
    runs = []
    for (scenario, level), e in zip(CELLS, energy):
        runs.append({
            "scenario": scenario, "level": level, "controller": "rule",
            "actor_steps": 0, "speed_est_mode": ARMS[arm],
            "equivalent_wh_per_km": e, "tracking_rmse_mps": rmse,
            "tracking_max_mps": 0.1, "peak_current_a": 200.0, "regen_wh": 1.0,
            "ctrl_wcet_us": 70, "sensor_alarms": alarms,
            "sensor_flag_steps": 0, "dropped_frames": 3, "ctrl_late": 0,
            "steps": 60000, "duration_s": 600.0, "distance_km": 12.9,
        })
    return {"runs": runs}


B0 = [168.0, 154.0, 190.6, 190.8, 191.4, 201.0]
GOOD = [168.0, 154.0, 190.5, 190.7, 190.8, 191.0]


def validated(**over):
    files = {"b0": arm_file("b0", B0), "b5": arm_file("b5", GOOD),
             "b6": arm_file("b6", GOOD)}
    files.update(over)
    return {a: validate_arm(a, f) for a, f in files.items()}


def test_a_filter_that_removes_the_penalty_meets_the_criteria():
    out = summarise(validated())
    v = out["verdicts"]["b5"]
    assert v["fraction of b0's 10x penalty recovered"] == pytest.approx(
        (201.0 - 191.0) / (201.0 - 190.8))
    assert v["meets every criterion the board can test"]


def test_a_filter_that_changes_nothing_does_not():
    out = summarise(validated(b5=arm_file("b5", B0)))
    v = out["verdicts"]["b5"]
    assert v["fraction of b0's 10x penalty recovered"] == pytest.approx(0.0)
    assert not v["meets every criterion the board can test"]


def test_a_false_alarm_fails_the_detector_arm():
    out = summarise(validated(b6=arm_file("b6", GOOD, alarms=1)))
    assert out["verdicts"]["b6"]["false alarms on a healthy sensor"] == 6
    assert not out["verdicts"]["b6"]["meets every criterion the board can test"]


def test_worse_clean_tracking_fails():
    out = summarise(validated(b5=arm_file("b5", GOOD, rmse=0.02)))
    assert not out["verdicts"]["b5"]["clean tracking within 0.005 m/s of b0"]


def test_a_run_from_the_wrong_image_is_refused():
    bad = arm_file("b5", GOOD)
    bad["runs"][2]["speed_est_mode"] = 0
    with pytest.raises(ValueError, match="reports estimator 0"):
        validate_arm("b5", bad)


def test_a_disturbed_or_missing_cell_is_refused():
    bad = arm_file("b0", B0)
    bad["runs"][1]["dropped_frames"] = 40
    with pytest.raises(ValueError, match="disturbed"):
        validate_arm("b0", bad)
    short = copy.deepcopy(arm_file("b0", B0))
    short["runs"].pop()
    with pytest.raises(ValueError, match="5/6 cells"):
        validate_arm("b0", short)


def test_fault_counters_moving_without_a_detector_is_refused():
    with pytest.raises(ValueError, match="no detector"):
        validate_arm("b5", arm_file("b5", GOOD, alarms=2))
