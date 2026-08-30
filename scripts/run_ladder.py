"""The Week 4 model ladder: persistence, drift, ridge, XGBoost, LSTM.

Spec 4.2's arms, scored on validation with the metrics of spec 6.2 and judged
against gate G4. Test trips are not opened.

The LSTM is run over several seeds because the question it has to answer -- is
a recurrent model better than a linear solve on this data -- is decided by a
gap of a few percent, and a single training run cannot distinguish that from
initialisation noise.

    PYTHONPATH="src:." python3 scripts/run_ladder.py
"""

from __future__ import annotations

import argparse
import json
import pickle
import time
from pathlib import Path

import numpy as np

from evpil.data.guards import assert_disjoint_groups
from evpil.forecast.baselines import drift, persistence
from evpil.forecast.metrics import bootstrap_ci, per_horizon, per_trip_rmse
from evpil.forecast.models import fit_lstm, fit_ridge, fit_xgboost
from evpil.forecast.windows import WindowSpec, build_dataset


def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(((np.asarray(y_pred) - np.asarray(y_true)) ** 2).mean()))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--canonical", default="data/i3_canonical.pkl")
    ap.add_argument("--splits", default="data/splits.json")
    ap.add_argument("--seq-len", type=int, default=32)
    ap.add_argument("--horizon", type=int, default=30)
    ap.add_argument("--stride", type=int, default=5)
    ap.add_argument("--lstm-seeds", type=int, default=5)
    ap.add_argument("--lstm-epochs", type=int, default=12)
    ap.add_argument("--seed", type=int, default=20260830)
    ap.add_argument("--out-csv", default="docs/forecast-ladder.csv")
    ap.add_argument("--out-json", default="docs/forecast-ladder.json")
    args = ap.parse_args()

    df = pickle.loads(Path(args.canonical).read_bytes())
    sp = json.loads(Path(args.splits).read_text())
    spec = WindowSpec(args.seq_len, args.horizon, args.stride)

    X_tr, Y_tr, g_tr, _ = build_dataset(df, sp["train"], spec)
    X_va, Y_va, g_va, _ = build_dataset(df, sp["val"], spec)
    assert_disjoint_groups(train=g_tr.tolist(), val=g_va.tolist(), test=sp["test"])

    print(f"train {len(Y_tr)} windows / {len(set(g_tr))} trips, "
          f"val {len(Y_va)} / {len(set(g_va))} trips, test sealed")
    print(f"window {spec.seq_len} in / {spec.horizon} out, stride {spec.stride}\n")

    preds: dict[str, np.ndarray] = {}
    params: dict[str, int] = {}
    notes: dict[str, object] = {}

    print("fitting arms")
    t = time.time()
    preds["persistence"] = persistence(X_va, spec.horizon)
    params["persistence"] = 0
    preds["drift"] = drift(X_va, spec.horizon, steps=5)
    params["drift"] = 0
    print(f"  baselines            {time.time() - t:6.1f}s")

    t = time.time()
    r = fit_ridge(X_tr, Y_tr, X_va)
    preds["ridge"], params["ridge"] = r.pred, r.n_params
    print(f"  ridge                {time.time() - t:6.1f}s  {r.n_params} weights")

    t = time.time()
    x = fit_xgboost(X_tr, Y_tr, X_va, Y_va, seed=0)
    preds["xgboost"], params["xgboost"] = x.pred, x.n_params
    notes["xgboost_best_rounds"] = x.info["best_rounds"]
    print(f"  xgboost              {time.time() - t:6.1f}s  {x.n_params} trees "
          f"over {spec.horizon} boosters")

    # LSTM: one run per seed, kept separately so the spread is visible rather
    # than averaged away before anyone sees it.
    lstm_preds, lstm_final = [], []
    for s in range(args.lstm_seeds):
        t = time.time()
        out = fit_lstm(X_tr, Y_tr, X_va, Y_va, epochs=args.lstm_epochs, seed=s)
        lstm_preds.append(out.pred)
        final = per_horizon(Y_va, out.pred).rmse[-1]
        lstm_final.append(float(final))
        params["lstm"] = out.n_params
        print(f"  lstm seed {s}          {time.time() - t:6.1f}s  "
              f"epoch {out.info['best_epoch']:2d}  "
              f"{spec.horizon / 10:.1f} s RMSE {final / 1000:.3f} kW")

    # The reported LSTM is the seed-mean prediction. Averaging predictions
    # rather than metrics is what a deployed ensemble would do, so the numbers
    # below are reachable; per-seed spread is reported alongside.
    preds["lstm"] = np.mean(lstm_preds, axis=0)
    notes["lstm_final_rmse_per_seed"] = lstm_final
    notes["lstm_seeds"] = args.lstm_seeds
    notes["lstm_epochs"] = args.lstm_epochs

    metrics = {name: per_horizon(Y_va, p) for name, p in preds.items()}
    base = metrics["persistence"].rmse
    ridge_rmse = metrics["ridge"].rmse

    print(f"\nvalidation, {spec.horizon / 10:.1f} s horizon (final step)")
    print(f"{'arm':<14}{'RMSE kW':>10}{'R^2':>9}{'vs persist':>12}"
          f"{'vs ridge':>11}{'params':>10}")
    for name in ("persistence", "drift", "ridge", "xgboost", "lstm"):
        m = metrics[name]
        sk_p = 1.0 - m.rmse[-1] / base[-1]
        sk_r = 1.0 - m.rmse[-1] / ridge_rmse[-1]
        print(f"{name:<14}{m.rmse[-1] / 1000:>10.3f}{m.r2[-1]:>9.4f}"
              f"{sk_p:>11.1%}{sk_r:>11.1%}{params[name]:>10}")

    spread = max(lstm_final) - min(lstm_final)
    print(f"\nlstm across {args.lstm_seeds} seeds: "
          f"{min(lstm_final) / 1000:.3f} to {max(lstm_final) / 1000:.3f} kW, "
          f"spread {spread / 1000:.3f} kW")
    print(f"lstm mean-of-seeds gain over ridge: "
          f"{(ridge_rmse[-1] - metrics['lstm'].rmse[-1]) / 1000:.3f} kW")

    print("\ngate G4: beat persistence by 10% RMSE at the final step")
    for name in ("ridge", "xgboost", "lstm"):
        sk = 1.0 - metrics[name].rmse[-1] / base[-1]
        print(f"  {name:<10} {sk:>6.1%}  {'PASS' if sk >= 0.10 else 'FAIL'}")

    print("\nbootstrap over trips, final step, 95%")
    ci = {}
    for name in ("persistence", "ridge", "xgboost", "lstm"):
        lo, hi = bootstrap_ci(Y_va[:, -1:], preds[name][:, -1:], g_va, rmse,
                              n_boot=1000, seed=args.seed)
        ci[name] = (lo, hi)
        print(f"  {name:<12}[{lo / 1000:6.3f}, {hi / 1000:6.3f}] kW")

    print("\nper trip, final step, RMSE kW")
    trips = sorted(set(g_va.tolist()))
    per_trip = {n: per_trip_rmse(Y_va, preds[n], g_va, step=spec.horizon)
                for n in ("persistence", "ridge", "lstm")}
    print(f"  {'trip':<10}{'persist':>9}{'ridge':>9}{'lstm':>9}")
    for trip in trips:
        print(f"  {trip:<10}{per_trip['persistence'][trip] / 1000:>9.3f}"
              f"{per_trip['ridge'][trip] / 1000:>9.3f}"
              f"{per_trip['lstm'][trip] / 1000:>9.3f}")
    wins = sum(per_trip["lstm"][t] < per_trip["ridge"][t] for t in trips)
    print(f"  lstm beats ridge on {wins} of {len(trips)} trips")

    arms = ("persistence", "drift", "ridge", "xgboost", "lstm")
    head = ["step", "seconds"]
    for a in arms:
        head += [f"{a}_rmse_w", f"{a}_mae_w", f"{a}_r2"]
    head += ["lstm_skill_vs_persistence", "lstm_skill_vs_ridge"]
    lines = [",".join(head)]
    for i in range(spec.horizon):
        row = [f"{i + 1}", f"{(i + 1) / 10:.1f}"]
        for a in arms:
            m = metrics[a]
            row += [f"{m.rmse[i]:.4f}", f"{m.mae[i]:.4f}", f"{m.r2[i]:.6f}"]
        row += [f"{1.0 - metrics['lstm'].rmse[i] / base[i]:.6f}",
                f"{1.0 - metrics['lstm'].rmse[i] / ridge_rmse[i]:.6f}"]
        lines.append(",".join(row))
    Path(args.out_csv).write_text("\n".join(lines) + "\n")

    Path(args.out_json).write_text(json.dumps({
        "spec": {"seq_len": spec.seq_len, "horizon": spec.horizon,
                 "stride": spec.stride},
        "n_windows": {"train": int(len(Y_tr)), "val": int(len(Y_va))},
        "params": params,
        "final_step_rmse_w": {a: float(metrics[a].rmse[-1]) for a in arms},
        "final_step_r2": {a: float(metrics[a].r2[-1]) for a in arms},
        "skill_vs_persistence": {a: float(1.0 - metrics[a].rmse[-1] / base[-1])
                                 for a in arms},
        "bootstrap_ci_final_w": {k: list(v) for k, v in ci.items()},
        "per_trip_final_rmse_w": per_trip,
        "notes": notes,
    }, indent=2) + "\n")

    print(f"\nwrote {args.out_csv} and {args.out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
