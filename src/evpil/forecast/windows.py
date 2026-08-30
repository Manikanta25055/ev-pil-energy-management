"""Turn canonical trip frames into supervised forecasting tensors.

Spec 4.2: `seq_len` past steps of `[v, a, SoC, I, V, T_ambient, grade, P_aux]`
predicting `horizon` future steps of battery power.

Two things this module exists to make structurally impossible rather than
merely discouraged. A window never spans two trips, and a window's inputs never
overlap its own targets. The predecessor work's headline numbers came from
row-level shuffling, which is the first of those failures, and it is not the
kind of error a metric reveals -- it makes the metric look better.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd

# Order matters: it is the channel order of every tensor this module returns,
# and the order the on-device input buffer will be packed in.
FEATURE_COLUMNS: tuple[str, ...] = (
    "v_mps", "a_mps2", "soc_frac", "i_batt_a", "v_batt_v",
    "t_ambient_c", "grade_rad", "p_aux_w",
)

TARGET_COLUMN = "p_batt_w"

_I_IDX = FEATURE_COLUMNS.index("i_batt_a")
_V_IDX = FEATURE_COLUMNS.index("v_batt_v")


class WindowError(ValueError):
    """Raised when a window cannot be built as specified."""


@dataclass(frozen=True)
class WindowSpec:
    """Window geometry, in samples rather than seconds.

    Samples, not seconds, because the i3 logs at 10 Hz and VED at 1 Hz, and a
    module that silently reinterprets `horizon` between the two would be a
    quiet source of incomparable numbers.
    """

    seq_len: int = 32
    horizon: int = 30
    stride: int = 1

    def __post_init__(self) -> None:
        for name in ("seq_len", "horizon", "stride"):
            if getattr(self, name) < 1:
                raise WindowError(f"{name} must be at least 1, got {getattr(self, name)}")

    @property
    def span(self) -> int:
        """Samples consumed by one window, inputs plus targets."""
        return self.seq_len + self.horizon


def add_battery_power(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy carrying `p_batt_w`, positive when discharging.

    Sign follows the canonical current convention: positive current is
    discharge, so positive power is energy leaving the pack.
    """
    out = df.copy()
    out[TARGET_COLUMN] = out["v_batt_v"].to_numpy() * out["i_batt_a"].to_numpy()
    return out


def contiguous_runs(t_s: np.ndarray, tol: float = 0.5) -> list[tuple[int, int]]:
    """Split a time axis into runs of uniform sampling.

    A logging gap inside a window would silently stretch the forecast horizon
    past the seconds it claims to cover, so runs are cut wherever the interval
    departs from the run's own median by more than `tol` of that median.
    Returns half-open [start, stop) index pairs.
    """
    n = len(t_s)
    if n < 2:
        return [(0, n)] if n else []

    dt = np.diff(t_s)
    nominal = float(np.median(dt))
    if nominal <= 0.0:
        raise WindowError("time axis is not increasing")

    breaks = np.flatnonzero(np.abs(dt - nominal) > tol * nominal) + 1
    edges = [0, *breaks.tolist(), n]
    return [(a, b) for a, b in zip(edges[:-1], edges[1:]) if b > a]


def _windows_from_run(
    features: np.ndarray, target: np.ndarray, spec: WindowSpec
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    n = len(target)
    if n < spec.span:
        empty_x = np.empty((0, spec.seq_len, features.shape[1]), dtype=np.float32)
        empty_y = np.empty((0, spec.horizon), dtype=np.float32)
        return empty_x, empty_y, np.empty(0, dtype=np.int64)

    starts = np.arange(0, n - spec.span + 1, spec.stride, dtype=np.int64)
    in_idx = starts[:, None] + np.arange(spec.seq_len)[None, :]
    # The first target step is `seq_len`, not `seq_len - 1`: the window ends
    # where the horizon begins, and the two never share a sample.
    out_idx = starts[:, None] + spec.seq_len + np.arange(spec.horizon)[None, :]

    return (
        features[in_idx].astype(np.float32, copy=False),
        target[out_idx].astype(np.float32, copy=False),
        starts + spec.seq_len,
    )


def build_dataset(
    df: pd.DataFrame,
    trip_ids: Iterable[str],
    spec: WindowSpec = WindowSpec(),
    feature_columns: Sequence[str] = FEATURE_COLUMNS,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Window the named trips into `(X, Y, groups, t0)`.

    `X` is `(n, seq_len, len(feature_columns))`, `Y` is `(n, horizon)` of
    battery power in watts, `groups` names the trip each window came from, and
    `t0` is the trip-relative time of each window's first predicted step.

    `groups` is the load-bearing return value. Every split, every bootstrap and
    every leakage check downstream is grouped by it, so a window can only ever
    appear on one side of a boundary.
    """
    wanted = list(dict.fromkeys(trip_ids))
    if not wanted:
        raise WindowError("no trips requested")

    available = set(df["trip_id"].unique())
    missing = [t for t in wanted if t not in available]
    if missing:
        raise WindowError(f"trips not present in the frame: {missing}")

    if TARGET_COLUMN not in df.columns:
        df = add_battery_power(df)

    xs, ys, gs, ts = [], [], [], []
    for trip in wanted:
        sub = df[df["trip_id"] == trip]
        t_s = sub["t_s"].to_numpy()
        features = sub[list(feature_columns)].to_numpy()
        target = sub[TARGET_COLUMN].to_numpy()

        for a, b in contiguous_runs(t_s):
            x, y, first = _windows_from_run(features[a:b], target[a:b], spec)
            if len(y) == 0:
                continue
            xs.append(x)
            ys.append(y)
            gs.append(np.full(len(y), trip, dtype=object))
            ts.append(t_s[a:b][first])

    if not ys:
        raise WindowError(
            f"no trip yielded a window of {spec.span} contiguous samples "
            f"(seq_len {spec.seq_len} + horizon {spec.horizon})"
        )

    return (
        np.concatenate(xs),
        np.concatenate(ys),
        np.concatenate(gs),
        np.concatenate(ts).astype(np.float64),
    )


def last_observed_power(X: np.ndarray) -> np.ndarray:
    """Battery power at the final input step of each window.

    Derived from the current and voltage channels rather than carried as a
    ninth feature, so that the target quantity never appears in `X` under its
    own name and cannot be selected as an input by accident.
    """
    return X[:, -1, _V_IDX] * X[:, -1, _I_IDX]
