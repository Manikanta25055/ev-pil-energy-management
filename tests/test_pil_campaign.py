"""The PIL campaign harness, exercised without a board.

The campaign itself needs the ESP32-S3 in the loop, so what can be tested off
hardware is the part that decides what the board is asked to do and what is
made of its answers: the scenario-to-cycle transformation, the sensor-noise
injection, and the run loop's frame handling. A fake link stands in for the
firmware, which is enough to catch a protocol or accounting mistake before it
costs six hours of board time.
"""

from __future__ import annotations

import numpy as np
import pytest

from evpil.control.scenarios import AXES, BASELINE, NOISE_SIGMA
from evpil.protocol import (
    CRC_SIZE, HEADER_SIZE, FrameType, pack_actuation, unpack_state,
)
from scripts.run_pil_campaign import (
    CTRL_PERIOD_S, apply_noise, run_one, scaled_cycle,
)


def test_aggression_one_leaves_the_cycle_alone():
    v, a, g = scaled_cycle("us06", aggression=1.0, grade_offset_rad=0.0,
                           dt_s=CTRL_PERIOD_S)
    assert len(v) == 60001
    assert abs(float(np.max(v)) - 35.90) < 0.05


def test_aggression_shortens_the_cycle_and_raises_acceleration():
    v1, a1, _ = scaled_cycle("us06", aggression=1.0, grade_offset_rad=0.0,
                             dt_s=CTRL_PERIOD_S)
    v2, a2, _ = scaled_cycle("us06", aggression=1.5, grade_offset_rad=0.0,
                             dt_s=CTRL_PERIOD_S)
    # Same speeds, reached sooner: duration divides by the factor and peak
    # acceleration multiplies by it.
    assert abs(len(v2) / len(v1) - 1 / 1.5) < 0.01
    assert abs(float(np.max(v2)) - float(np.max(v1))) < 0.2
    ratio = float(np.max(np.abs(a2))) / float(np.max(np.abs(a1)))
    assert 1.35 < ratio < 1.65, ratio


def test_grade_offset_is_added_exactly():
    _, _, g0 = scaled_cycle("us06", aggression=1.0, grade_offset_rad=0.0,
                            dt_s=CTRL_PERIOD_S)
    _, _, g1 = scaled_cycle("us06", aggression=1.0, grade_offset_rad=0.03,
                            dt_s=CTRL_PERIOD_S)
    assert np.allclose(g1 - g0, 0.03)


def test_noise_touches_only_measured_channels():
    rng = np.random.default_rng(0)
    clean = {k: 1.0 for k in NOISE_SIGMA}
    clean["v_ref_mps"] = 12.0
    clean["a_ref_mps2"] = 0.5
    dirty = apply_noise(clean, scale=10.0, rng=rng)
    # The reference is not a measurement and must come through untouched.
    assert dirty["v_ref_mps"] == 12.0
    assert dirty["a_ref_mps2"] == 0.5
    assert any(dirty[k] != clean[k] for k in NOISE_SIGMA)


def test_noise_is_reproducible_from_the_seed():
    clean = {k: 1.0 for k in NOISE_SIGMA}
    a = apply_noise(clean, scale=3.0, rng=np.random.default_rng(7))
    b = apply_noise(clean, scale=3.0, rng=np.random.default_rng(7))
    assert a == b


def test_noise_scales_with_the_multiplier():
    clean = {k: 0.0 for k in NOISE_SIGMA}
    draws_lo = [apply_noise(clean, scale=1.0, rng=np.random.default_rng(i))
                for i in range(200)]
    draws_hi = [apply_noise(clean, scale=10.0, rng=np.random.default_rng(i))
                for i in range(200)]
    sd_lo = float(np.std([d["v_mps"] for d in draws_lo]))
    sd_hi = float(np.std([d["v_mps"] for d in draws_hi]))
    assert 7.0 < sd_hi / sd_lo < 13.0


class FakeBoard:
    """A stand-in for the firmware: ask for a state, answer with an action.

    It applies a fixed torque rather than a real PID. The run loop under test
    does not care what the controller decides, only that request, reply and
    actuation are sequenced and accounted for correctly.
    """

    def __init__(self, torque_nm: float = 150.0, n_steps: int = 400,
                 frames_dropped: int = 0):
        self.torque_nm = torque_nm
        self.n_steps = n_steps
        self.seq = 0
        self.pending = None
        self.sent_states: list[dict] = []
        self._frames_dropped = frames_dropped

    @property
    def stats(self) -> dict:
        """A property, exactly as SerialLink.stats is.

        The shape matters as much as the value: reading it as a method
        returns a dict and calling that dict raises, which is how a whole
        run was lost once.
        """
        return {"frames_ok": self.seq, "frames_bad": 0,
                "frames_dropped": self._frames_dropped, "open_attempts": 1}

    def recv(self, timeout_s: float = 0.5):
        if self.seq >= self.n_steps:
            return None
        if self.pending is None:
            self.seq += 1
            return (FrameType.STEP_REQ, self.seq, self.seq * 10_000, b"")
        payload = self.pending
        self.pending = None
        return (FrameType.ACTUATION, self.seq, self.seq * 10_000, payload)

    def send(self, frame: bytes) -> None:
        # The host answered a STEP_REQ; queue the actuation that answers it.
        self.sent_states.append(unpack_state(frame[HEADER_SIZE:-CRC_SIZE]))
        self.pending = pack_actuation(
            self.seq, self.seq * 10_000,
            [self.torque_nm, 0.5, 60_000.0, 0.0])[HEADER_SIZE:-CRC_SIZE]


def test_run_one_closes_the_loop_and_accounts_for_it():
    board = FakeBoard(n_steps=400)
    level = AXES["battery_state"][0]
    result = run_one(board, scenario=level, controller="rule", seed=0,
                     max_steps=200, port="/dev/fake")

    assert result["steps"] == 200
    assert result["distance_km"] > 0.0
    assert result["scenario"] == "battery_state"
    assert result["level"] == "high"
    assert result["controller"] == "rule"
    assert result["seed"] == 0
    assert result["soc_start"] == pytest.approx(level.soc0)
    # A constant positive torque drains the pack.
    assert result["soc_end"] < result["soc_start"]
    assert np.isfinite(result["tracking_rmse_mps"])
    assert result["equivalent_wh_per_km"] >= result["wh_per_km"]


def test_run_one_records_the_scenario_it_was_given():
    board = FakeBoard(n_steps=200)
    level = AXES["comm_delay"][2]
    result = run_one(board, scenario=level, controller="actor", seed=2,
                     max_steps=100, port="/dev/fake",
                     sleep=lambda _s: None)
    assert result["comm_delay_s"] == pytest.approx(0.030)
    assert result["noise_scale"] == pytest.approx(BASELINE.noise_scale)
    assert result["cycle"] == "us06"


def test_arm_check_rejects_an_actor_image_filed_as_rule():
    from scripts.run_pil_campaign import check_arm
    with pytest.raises(SystemExit) as e:
        check_arm({"controller": "rule", "actor_steps": 5965, "steps": 60000})
    assert "actor build" in str(e.value)


def test_arm_check_rejects_a_ruleless_actor_run():
    from scripts.run_pil_campaign import check_arm
    with pytest.raises(SystemExit) as e:
        check_arm({"controller": "actor", "actor_steps": 0, "steps": 60000})
    assert "no policy in it" in str(e.value)


def test_arm_check_passes_the_matching_pairs():
    from scripts.run_pil_campaign import check_arm
    check_arm({"controller": "actor", "actor_steps": 5965, "steps": 60000})
    check_arm({"controller": "rule", "actor_steps": 0, "steps": 60000})


def test_host_dropped_frames_are_read_from_the_link_property():
    """Regression: SerialLink.stats is a property, not a method."""
    board = FakeBoard(n_steps=200, frames_dropped=4)
    result = run_one(board, scenario=AXES["road_grade"][1], controller="rule",
                     seed=1, max_steps=100, port="/dev/fake")
    assert result["host_frames_dropped"] == 4
    # The campaign total folds the host's count in with the board's, the way
    # run_g3.py composes its dropped-frame figure.
    assert result["dropped_frames"] >= 4


def test_a_run_on_the_wrong_speed_estimator_is_refused():
    from scripts.run_pil_campaign import check_speed_estimator
    check_speed_estimator({"speed_est_mode": 3}, 3)
    check_speed_estimator({"speed_est_mode": 0}, None)
    with pytest.raises(SystemExit, match="speed_est_mode=0"):
        check_speed_estimator({"speed_est_mode": 0}, 4)
