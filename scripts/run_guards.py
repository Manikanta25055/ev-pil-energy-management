"""Run spec 6.4's three guards on the i3 windows, before any model is trained.

Order matters. The leakage audit and the shuffled-label control decide whether
any number produced later means anything; the persistence baseline decides what
a later number has to beat. Running them after training would be running them
after they could have changed a decision.

    PYTHONPATH="src:." python3 scripts/run_guards.py
"""

from __future__ import annotations

import argparse
import json
import pickle
from pathlib import Path

import numpy as np

from evpil.data.guards import LeakageError, assert_disjoint_groups, audit_features
from evpil.forecast.baselines import drift, persistence
from evpil.forecast.metrics import bootstrap_ci, per_horizon, per_trip_rmse
from evpil.forecast.windows import (
    FEATURE_COLUMNS,
    TARGET_COLUMN,
    WindowSpec,
    build_dataset,
)

# Written down per target, deliberately, because no automatic check can know
# that terminal voltage times battery current IS the target rather than merely
# correlating with it. Both channels are legitimate as past-window inputs; what
# is forbidden is either of them at or beyond the first predicted step, and
# that is enforced by the window geometry, not by this list.
FORBIDDEN: dict[str, tuple[str, ...]] = {
    TARGET_COLUMN: ("p_batt_w", "p_batt_kw", "energy_wh", "energy_kwh"),
}


def ridge_fit_predict(
    X_tr: np.ndarray, y_tr: np.ndarray, X_te: np.ndarray, lam: float = 1.0
) -> np.ndarray:
    """Least squares with a small ridge, on flattened windows.

    Deliberately the weakest reasonable learner. The shuffled-label control
    asks whether the *pipeline* leaks, and a leak is a property of the wiring
    rather than of model capacity, so a linear map is enough to find one and
    fast enough to run every time.
    """
    A = X_tr.reshape(len(X_tr), -1).astype(np.float64)
    B = X_te.reshape(len(X_te), -1).astype(np.float64)

    mu, sd = A.mean(axis=0), A.std(axis=0)
    sd = np.where(sd > 0.0, sd, 1.0)
    A = (A - mu) / sd
    B = (B - mu) / sd

    A = np.hstack([A, np.ones((len(A), 1))])
    B = np.hstack([B, np.ones((len(B), 1))])

    y = np.asarray(y_tr, dtype=np.float64)
    flat = y.ndim == 1
    if flat:
        y = y[:, None]

    G = A.T @ A + lam * np.eye(A.shape[1])
    W = np.linalg.solve(G, A.T @ y)          # one factorisation, all horizons
    pred = B @ W
    return pred[:, 0] if flat else pred


def r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    y_true = np.asarray(y_true, dtype=np.float64).ravel()
    y_pred = np.asarray(y_pred, dtype=np.float64).ravel()
    ss_res = float(((y_true - y_pred) ** 2).sum())
    ss_tot = float(((y_true - y_true.mean()) ** 2).sum())
    return 1.0 - ss_res / ss_tot if ss_tot > 0.0 else 0.0


def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(((np.asarray(y_pred) - np.asarray(y_true)) ** 2).mean()))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--canonical", default="data/i3_canonical.pkl")
    ap.add_argument("--splits", default="data/splits.json")
    ap.add_argument("--seq-len", type=int, default=32)
    ap.add_argument("--horizon", type=int, default=30)
    ap.add_argument("--stride", type=int, default=5)
    ap.add_argument("--seed", type=int, default=20260830)
    ap.add_argument("--out-csv", default="docs/forecast-baselines.csv")
    args = ap.parse_args()

    df = pickle.loads(Path(args.canonical).read_bytes())
    sp = json.loads(Path(args.splits).read_text())
    spec = WindowSpec(args.seq_len, args.horizon, args.stride)

    print(f"window: {spec.seq_len} in / {spec.horizon} out, stride {spec.stride}")
    print(f"        {spec.seq_len / 10:.1f} s of history, {spec.horizon / 10:.1f} s "
          f"of horizon at the i3's 10 Hz\n")

    X_tr, Y_tr, g_tr, _ = build_dataset(df, sp["train"], spec)
    X_va, Y_va, g_va, _ = build_dataset(df, sp["val"], spec)
    print(f"train {len(Y_tr):>7} windows over {len(set(g_tr)):2d} trips")
    print(f"val   {len(Y_va):>7} windows over {len(set(g_va)):2d} trips")
    print(f"test  sealed\n")

    # ---- Guard 1: leakage audit -------------------------------------------
    print("GUARD 1  leakage audit")
    audit_features(FEATURE_COLUMNS, TARGET_COLUMN, FORBIDDEN)
    print(f"  target {TARGET_COLUMN!r} absent from the {len(FEATURE_COLUMNS)} "
          f"feature channels")

    assert_disjoint_groups(train=g_tr.tolist(), val=g_va.tolist(), test=sp["test"])
    print("  no trip appears in two splits, checked on the tensors' own labels")

    # The structural claim, restated as an assertion on real tensors: a window
    # holds seq_len + horizon distinct samples, so its inputs cannot contain
    # any sample its targets cover.
    assert X_tr.shape[1] == spec.seq_len and Y_tr.shape[1] == spec.horizon
    print(f"  inputs end at step {spec.seq_len}, targets begin at step "
          f"{spec.seq_len + 1}, no overlap\n")

    # ---- Guard 2: shuffled-label control ----------------------------------
    print("GUARD 2  shuffled-label control")
    # Scored at the final horizon step, the step G4 is written against.
    y_tr_last, y_va_last = Y_tr[:, -1], Y_va[:, -1]

    real = r2(y_va_last, ridge_fit_predict(X_tr, y_tr_last, X_va))
    rng = np.random.default_rng(args.seed)
    shuffled_tr = rng.permutation(y_tr_last)
    shuffled_va = rng.permutation(y_va_last)
    fake = r2(shuffled_va, ridge_fit_predict(X_tr, shuffled_tr, X_va))

    print(f"  ridge on real labels      R^2 = {real:+.4f}")
    print(f"  ridge on shuffled labels  R^2 = {fake:+.4f}")
    if fake > 0.05:
        raise LeakageError(
            f"shuffled-label R^2 is {fake:+.4f}. The pipeline can see its "
            f"evaluation targets through some path. Fix it before recording "
            f"any result."
        )
    if real < 0.05:
        raise SystemExit(
            f"real-label R^2 is only {real:+.4f}, so the shuffled control is "
            f"vacuous: it proves nothing that a broken feature path would not "
            f"also produce."
        )
    print("  collapses to chance on shuffled labels, learns on real ones\n")

    # ---- Guard 3: persistence baseline ------------------------------------
    print("GUARD 3  persistence baseline on validation")
    P_va = persistence(X_va, spec.horizon)
    D_va = drift(X_va, spec.horizon, steps=5)

    mp = per_horizon(Y_va, P_va)
    md = per_horizon(Y_va, D_va)

    print("   step      s   persistence RMSE      drift RMSE   persistence R^2")
    for step in (1, 5, 10, 20, spec.horizon):
        i = step - 1
        print(f"  {step:>5} {step / 10:>6.1f}   {mp.rmse[i] / 1000:>14.3f} kW "
              f"{md.rmse[i] / 1000:>10.3f} kW   {mp.r2[i]:>15.4f}")

    lo, hi = bootstrap_ci(
        Y_va[:, -1:], P_va[:, -1:], g_va, rmse, n_boot=1000, seed=args.seed
    )
    print(f"\n  persistence RMSE at {spec.horizon / 10:.1f} s: "
          f"{mp.rmse[-1] / 1000:.3f} kW, 95% CI over trips "
          f"[{lo / 1000:.3f}, {hi / 1000:.3f}] kW")

    per_trip = per_trip_rmse(Y_va, P_va, g_va, step=spec.horizon)
    worst = max(per_trip, key=per_trip.get)
    best = min(per_trip, key=per_trip.get)
    print(f"  per trip: best {best} {per_trip[best] / 1000:.3f} kW, "
          f"worst {worst} {per_trip[worst] / 1000:.3f} kW")

    target = mp.rmse[-1] * 0.90
    print(f"\n  G4 threshold: a model must reach {target / 1000:.3f} kW RMSE at "
          f"{spec.horizon / 10:.1f} s on validation")
    print(f"                (10% below persistence, spec 8.2)")

    # ---- Where a linear map already lands ---------------------------------
    # Not a proposed model. The gate is stated as a percentage below
    # persistence, and a percentage means nothing until something has been
    # measured against it. If a ridge on flattened windows already clears G4,
    # then clearing G4 is not evidence for a Transformer, and the paper needs
    # to know that before the Transformer is built rather than after.
    print("\nCALIBRATION  ridge on flattened windows, all horizon steps")
    R_va = ridge_fit_predict(X_tr, Y_tr, X_va)
    mr = per_horizon(Y_va, R_va)
    skill = 1.0 - mr.rmse / mp.rmse

    print("   step      s        ridge RMSE   skill vs persistence     ridge R^2")
    for step in (1, 5, 10, 20, spec.horizon):
        i = step - 1
        print(f"  {step:>5} {step / 10:>6.1f}   {mr.rmse[i] / 1000:>11.3f} kW "
              f"{skill[i]:>21.1%} {mr.r2[i]:>13.4f}")

    verdict = "CLEARS" if skill[-1] >= 0.10 else "misses"
    print(f"\n  a linear map {verdict} the G4 bar at {spec.horizon / 10:.1f} s "
          f"({skill[-1]:.1%} against the required 10.0%)")

    out = Path(args.out_csv)
    lines = ["step,seconds,persistence_rmse_w,persistence_mae_w,persistence_r2,"
             "drift_rmse_w,drift_mae_w,drift_r2,"
             "ridge_rmse_w,ridge_mae_w,ridge_r2,ridge_skill,g4_threshold_rmse_w"]
    for i in range(spec.horizon):
        lines.append(
            f"{i + 1},{(i + 1) / 10:.1f},{mp.rmse[i]:.4f},{mp.mae[i]:.4f},"
            f"{mp.r2[i]:.6f},{md.rmse[i]:.4f},{md.mae[i]:.4f},{md.r2[i]:.6f},"
            f"{mr.rmse[i]:.4f},{mr.mae[i]:.4f},{mr.r2[i]:.6f},{skill[i]:.6f},"
            f"{mp.rmse[i] * 0.90:.4f}"
        )
    out.write_text("\n".join(lines) + "\n")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
