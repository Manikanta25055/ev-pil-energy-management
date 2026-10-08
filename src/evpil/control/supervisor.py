"""The supervisory architectures, with the reviewer as a slot.

`docs/2026-10-07-model-advancement-research.md`, section 12. The fast path
stays what it is: the detector B7 and the PID, every 10 ms. Around it sits a
slower loop that reviews what has just happened and may change a bounded
setting for what happens next:

    B7 acts -> 100 ms of outcome -> snapshot -> reviewer -> (delay) ->
    local check -> bounded setting -> B7

The reviewer is anything with `review(snapshot, history) -> Advice`. A rule
monitor, a tiny GRU, a FastGRNN cell and a hosted model all fit, and each is
given the same snapshot. What makes an architecture is where the reviewer
runs and how its answer gets back, and that is the `Channel`:

  A2  reviewer on the chip           no delay
  A1  post-action review, remote     70 ms to 1 s, jitter, loss, outages
  A6  reviewer on a nearby host      a few ms
  A5  a fast reviewer on the chip and a slow one behind a channel

A reviewer never sees the true speed, the fault schedule or anything from
the future. It does not command torque and cannot clear or raise a flag by
itself: it names a diagnosis, and `Supervisor._apply` maps the diagnosis to
one of four settings B7 already has, after checking the answer is still
about the present.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Protocol

import numpy as np

from evpil.control.block_features import BLOCK_STEPS
from evpil.control.speed_estimators import BiasAwareFaultKalman

# The restricted choices. Every reviewer answers with one probability each.
DIAGNOSES = ("healthy", "sensor_fault", "accel_degraded", "both")
FEATURES = (
    "gap_mean", "gap_sd", "nu_mean", "nu_sd", "gap_minus_nu", "log_sigma",
    "accel_offset", "frozen_share", "flagged", "flag_seconds", "v_meas",
    "torque",
)
N_FEATURES = len(FEATURES)
# The truth label calls the acceleration channel degraded when its slow error
# over a block is larger than this. Twice the training trips' median spread.
ACCEL_DEGRADED_MPS2 = 0.24


@dataclass(frozen=True)
class Snapshot:
    """What a reviewer is given: one 100 ms block, as the chip saw it."""
    block: int                  # index of the block this describes
    t_s: float                  # time at the end of the block
    flag_epoch: int             # how many times the flag has changed
    x: tuple[float, ...]        # FEATURES, scaled


@dataclass(frozen=True)
class Advice:
    request_block: int
    flag_epoch: int
    probs: tuple[float, ...]    # over DIAGNOSES
    source: str = ""

    @property
    def p_fault(self) -> float:
        return self.probs[1] + self.probs[3]

    @property
    def p_accel(self) -> float:
        return self.probs[2] + self.probs[3]


class Reviewer(Protocol):
    name: str

    def reset(self) -> None: ...
    def review(self, snap: Snapshot) -> tuple[float, ...]: ...


@dataclass
class Channel:
    """How a reviewer's answer gets back. Times in blocks of 100 ms are too
    coarse for a 70 ms link, so everything here is in control steps."""
    delay_s: float = 0.0
    jitter_s: float = 0.0
    loss: float = 0.0
    outages: tuple[tuple[float, float], ...] = ()   # (start_s, end_s)
    one_in_flight: bool = True
    seed: int = 0

    def __post_init__(self) -> None:
        self._rng = np.random.default_rng([self.seed, 7])
        self._flight: list[tuple[float, Advice]] = []
        self.sent = self.lost = self.busy = 0

    def send(self, t_s: float, advice: Advice) -> None:
        if self.delay_s <= 0.0 and self.jitter_s <= 0.0:
            self._flight.append((t_s, advice))
            self.sent += 1
            return
        if self.one_in_flight and self._flight:
            self.busy += 1
            return
        self.sent += 1
        if (self._rng.random() < self.loss
                or any(a <= t_s < b for a, b in self.outages)):
            self.lost += 1
            return
        d = self.delay_s + abs(self._rng.normal(0.0, self.jitter_s))
        self._flight.append((t_s + d, advice))

    def arrived(self, t_s: float) -> list[Advice]:
        out = [a for due, a in self._flight if due <= t_s + 1e-9]
        self._flight = [(due, a) for due, a in self._flight
                        if due > t_s + 1e-9]
        return out


@dataclass(frozen=True)
class Policy:
    """The local mapping from a diagnosis to a setting, and its limits."""
    p_hold: float = 0.6         # above this, a raised flag is held
    p_release: float = 0.2      # below this, a raised flag may be dropped
    p_accel: float = 0.5        # above this, fall back on the model
    p_vigilant: float = 0.6     # above this with no flag, look harder
    vigilance: float = 0.6
    expiry_s: float = 1.5       # advice older than this is not used
    max_hold_s: float = 10.0    # a hold cannot outlast this
    min_flag_s: float = 0.5     # no release before the fast path's own wait
    trigger: str = "always"     # or "event": ask only when something is up
    use_hold: bool = True
    use_release: bool = True
    use_fallback: bool = True
    use_vigilance: bool = True


class BlockFeatures:
    """The twelve inputs, accumulated over a block from quantities the
    detector already holds."""

    def __init__(self) -> None:
        self._gap: list[float] = []
        self._nu: list[float] = []
        self._same = 0
        self._v: list[float] = []
        self._tq: list[float] = []
        self._last: float | None = None

    def push(self, est: BiasAwareFaultKalman, v_meas: float,
             torque_nm: float) -> None:
        self._gap.append(est.last_gap)
        self._nu.append(est.last_nu)
        self._same += v_meas == self._last
        self._last = v_meas
        self._v.append(v_meas)
        self._tq.append(torque_nm)

    def full(self) -> bool:
        return len(self._gap) >= BLOCK_STEPS

    def pop(self, est: BiasAwareFaultKalman, flag_s: float) -> tuple:
        g, nu = np.array(self._gap), np.array(self._nu)
        clip = lambda x, lim: float(max(-lim, min(lim, x)))
        x = (
            clip(g.mean(), 5.0), clip(g.std(), 5.0),
            clip(nu.mean(), 5.0), clip(nu.std(), 5.0),
            clip(g.mean() - nu.mean(), 5.0),
            math.log10(max(math.sqrt(est.r2), 1e-3)) + 2.0,
            clip(est.accel_offset_mps2 * 5.0, 5.0),
            self._same / len(g),
            1.0 if est.flagged else 0.0,
            min(flag_s, 10.0) / 10.0,
            float(np.mean(self._v)) / 30.0,
            clip(float(np.mean(self._tq)) / 250.0, 2.0),
        )
        self.__init__()
        return x


class Supervisor:
    """B7 with a reviewer around it. Satisfies `SpeedEstimator`, so the
    registered evaluation runs it like any other arm.

    `fast` and `slow` are (reviewer, channel) pairs. With both, the slow
    answer is used while it is fresh and the fast one otherwise (A5).
    """

    def __init__(self, base: BiasAwareFaultKalman, *,
                 fast: tuple[Reviewer, Channel] | None = None,
                 slow: tuple[Reviewer, Channel] | None = None,
                 policy: Policy = Policy(), record: bool = False) -> None:
        self.base = base
        self.paths = [p for p in (slow, fast) if p is not None]
        for r, _ in self.paths:
            r.reset()
        self.policy = policy
        self._feat = BlockFeatures()
        self._k = 0
        self._block = 0
        self._epoch = 0
        self._was_flagged = False
        self._flag_s = 0.0
        self._hold_s = 0.0
        self._latest: list[tuple[float, Advice] | None] = [None] * len(self.paths)
        self.record = record
        self.snapshots: list[Snapshot] = []
        self.applied = {"hold": 0, "release": 0, "fallback": 0,
                        "vigilant": 0, "expired": 0, "stale_epoch": 0,
                        "requests": 0}

    # The registered evaluation reads these off an arm.
    @property
    def alarm_steps(self):
        return self.base.alarm_steps

    @property
    def alarm_tests(self):
        return self.base.alarm_tests

    @property
    def flag_history(self):
        return self.base.flag_history

    def _interesting(self, x: tuple) -> bool:
        """The event trigger: a flag up, or the reading away from either
        reference by more than noise explains."""
        return bool(x[8] or abs(x[0]) > 0.1 or abs(x[2]) > 0.1 or x[7] > 0.5)

    def _apply(self, t_s: float) -> None:
        b, p = self.base, self.policy
        advice = None
        for slot in self._latest:               # slow first, then fast
            if slot is None:
                continue
            asked_s, a = slot
            if t_s - asked_s > p.expiry_s:
                continue
            if a.flag_epoch != self._epoch:
                continue
            advice = a
            break
        b.hold_release = False
        b.vigilance = 1.0
        if advice is None:
            # Nothing usable: the detector runs as it would alone.
            b.fallback_model = False
            return
        if b.flagged:
            if p.use_fallback:
                want = advice.p_accel > p.p_accel
                self.applied["fallback"] += want != b.fallback_model
                b.fallback_model = want
            if (p.use_hold and advice.p_fault > p.p_hold
                    and self._hold_s < p.max_hold_s):
                b.hold_release = True
                self.applied["hold"] += 1
            elif (p.use_release and advice.p_fault < p.p_release
                  and self._flag_s >= p.min_flag_s):
                b.release_now = True
                self.applied["release"] += 1
        elif p.use_vigilance and advice.p_fault > p.p_vigilant:
            b.vigilance = p.vigilance
            self.applied["vigilant"] += 1

    def step(self, *, v_meas_mps, torque_prev_nm, grade_rad, dt_s,
             a_meas_mps2=0.0) -> float:
        b = self.base
        t_s = self._k * dt_s
        for i, (_, ch) in enumerate(self.paths):
            for a in ch.arrived(t_s):
                # Age counts from when the block it describes ended, so a
                # late answer to an old question is old however fresh it
                # looks on arrival.
                asked_s = (a.request_block + 1) * BLOCK_STEPS * dt_s
                if t_s - asked_s > self.policy.expiry_s:
                    self.applied["expired"] += 1
                elif a.flag_epoch != self._epoch:
                    self.applied["stale_epoch"] += 1
                elif (self._latest[i] is None
                      or asked_s >= self._latest[i][0]):
                    self._latest[i] = (asked_s, a)
        self._apply(t_s)

        out = b.step(v_meas_mps=v_meas_mps, torque_prev_nm=torque_prev_nm,
                     grade_rad=grade_rad, dt_s=dt_s, a_meas_mps2=a_meas_mps2)

        if b.flagged != self._was_flagged:
            self._epoch += 1
            self._was_flagged = b.flagged
            self._flag_s = self._hold_s = 0.0
            self._latest = [None] * len(self.paths)
            if not b.flagged:
                b.fallback_model = False
        elif b.flagged:
            self._flag_s += dt_s
            self._hold_s += dt_s if b.hold_release else 0.0

        self._feat.push(b, v_meas_mps, torque_prev_nm)
        self._k += 1
        if self._feat.full():
            snap = Snapshot(self._block, self._k * dt_s, self._epoch,
                            self._feat.pop(b, self._flag_s))
            if self.record:
                self.snapshots.append(snap)
            ask = (self.policy.trigger == "always"
                   or self._interesting(snap.x))
            for r, ch in self.paths:
                # A reviewer with memory is stepped every block so that its
                # state is the same whether or not its answer is sent.
                probs = r.review(snap)
                if ask:
                    self.applied["requests"] += 1
                    ch.send(self._k * dt_s, Advice(
                        snap.block, snap.flag_epoch, tuple(probs), r.name))
            self._block += 1
        return out


class RuleMonitor:
    """The ordinary numerical monitor: the comparison every learned or
    hosted reviewer has to beat. Two references, one vote.

    The reading is compared with the dead-reckoned speed (gap) and with the
    vehicle model's prediction (nu). A sensor fault moves the reading away
    from both by the same amount. A degraded acceleration channel moves the
    dead reckoning and leaves the model where it was, so the two references
    part and the reading stays with the model.
    """

    name = "monitor"

    def __init__(self, *, off_mps: float = 0.15, split_mps: float = 0.15,
                 offset_mps2: float = 0.1, memory: int = 3) -> None:
        self.off, self.split, self.b_lim = off_mps, split_mps, offset_mps2
        self.memory = memory
        self.reset()

    def reset(self) -> None:
        self._fault: list[bool] = []
        self._accel: list[bool] = []

    def review(self, snap: Snapshot) -> tuple[float, ...]:
        x = dict(zip(FEATURES, snap.x))
        noise = 10.0 ** (x["log_sigma"] - 2.0)
        lim = max(self.off, 2.0 * noise)
        if x["flagged"]:
            both_off = (abs(x["gap_mean"]) > lim and abs(x["nu_mean"]) > lim
                        and x["gap_mean"] * x["nu_mean"] > 0.0)
            fault = both_off or x["frozen_share"] > 0.5
        else:
            fault = x["frozen_share"] > 0.5
        accel = (abs(x["gap_minus_nu"]) > max(self.split, 2.0 * noise)
                 or abs(x["accel_offset"]) / 5.0 > self.b_lim)
        self._fault = (self._fault + [bool(fault)])[-self.memory:]
        self._accel = (self._accel + [bool(accel)])[-self.memory:]
        pf = sum(self._fault) / len(self._fault)
        pa = sum(self._accel) / len(self._accel)
        return ((1 - pf) * (1 - pa), pf * (1 - pa), (1 - pf) * pa, pf * pa)


class FixedReviewer:
    """Always the same answer. `healthy` is a reviewer that says nothing is
    wrong; with the policy's defaults it is the control for 'any advice at
    all changes the outcome'."""

    def __init__(self, probs=(1.0, 0.0, 0.0, 0.0), name="fixed") -> None:
        self.probs, self.name = tuple(probs), name

    def reset(self) -> None:
        pass

    def review(self, snap: Snapshot) -> tuple[float, ...]:
        return self.probs
