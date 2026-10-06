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

    def _predict(self, torque_prev_nm: float, grade_rad: float,
                 dt_s: float) -> tuple[float, float]:
        """Where the model says the speed is now, and how sure it is."""
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
        return v + a * dt_s, self._P + self.q2

    def _correct(self, x_pred: float, P_pred: float, v_meas_mps: float) -> float:
        k = P_pred / (P_pred + self.r2)
        self._x = x_pred + k * (v_meas_mps - x_pred)
        self._P = (1.0 - k) * P_pred
        return self._x

    def step(self, *, v_meas_mps, torque_prev_nm, grade_rad, dt_s) -> float:
        if self._meter is not None:
            self._meter.push(v_meas_mps)
            if self._meter.new_block:
                self.r2 = max(self._meter.sigma_mps ** 2, self.r_floor2)
        if self._x is None:
            self._x = v_meas_mps
            return self._x
        x_pred, P_pred = self._predict(torque_prev_nm, grade_rad, dt_s)
        return self._correct(x_pred, P_pred, v_meas_mps)


@dataclass(frozen=True)
class FaultSettings:
    """Thresholds of the classical speed-sensor fault detector. Set on the
    training cycle by scripts/run_fault_arms.py --tune."""
    window: int = 20            # innovations in the mean test (200 ms)
    t_limit: float = 8.0        # mean over its own standard error
    gross_mps: float = 1.0      # a jump no vehicle makes in 10 ms
    gross_count: int = 2
    frozen_count: int = 10      # identical samples in a row
    clear_count: int = 50       # quiet samples before the flag is dropped
    # While flagged the estimate runs on the model and drifts from the truth,
    # so a sensor that has come back cannot be asked to agree with it as
    # closely as before. A reading within this band, and not frozen, counts
    # as quiet. An offset smaller than the band is let back in: one channel
    # cannot tell it from the model's own drift.
    clear_band_mps: float = 0.25


class FaultTolerantKalman(KalmanSpeed):
    """B4: the adaptive Kalman estimate plus a detector for a speed sensor
    that is stuck, has dropped out, or has picked up an offset.

    The detector watches the innovation, the gap between each measurement and
    where the model expected it. Three tests, cheapest first:

      gross   the gap is larger than any real change of speed in one step
      frozen  the last samples are identical to the bit, on a channel that
              was jittering a moment ago
      mean    over the last 200 ms the gap has a mean that is large against
              its own scatter. Scaling by the window's own scatter is what
              stops a sudden rise in noise, which widens the gap without
              biasing it, from being called a fault.

    While the flag is up the measurement is ignored and the estimate runs on
    the model alone, which is the fallback the design's section 3 names.
    """

    def __init__(self, params: VehicleParams, *, q_mps: float,
                 settings: FaultSettings = FaultSettings(),
                 r_floor_mps: float = 0.005) -> None:
        super().__init__(params, q_mps=q_mps, r_mps=0.02, adaptive=True,
                         r_floor_mps=r_floor_mps)
        self.s = settings
        self._innov: list[float] = []
        self._gross = 0
        self._same = 0
        self._last: float | None = None
        self._quiet = 0
        self._k = 0
        # Enough history to undo what a fault did to the estimate before it
        # was caught: the estimate as it stood, and the inputs since.
        self._past: list[tuple[float, float, float, float, float]] = []
        self.flagged = False
        self.alarm_steps: list[int] = []        # step index of each new flag
        self.flag_history: list[bool] = []

    def _tests(self, nu: float, v_meas_mps: float, S: float) -> bool:
        s = self.s
        self._gross = self._gross + 1 if abs(nu) > max(
            s.gross_mps, 8.0 * math.sqrt(S)) else 0
        self._same = self._same + 1 if v_meas_mps == self._last else 0
        self._last = v_meas_mps
        self._innov.append(nu)
        if len(self._innov) > s.window:
            self._innov.pop(0)

        if self._gross >= s.gross_count:
            return True
        if self._same >= s.frozen_count and self._meter.sigma_mps > 1e-4:
            return True
        if len(self._innov) == s.window:
            n = s.window
            m = sum(self._innov) / n
            var = sum((x - m) ** 2 for x in self._innov) / (n - 1)
            # The scatter is not allowed below what the filter itself expects,
            # or a noiseless stretch would make any offset look significant.
            se = math.sqrt(max(var, S) / n)
            if abs(m) > s.t_limit * se:
                return True
        return False

    def step(self, *, v_meas_mps, torque_prev_nm, grade_rad, dt_s) -> float:
        self._k += 1
        if self._x is None:
            self._x = v_meas_mps
            self._last = v_meas_mps
            self.flag_history.append(False)
            return self._x

        self._past.append((self._x, self._P, torque_prev_nm, grade_rad, dt_s))
        if len(self._past) > self.s.window + 1:
            self._past.pop(0)

        x_pred, P_pred = self._predict(torque_prev_nm, grade_rad, dt_s)
        nu = v_meas_mps - x_pred
        S = P_pred + self.r2
        suspect = abs(nu) > max(self.s.gross_mps, 8.0 * math.sqrt(S))
        fault_now = self._tests(nu, v_meas_mps, S)

        if not self.flagged:
            if fault_now:
                self.flagged = True
                self._quiet = 0
                self.alarm_steps.append(self._k - 1)
                # The samples that tripped the test were being blended in
                # while it made up its mind. Go back to the estimate from
                # before the window and bring it forward on the model alone.
                self._x, self._P = self._past[0][0], self._past[0][1]
                for _, _, tq, g, dt in self._past:
                    self._x, self._P = self._predict(tq, g, dt)
                self.flag_history.append(True)
                return self._x
        else:
            # Four deviations of the noise, where that is wider than the band:
            # at ten times the floor a healthy sample is outside 0.25 m/s one
            # time in five, and the flag would never drop.
            band = max(self.s.clear_band_mps, 4.0 * math.sqrt(self.r2))
            quiet = (abs(nu) < band
                     and self._same < self.s.frozen_count
                     and self._gross == 0)
            self._quiet = self._quiet + 1 if quiet else 0
            if self._quiet >= self.s.clear_count:
                self.flagged = False
                self._innov.clear()
        self.flag_history.append(self.flagged)

        if self.flagged or suspect:
            # Model only. A single wild sample is not blended in even before
            # the flag goes up. The uncertainty keeps growing, so the first
            # good measurement after the flag clears is taken almost whole.
            self._x, self._P = x_pred, P_pred
            return self._x

        # The noise level is only learned from samples believed to be good.
        self._meter.push(v_meas_mps)
        if self._meter.new_block:
            self.r2 = max(self._meter.sigma_mps ** 2, self.r_floor2)
        return self._correct(x_pred, P_pred, v_meas_mps)


class SpeedFault:
    """A fault on the speed measurement, applied after the noise.

      stuck    the reading freezes at its value when the fault starts
      dropout  the reading goes to zero
      bias     a constant offset appears (magnitude in m/s)
      drift    an offset that grows (magnitude in m/s per second)
    """

    KINDS = ("stuck", "dropout", "bias", "drift")

    def __init__(self, kind: str, onset_s: float, magnitude: float = 0.0,
                 duration_s: float = float("inf")) -> None:
        if kind not in self.KINDS:
            raise ValueError(kind)
        self.kind, self.onset_s = kind, onset_s
        self.magnitude, self.duration_s = magnitude, duration_s
        self._held: float | None = None

    def active(self, t_s: float) -> bool:
        return self.onset_s <= t_s < self.onset_s + self.duration_s

    def apply(self, t_s: float, v_meas_mps: float) -> float:
        if not self.active(t_s):
            self._held = None
            return v_meas_mps
        if self.kind == "stuck":
            if self._held is None:
                self._held = v_meas_mps
            return self._held
        if self.kind == "dropout":
            return 0.0
        if self.kind == "bias":
            return v_meas_mps + self.magnitude
        return v_meas_mps + self.magnitude * (t_s - self.onset_s)
