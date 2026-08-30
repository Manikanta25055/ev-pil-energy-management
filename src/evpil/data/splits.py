"""Trip-level splits with temperature stratification.

Splitting at the row level on temporally correlated data puts neighbouring
samples on both sides of the boundary, so the test score measures memorisation
rather than generalisation. Every split here is at trip granularity.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Split:
    train: list[str]
    val: list[str]
    test: list[str]

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Split):
            return NotImplemented
        return (sorted(self.train) == sorted(other.train)
                and sorted(self.val) == sorted(other.val)
                and sorted(self.test) == sorted(other.test))


def make_trip_splits(
    df: pd.DataFrame,
    *,
    seed: int,
    val_frac: float = 0.2,
    test_frac: float = 0.2,
    stratify_col: str = "t_ambient_c",
) -> Split:
    """Partition trips into train/val/test, stratified by mean ambient temperature.

    The i3 archive spans winter and summer, and HVAC load is the dominant
    confounder on energy consumption, so an unstratified split risks putting
    all the cold trips on one side.
    """
    per_trip = (df.groupby("trip_id")[stratify_col].mean()
                  .sort_values(kind="mergesort"))
    trips = per_trip.index.to_numpy()

    n = len(trips)
    n_val = int(round(n * val_frac))
    n_test = int(round(n * test_frac))
    if n_val + n_test >= n:
        raise ValueError(f"val_frac + test_frac leaves no training trips (n={n})")

    # Walk the temperature-ordered list in strata of 5 and shuffle within each,
    # so every split draws from the full temperature range.
    rng = np.random.default_rng(seed)
    order: list[str] = []
    for start in range(0, n, 5):
        block = list(trips[start : start + 5])
        rng.shuffle(block)
        order.extend(block)

    # Deal round-robin so strata stay balanced across the three splits.
    val: list[str] = []
    test: list[str] = []
    train: list[str] = []
    for i, trip in enumerate(order):
        if len(val) < n_val and i % 5 == 0:
            val.append(trip)
        elif len(test) < n_test and i % 5 == 1:
            test.append(trip)
        else:
            train.append(trip)

    # Round-robin may under-fill; top up from the largest split.
    while len(val) < n_val:
        val.append(train.pop())
    while len(test) < n_test:
        test.append(train.pop())

    return Split(train=sorted(train), val=sorted(val), test=sorted(test))


def assert_no_trip_overlap(split: Split) -> None:
    tr, va, te = set(split.train), set(split.val), set(split.test)
    for a, b, names in ((tr, va, "train/val"), (tr, te, "train/test"),
                        (va, te, "val/test")):
        shared = a & b
        assert not shared, f"trip overlap between {names}: {sorted(shared)}"


def apply_split(
    df: pd.DataFrame, split: Split
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    assert_no_trip_overlap(split)
    return (
        df[df.trip_id.isin(split.train)].reset_index(drop=True),
        df[df.trip_id.isin(split.val)].reset_index(drop=True),
        df[df.trip_id.isin(split.test)].reset_index(drop=True),
    )
