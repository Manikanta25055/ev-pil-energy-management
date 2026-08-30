"""Naive forecasters that any proposed model has to beat to be worth reporting.

Spec 6.4 makes persistence mandatory. Short-horizon power forecasting is a
domain where persistence is genuinely hard to beat, and a paper that omits it
invites the reviewer question it cannot then answer.

These are pure functions of a window tensor: no fitting, no state, nothing that
can leak.
"""

from __future__ import annotations

import numpy as np

from evpil.forecast.windows import last_observed_power


def persistence(X: np.ndarray, horizon: int) -> np.ndarray:
    """Predict that battery power stays at its last observed value.

    The value is recomputed from the window's own current and voltage channels,
    so persistence sees exactly what a model sees and no more.
    """
    if horizon < 1:
        raise ValueError(f"horizon must be at least 1, got {horizon}")
    return np.repeat(last_observed_power(X)[:, None], horizon, axis=1)


def drift(X: np.ndarray, horizon: int, steps: int = 5) -> np.ndarray:
    """Extrapolate the recent trend in battery power linearly.

    The honest companion to persistence: if a model beats persistence only by
    noticing that power was already rising, a straight line says so for free.
    `steps` is the number of input samples the slope is measured over.
    """
    if horizon < 1:
        raise ValueError(f"horizon must be at least 1, got {horizon}")
    if steps < 2:
        raise ValueError(f"steps must be at least 2, got {steps}")
    if steps > X.shape[1]:
        raise ValueError(f"steps {steps} exceeds the {X.shape[1]}-sample window")

    from evpil.forecast.windows import FEATURE_COLUMNS

    i_idx = FEATURE_COLUMNS.index("i_batt_a")
    v_idx = FEATURE_COLUMNS.index("v_batt_v")
    tail = X[:, -steps:, v_idx] * X[:, -steps:, i_idx]

    k = np.arange(steps, dtype=np.float64)
    k = k - k.mean()
    slope = (tail * k).sum(axis=1) / (k ** 2).sum()

    ahead = np.arange(1, horizon + 1, dtype=np.float64)
    return tail[:, -1][:, None] + slope[:, None] * ahead[None, :]
