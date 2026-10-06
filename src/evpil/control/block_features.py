"""What the decision model reads: the last 3.2 s, as 32 blocks of 100 ms.

The 10 ms control task sees every sample; the decision model runs every
100 ms and cannot afford to. So the control task reduces each run of ten
samples to ten numbers as it goes, a handful of adds per step, and the model
reads the last 32 of those blocks
(`docs/superpowers/specs/2026-10-06-decision-model-design.md`, section 3).

The features are chosen to carry what a filter decision needs: how much the
speed measurement jitters from one sample to the next, whether the torque
command is flipping sign, and enough of the operating point to tell jitter
from a real manoeuvre.

Spread is computed about the block's first sample. The firmware has
single-precision arithmetic only, and a sum of squares of a 300 A current
taken about zero loses a 0.1 A ripple to rounding. This module does the same
so that the two agree for the same reason, not by luck; the arithmetic here is
float32 throughout. `firmware/main/features.c` is the other copy and
`tests/control/test_features_c_parity.py` holds them together.
"""

from __future__ import annotations

import numpy as np

BLOCK_STEPS = 10        # 10 ms samples per block
WINDOW_BLOCKS = 32      # blocks the model reads

FEATURE_NAMES: tuple[str, ...] = (
    "v_mean",       # measured speed, block mean
    "dv_std",       # spread of the 10 ms speed differences: the jitter itself
    "a_mean",       # measured acceleration, block mean
    "a_std",
    "tq_mean",      # torque command, block mean
    "tq_flips",     # sign changes of the torque command in the block
    "i_mean",       # battery current, block mean
    "i_std",
    "v_ref",        # reference at the end of the block
    "a_ref",
)

# Divisors that put each feature roughly in [-1, 1]. Constants, not a running
# normaliser, because the same numbers are compiled into the firmware.
FEATURE_SCALE = np.array(
    [40.0, 0.5, 5.0, 5.0, 250.0, 10.0, 350.0, 100.0, 40.0, 5.0],
    dtype=np.float32)

_F = np.float32


class _Spread:
    """Mean and population standard deviation of a block, in float32, with the
    sums taken about the block's first value."""

    __slots__ = ("x0", "s1", "s2")

    def __init__(self) -> None:
        self.x0 = _F(0.0)
        self.s1 = _F(0.0)
        self.s2 = _F(0.0)

    def add(self, x: np.float32, first: bool) -> None:
        if first:
            self.x0, self.s1, self.s2 = x, _F(0.0), _F(0.0)
            return
        d = _F(x - self.x0)
        self.s1 = _F(self.s1 + d)
        self.s2 = _F(self.s2 + _F(d * d))

    def mean(self, n: int) -> np.float32:
        return _F(self.x0 + _F(self.s1 / _F(n)))

    def std(self, n: int) -> np.float32:
        m = _F(self.s1 / _F(n))
        var = _F(_F(self.s2 / _F(n)) - _F(m * m))
        return _F(np.sqrt(var)) if var > 0.0 else _F(0.0)


class BlockFeatures:
    """Accumulates 10 ms samples and emits one scaled feature row per block."""

    def __init__(self) -> None:
        self._n = 0
        self._v, self._dv = _Spread(), _Spread()
        self._a, self._i = _Spread(), _Spread()
        self._tq_sum = _F(0.0)
        self._flips = 0
        self._v_prev = _F(0.0)
        self._tq_prev = _F(0.0)
        self._have_prev = False

    def push(self, *, v_meas_mps: float, a_meas_mps2: float, torque_nm: float,
             i_batt_a: float, v_ref_mps: float, a_ref_mps2: float
             ) -> np.ndarray | None:
        v, a = _F(v_meas_mps), _F(a_meas_mps2)
        tq, i = _F(torque_nm), _F(i_batt_a)
        first = self._n == 0

        # The very first sample has no predecessor; its difference is zero.
        dv = _F(v - self._v_prev) if self._have_prev else _F(0.0)
        if first:
            self._tq_sum = _F(0.0)
            self._flips = 0
        self._v.add(v, first)
        self._dv.add(dv, first)
        self._a.add(a, first)
        self._i.add(i, first)
        self._tq_sum = _F(self._tq_sum + tq)
        # A product below zero is a change of sign; passing through zero, or
        # resting at it, is not.
        if self._have_prev and _F(tq * self._tq_prev) < 0.0:
            self._flips += 1

        self._v_prev, self._tq_prev, self._have_prev = v, tq, True
        self._n += 1
        if self._n < BLOCK_STEPS:
            return None

        n = BLOCK_STEPS
        row = np.array([
            self._v.mean(n), self._dv.std(n),
            self._a.mean(n), self._a.std(n),
            _F(self._tq_sum / _F(n)), _F(self._flips),
            self._i.mean(n), self._i.std(n),
            _F(v_ref_mps), _F(a_ref_mps2),
        ], dtype=np.float32)
        self._n = 0
        return (row / FEATURE_SCALE).astype(np.float32)


class FeatureWindow:
    """The last WINDOW_BLOCKS rows, oldest first, zero-padded until full."""

    def __init__(self) -> None:
        self._rows = np.zeros((WINDOW_BLOCKS, len(FEATURE_NAMES)),
                              dtype=np.float32)
        self._head = 0          # where the next row goes
        self._count = 0

    @property
    def full(self) -> bool:
        return self._count >= WINDOW_BLOCKS

    def push(self, row: np.ndarray) -> None:
        self._rows[self._head] = row
        self._head = (self._head + 1) % WINDOW_BLOCKS
        self._count = min(self._count + 1, WINDOW_BLOCKS)

    def as_array(self) -> np.ndarray:
        out = np.roll(self._rows, -self._head, axis=0).copy()
        if not self.full:
            out[: WINDOW_BLOCKS - self._count] = 0.0
        return out
