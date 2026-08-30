"""Per-horizon-step metrics, and confidence intervals that respect trips.

Spec 6.2 asks for MAE, RMSE and R^2 **per horizon step, not pooled**, with
per-trip distributions alongside aggregates and bootstrap confidence intervals.
Pooling across the horizon hides the only thing worth knowing about a
forecaster: 0.1 s ahead is nearly free and 3.0 s ahead is the actual problem,
and one averaged number lets the first pay for the second.

Confidence intervals resample trips, never windows. Consecutive windows overlap
by `seq_len - stride` samples and come from the same driver on the same road,
so treating them as independent draws would shrink every interval by a factor
that has nothing to do with the evidence.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


class MetricError(ValueError):
    """Raised when predictions and targets cannot be compared as given."""


@dataclass(frozen=True)
class HorizonMetrics:
    """One value per horizon step, in the order the steps are predicted."""

    mae: np.ndarray
    rmse: np.ndarray
    r2: np.ndarray

    @property
    def horizon(self) -> int:
        return len(self.mae)

    def at(self, step: int) -> dict[str, float]:
        """Metrics at one step, indexed from 1 as the reporting tables are."""
        if not 1 <= step <= self.horizon:
            raise MetricError(f"step {step} outside 1..{self.horizon}")
        i = step - 1
        return {"mae": float(self.mae[i]), "rmse": float(self.rmse[i]),
                "r2": float(self.r2[i])}


def _check(y_true: np.ndarray, y_pred: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    y_true = np.asarray(y_true, dtype=np.float64)
    y_pred = np.asarray(y_pred, dtype=np.float64)
    if y_true.shape != y_pred.shape:
        raise MetricError(f"shape mismatch: {y_true.shape} against {y_pred.shape}")
    if y_true.ndim != 2:
        raise MetricError(f"expected (n_windows, horizon), got {y_true.ndim} dimensions")
    if len(y_true) == 0:
        raise MetricError("no windows to score")
    return y_true, y_pred


def per_horizon(y_true: np.ndarray, y_pred: np.ndarray) -> HorizonMetrics:
    """MAE, RMSE and R^2 at each step of the horizon."""
    y_true, y_pred = _check(y_true, y_pred)
    err = y_pred - y_true

    mae = np.abs(err).mean(axis=0)
    rmse = np.sqrt((err ** 2).mean(axis=0))

    ss_res = (err ** 2).sum(axis=0)
    ss_tot = ((y_true - y_true.mean(axis=0)) ** 2).sum(axis=0)
    # A step whose targets are constant has no variance to explain. Reporting
    # R^2 = 0 there is honest; reporting 1.0 would flatter a model that has
    # done nothing.
    r2 = np.where(ss_tot > 0.0, 1.0 - ss_res / np.where(ss_tot > 0.0, ss_tot, 1.0), 0.0)

    return HorizonMetrics(mae=mae, rmse=rmse, r2=r2)


def per_trip_rmse(
    y_true: np.ndarray, y_pred: np.ndarray, groups: np.ndarray, step: int | None = None
) -> dict[str, float]:
    """RMSE for each trip separately, pooled over the horizon or at one step.

    Spec 6.2 requires the distribution alongside the aggregate. A pooled mean
    over 33 trips can be carried by the easy ones, and the G2 work already
    showed how much per-trip spread this data has.
    """
    y_true, y_pred = _check(y_true, y_pred)
    groups = np.asarray(groups)
    if len(groups) != len(y_true):
        raise MetricError(f"groups has {len(groups)} entries for {len(y_true)} windows")

    if step is not None:
        if not 1 <= step <= y_true.shape[1]:
            raise MetricError(f"step {step} outside 1..{y_true.shape[1]}")
        y_true = y_true[:, step - 1 : step]
        y_pred = y_pred[:, step - 1 : step]

    out = {}
    for trip in sorted(set(groups.tolist())):
        m = groups == trip
        out[str(trip)] = float(np.sqrt(((y_pred[m] - y_true[m]) ** 2).mean()))
    return out


def skill_against(
    y_true: np.ndarray, y_pred: np.ndarray, y_baseline: np.ndarray
) -> np.ndarray:
    """Fractional RMSE reduction against a baseline, per horizon step.

    Positive is better than the baseline. G4 asks for at least 0.10 at the
    final step, so this returns the quantity the gate is written in rather than
    two tables a reader has to divide.
    """
    model = per_horizon(y_true, y_pred).rmse
    base = per_horizon(y_true, y_baseline).rmse
    if np.any(base <= 0.0):
        raise MetricError("baseline RMSE is zero at some step; skill is undefined")
    return 1.0 - model / base


def bootstrap_ci(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    groups: np.ndarray,
    statistic,
    n_boot: int = 1000,
    alpha: float = 0.05,
    seed: int = 20260830,
) -> tuple[float, float]:
    """Percentile interval from resampling trips with replacement.

    `statistic(y_true, y_pred) -> float`. Trips are the resampling unit; see
    the module docstring for why windows are not.
    """
    y_true, y_pred = _check(y_true, y_pred)
    groups = np.asarray(groups)
    if len(groups) != len(y_true):
        raise MetricError(f"groups has {len(groups)} entries for {len(y_true)} windows")

    trips = sorted(set(groups.tolist()))
    if len(trips) < 2:
        raise MetricError(
            f"a grouped bootstrap over {len(trips)} trip cannot express uncertainty "
            f"between trips"
        )
    index = {t: np.flatnonzero(groups == t) for t in trips}

    rng = np.random.default_rng(seed)
    draws = np.empty(n_boot, dtype=np.float64)
    for b in range(n_boot):
        picked = rng.choice(len(trips), size=len(trips), replace=True)
        rows = np.concatenate([index[trips[i]] for i in picked])
        draws[b] = float(statistic(y_true[rows], y_pred[rows]))

    lo, hi = np.percentile(draws, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return float(lo), float(hi)
