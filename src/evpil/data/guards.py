"""Leakage guards, run before any model is trained.

Implements spec section 6.4. These exist because the predecessor work reported
metrics produced by row-level splitting and by feeding a target-derived column
back in as an input feature.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence

import numpy as np


class LeakageError(AssertionError):
    """Raised when a feature set can see its own target."""


def audit_features(
    feature_cols: Sequence[str],
    target_col: str,
    forbidden: Mapping[str, Iterable[str]],
) -> None:
    """Fail if any feature is the target, or is declared derived from it.

    `forbidden` maps a target name to columns that must never be used to
    predict it. The mapping is written down deliberately, per target, because
    it encodes domain knowledge no automatic check can infer.
    """
    if target_col in feature_cols:
        raise LeakageError(f"target {target_col!r} is present in its own feature set")

    banned = set(forbidden.get(target_col, ()))
    hits = sorted(banned.intersection(feature_cols))
    if hits:
        raise LeakageError(
            f"features {hits} are derived from target {target_col!r} "
            f"and must not be used to predict it"
        )


def shuffled_label_control(
    fit_fn: Callable[[np.ndarray, np.ndarray, np.ndarray], np.ndarray],
    X: np.ndarray,
    y: np.ndarray,
    seed: int,
    holdout_frac: float = 0.25,
) -> float:
    """Train on shuffled targets and return R^2 on a held-out shuffled set.

    An honest pipeline scores near zero. A materially positive score means the
    model can see the evaluation targets through some path, and the pipeline is
    broken regardless of how good the real numbers look.
    """
    rng = np.random.default_rng(seed)
    y_shuffled = np.array(y, copy=True)
    rng.shuffle(y_shuffled)

    n_hold = max(1, int(len(X) * holdout_frac))
    X_tr, y_tr = X[:-n_hold], y_shuffled[:-n_hold]
    X_te, y_te = X[-n_hold:], y_shuffled[-n_hold:]

    pred = np.asarray(fit_fn(X_tr, y_tr, X_te)).ravel()

    ss_res = float(np.sum((y_te - pred) ** 2))
    ss_tot = float(np.sum((y_te - y_te.mean()) ** 2))
    return 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
