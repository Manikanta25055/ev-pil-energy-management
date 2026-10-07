"""Why the fault detector raised its flag on a healthy sensor, on the board.

The first speed-arms campaign saw one false alarm from B6, in the urban cell.
Two more runs of that cell on firmware that reports which test fired and where
gave the same answer both times: the mean test, at control loop 125,950, with
the speed reading at 0.47 m/s. The same place twice is not a link hiccup.

This replays the cell on the laptop. The campaign's own run loop and plant are
used unchanged, with the same noise seed, and the board is replaced by a
Python copy of what its control task does: the pipelined loop (act on the
state from the previous request, predict with the command before last), the
rule manager, the speed controller and the B6 estimate. If the alarm
reproduces here, on the same step, then it comes from the detector and the
noise it was given, and the replay can show the one thing the board cannot:
the true speed beside the detector's dead-reckoned one.

Laptop only. No board.

    PYTHONPATH="src:." python3 scripts/replay_b6_alarm.py
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

from evpil.control.cycles import load_cycle
from evpil.control.pid import PidState, feedforward_torque_nm, pid_step
from evpil.control.rule_ems import RuleParams, rule_action
from evpil.control.scenarios import AXES, NOISE_SIGMA
from evpil.control.sim import DEFAULT_GAINS
from evpil.control.speed_estimators import FaultSettings, KinematicFaultKalman
from evpil.plant.motor import clamp_torque
from evpil.plant.plant import Plant
from evpil.protocol import (
    CRC_SIZE, HEADER_SIZE, FrameType, pack_actuation, unpack_state,
)
from scripts.identify_params import params_from_json
from scripts.run_pil_campaign import run_one

DT = 0.01
TAU_S = 2.0


class PythonBoard:
    """What the firmware's control task does, one request at a time."""

    def __init__(self, params, n_steps: int, q_mps: float, q_d_mps2: float):
        self.p = params
        self.n = n_steps
        self.seq = 0
        self.pending = None
        self.held = None
        self.pid = PidState()
        self.est = KinematicFaultKalman(params, q_mps=q_mps, q_d_mps2=q_d_mps2,
                                        tau_s=TAU_S)
        self.tq = self.tq2 = 0.0
        self.rules = RuleParams()
        self.log: list[tuple] = []      # (seq, v_meas, a_meas, v_dr, flagged)

    @property
    def stats(self) -> dict:
        return {"frames_ok": self.seq, "frames_bad": 0, "frames_dropped": 0,
                "open_attempts": 1}

    def recv(self, timeout_s: float = 0.5):
        if self.seq >= self.n:
            return None
        if self.pending is None:
            self.seq += 1
            return (FrameType.STEP_REQ, self.seq, self.seq * 10_000, b"")
        payload, self.pending = self.pending, None
        return (FrameType.ACTUATION, self.seq, self.seq * 10_000, payload)

    def send(self, frame: bytes) -> None:
        incoming = unpack_state(frame[HEADER_SIZE:-CRC_SIZE])
        h = self.held
        if h is None:
            act = [0.0, 1.0, 125000.0, 0.0]
        else:
            ems = rule_action(self.rules, soc_frac=h["soc_frac"], v_mps=h["v_mps"])
            ff = feedforward_torque_nm(
                self.p, v_ref_mps=h["v_ref_mps"], a_ref_mps2=h["a_ref_mps2"],
                grade_rad=h["grade_rad"])
            omega = (h["v_mps"] / self.p.wheel_radius_m) * self.p.gear_ratio
            limit = abs(clamp_torque(self.p.motor, self.p.motor.torque_max_nm,
                                     omega)) or 1e-6
            v_ctl = self.est.step(
                v_meas_mps=h["v_mps"], a_meas_mps2=h["a_mps2"],
                torque_prev_nm=self.tq2, grade_rad=h["grade_rad"], dt_s=DT)
            self.log.append((self.seq, h["v_mps"], h["a_mps2"],
                             self.est._v_dr, self.est.flagged))
            out = pid_step(DEFAULT_GAINS, self.pid, v_ref_mps=h["v_ref_mps"],
                           v_meas_mps=v_ctl, torque_ff_nm=ff,
                           torque_limit_nm=limit, dt_s=DT)
            self.pid = out.state
            self.tq2, self.tq = self.tq, out.torque_nm
            act = [out.torque_nm, ems.regen_blend, ems.p_limit_w, ems.aux_derate]
        self.pending = pack_actuation(
            self.seq, self.seq * 10_000, act)[HEADER_SIZE:-CRC_SIZE]
        self.held = incoming


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tuned", default="docs/week11-speed-arms-tuned.json")
    ap.add_argument("--board", nargs="*", default=[
        "docs/week12-b6-alarm-check-1.json", "docs/week12-b6-alarm-check-2.json"])
    ap.add_argument("--out-json", default="docs/week12-b6-alarm-replay.json")
    args = ap.parse_args()

    params = params_from_json("data/i3_params.json")
    tuned = json.loads(Path(args.tuned).read_text())["b5"]
    level = AXES["driving_condition"][0]
    assert level.level == "urban"
    n = len(load_cycle(level.cycle, dt_s=DT).v_ref_mps)

    truth: list[float] = []
    original = Plant.step

    def recording(self, state, **kw):
        truth.append(state.v_mps)
        return original(self, state, **kw)

    Plant.step = recording
    try:
        board = PythonBoard(params, n + 10, tuned["q_mps"], tuned["q_d_mps2"])
        result = run_one(board, scenario=level, controller="rule", seed=0,
                         port="replay", params=params)
    finally:
        Plant.step = original

    log = np.array(board.log, dtype=float)
    # The state acted on at request s was sent at request s-1, and is the
    # plant's state before its step number s-2.
    v_true = np.array([truth[int(s) - 2] for s in log[:, 0]])
    dr_err = log[:, 3] - v_true
    settled = slice(2000, len(log) - 10)

    alarms = []
    for step, test in zip(board.est.alarm_steps, board.est.alarm_tests):
        j = step - 1                    # log row of the step the flag went up
        w = slice(j - FaultSettings().window + 1, j + 1)
        gaps = log[w, 1] - (log[j - FaultSettings().window:j, 3] + log[w, 2] * DT)
        alarms.append({
            "control_step": int(step), "cycle_time_s": step * DT, "test": int(test),
            "reference_speed_mps": float(load_cycle(level.cycle, dt_s=DT)
                                         .v_ref_mps[min(step, n - 1)]),
            "true_speed_mps": float(v_true[j]),
            "speed_reading_mps": float(log[j, 1]),
            "dead_reckoned_mps": float(log[j - 1, 3]),
            "dead_reckoning_error_mps": float(dr_err[j - 1]),
            "mean_gap_of_window_mps": float(gaps.mean()),
            "mean_speed_noise_of_window_mps": float((log[w, 1] - v_true[w]).mean()),
        })

    sigma_v, sigma_a = NOISE_SIGMA["v_mps"], NOISE_SIGMA["a_mps2"]
    window = FaultSettings().window
    out = {
        "provenance": "replay on the laptop of the urban cell, same plant, "
                      "run loop and noise seed as the board run",
        "energy_wh_per_km": result["equivalent_wh_per_km"],
        "alarms": alarms,
        "board_runs": [
            {k: r[k] for k in ("sensor_alarms", "sensor_alarm_test",
                               "sensor_alarm_loop", "sensor_alarm_loop_first",
                               "sensor_alarm_v_mmps", "sensor_alarm_gap_mmps",
                               "equivalent_wh_per_km")}
            for path in args.board if Path(path).exists()
            for r in json.loads(Path(path).read_text())["runs"]
            if r["level"] == "urban"],
        "dead_reckoning_error": {
            "sd_mps": float(dr_err[settled].std()),
            "min_mps": float(dr_err[settled].min()),
            "max_mps": float(dr_err[settled].max()),
            "expected_sd_from_acceleration_noise_mps":
                sigma_a * DT * math.sqrt(TAU_S / (2 * DT)),
        },
        "mean_test": {
            "threshold_mps": FaultSettings().t_limit * sigma_v / math.sqrt(window),
            "what_it_allows_for": "the speed noise on the window's mean, "
                                  f"{sigma_v / math.sqrt(window):.4f} m/s",
            "what_it_leaves_out": "the error of the dead-reckoned speed it is "
                                  "compared with",
        },
        "plant_acceleration_matches_speed":
            bool(abs(float(np.mean(np.diff(v_true[settled]) / DT))) < 0.05),
    }
    Path(args.out_json).write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({k: out[k] for k in ("alarms", "board_runs",
                                           "dead_reckoning_error", "mean_test")},
                     indent=1))
    print(f"wrote {args.out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
