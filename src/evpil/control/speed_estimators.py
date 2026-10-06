"""The classical arms of the decision-model study: what turns a measured
speed into the speed the loop controls on.

`docs/superpowers/specs/2026-10-06-decision-model-design.md`, section 6. A
learned decision model is only worth building if it beats these, so they are
written to be good rather than to be beaten.

  PassThrough        B0  the loop as shipped
  FixedFilter        B1  one first-order filter, always on
  VarianceThreshold  B2  estimates the noise from the jitter in the speed
                         samples and picks the filter from a table
  KalmanSpeed        B3  predicts the speed from the torque it commanded and
                         corrects with the measurement

Every estimator sees the same things the firmware's control task has: the
measurement, the torque it sent last step, the grade, and the reference. None
sees the true speed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol

from evpil.control.block_features import BLOCK_STEPS
from evpil.control.speed_filter import SpeedFilterState, speed_filter_step
from evpil.plant.longitudinal import road_load
from evpil.plant.motor import clamp_torque
from evpil.plant.params import VehicleParams


class SpeedEstimator(Protocol):
    def step(self, *, v_meas_mps: float, torque_prev_nm: float,
             grade_rad: float, dt_s: float) -> float: ...


class PassThrough:
    """B0."""

    def step(self, *, v_meas_mps, torque_prev_nm, grade_rad, dt_s) -> float:
        return v_meas_mps


class FixedFilter:
    """B1."""

    def __init__(self, alpha: float) -> None:
        self.alpha = alpha
        self._st = SpeedFilterState()

    def step(self, *, v_meas_mps, torque_prev_nm, grade_rad, dt_s) -> float:
        self._st, y = speed_filter_step(self._st, v_meas_mps, self.alpha)
        return y


class JitterMeter:
    """Noise level on the speed channel, from the 10 ms differences.

    White noise of standard deviation s on each sample makes the difference of
    two neighbours spread by s*sqrt(2). A steady acceleration shifts every
    difference by the same amount and so moves their mean, not their spread;
    only jerk leaks in, and over 100 ms it is small. The estimate is the
    per-block spread averaged over the last `blocks` blocks.
    """

    def __init__(self, blocks: int = 8) -> None:
        self._blocks = blocks
        self._recent: list[float] = []
        self._diffs: list[float] = []
        self._prev: float | None = None
        self.sigma_mps = 0.0
        self.new_block = False

    def push(self, v_meas_mps: float) -> None:
        self.new_block = False
        if self._prev is not None:
            self._diffs.append(v_meas_mps - self._prev)
        self._prev = v_meas_mps
        if len(self._diffs) < BLOCK_STEPS:
            return
        m = sum(self._diffs) / len(self._diffs)
        var = sum((d - m) ** 2 for d in self._diffs) / len(self._diffs)
        self._diffs.clear()
        self._recent.append(math.sqrt(var) / math.sqrt(2.0))
        if len(self._recent) > self._blocks:
            self._recent.pop(0)
        self.sigma_mps = sum(self._recent) / len(self._recent)
        self.new_block = True


@dataclass(frozen=True)
class RegimeTable:
    """Filter coefficient per noise regime, quietest first, and the noise
    levels (m/s) that separate them. Chosen on the training cycles by
    scripts/tune_speed_arms.py; the defaults here are that script's output."""
    alphas: tuple[float, ...] = (1.0, 0.3, 0.1)
    bounds_mps: tuple[float, ...] = (0.035, 0.11)
    # Fraction of a bound, each side. With an 8-block average the estimate of
    # a level sitting exactly on a bound wanders by about a tenth; 0.25 holds
    # that to 4 changes in ten minutes where 0.15 gave 32.
    hysteresis: float = 0.25
    persist_blocks: int = 3


class VarianceThreshold:
    """B2. A hand-written version of the decision the model would make."""

    def __init__(self, table: RegimeTable = RegimeTable()) -> None:
        assert len(table.alphas) == len(table.bounds_mps) + 1
        self.table = table
        self._meter = JitterMeter()
        self._st = SpeedFilterState()
        self.regime = 0
        self._pending = 0
        self._pending_n = 0
        self.regime_history: list[int] = []     # one entry per 100 ms block

    def _wanted(self, sigma: float) -> int:
        """The regime sigma calls for, with a dead band about each bound so a
        level sitting on one does not flap."""
        t = self.table
        r = self.regime
        while r < len(t.bounds_mps) and sigma > t.bounds_mps[r] * (1 + t.hysteresis):
            r += 1
        while r > 0 and sigma < t.bounds_mps[r - 1] * (1 - t.hysteresis):
            r -= 1
        return r

    def step(self, *, v_meas_mps, torque_prev_nm, grade_rad, dt_s) -> float:
        self._meter.push(v_meas_mps)
        if self._meter.new_block:
            want = self._wanted(self._meter.sigma_mps)
            if want == self.regime:
                self._pending_n = 0
            elif want == self._pending:
                self._pending_n += 1
            else:
                self._pending, self._pending_n = want, 1
            if self._pending_n >= self.table.persist_blocks:
                self.regime, self._pending_n = self._pending, 0
            self.regime_history.append(self.regime)
        self._st, y = speed_filter_step(
            self._st, v_meas_mps, self.table.alphas[self.regime])
        return y


class KalmanSpeed:
    """B3. One state, the speed.

    Predict: the speed moves by what the commanded torque and the road load
    say it should, using the same vehicle model the feedforward uses. Correct:
    blend in the measurement, weighted by how noisy it is believed to be.

    Because the prediction follows the torque, a low gain does not lag the way
    a low-pass does. What a low gain costs instead is trust in the model: if
    the vehicle is heavier than the model thinks, the estimate drifts toward
    the model between corrections. `q_mps` is the allowance for that.

    `r_mps` fixed gives the textbook filter. `adaptive=True` replaces it each
    block with the noise level measured from the speed jitter.
    """

    def __init__(self, params: VehicleParams, *, q_mps: float, r_mps: float,
                 adaptive: bool = False, r_floor_mps: float = 0.005) -> None:
        self.p = params
        self.q2 = q_mps * q_mps
        self.r2 = r_mps * r_mps
        self.adaptive = adaptive
        self.r_floor2 = r_floor_mps * r_floor_mps
        self._meter = JitterMeter() if adaptive else None
        self._x: float | None = None
        self._P = self.r2

    def step(self, *, v_meas_mps, torque_prev_nm, grade_rad, dt_s) -> float:
        if self._meter is not None:
            self._meter.push(v_meas_mps)
            if self._meter.new_block:
                self.r2 = max(self._meter.sigma_mps ** 2, self.r_floor2)
        if self._x is None:
            self._x = v_meas_mps
            return self._x

        p = self.p
        v = self._x
        omega = (v / p.wheel_radius_m) * p.gear_ratio
        torque = clamp_torque(p.motor, torque_prev_nm, omega)
        if torque >= 0.0:
            f_wheel = torque * p.gear_ratio * p.drivetrain_eta / p.wheel_radius_m
        else:
            f_wheel = torque * p.gear_ratio / (p.drivetrain_eta * p.wheel_radius_m)
        load = road_load(
            v_mps=v, a_mps2=0.0, grade_rad=grade_rad, mass_kg=p.mass_kg,
            c_rr=p.c_rr, cd=p.cd, frontal_area_m2=p.frontal_area_m2,
            rot_mass_factor=p.rot_mass_factor)
        f_resist = load.rolling_n + load.aero_n + load.grade_n
        a = (f_wheel - f_resist) / (p.mass_kg * (1.0 + p.rot_mass_factor))

        x_pred = v + a * dt_s
        P_pred = self._P + self.q2
        k = P_pred / (P_pred + self.r2)
        self._x = x_pred + k * (v_meas_mps - x_pred)
        self._P = (1.0 - k) * P_pred
        return self._x
