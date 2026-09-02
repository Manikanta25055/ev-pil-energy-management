"""Ablation A2, third rung: distil the unconstrained Transformer into one that fits.

Spec 6.3 lists A2 as float32 to int8 to distilled student, and 7.2 says what
the third rung means: train the unconstrained Transformer offline, then distil
into whatever fits the G1 budget. Reporting accuracy at each rung *is* claim
C4 -- the Pareto curve is the result, not a compromise. The first two rungs
were measured in week 6 (`docs/a2-quantisation.json`, and `docs/g5-latency.md`
for what the device did with the int8 model); this is the one that was left.

The question is narrow and worth stating precisely, because "distillation
helps" is easy to claim and easy to get wrong. The deployed model is already
sized to the G1 budget and trained directly on the data. So the question is not
whether a big model beats a small one -- it does, and that is not interesting.
It is whether a budget-sized model taught by a big one beats the *same*
budget-sized model taught by the data alone. Same architecture, same seeds,
same windows, one difference.

**Why no distillation loss was written.** For a squared-error objective,

    a*||s - y||^2 + b*||s - t||^2  =  ||s - (a*y + b*t)||^2 + c(y, t)

with a + b = 1, and the leftover term does not depend on the student's output.
Training on the blended target is therefore *exactly* the blended distillation
loss, not an approximation of it. So the student is trained by the same
`fit_transformer` the other arms use, with its targets replaced. That keeps
every arm on one training path: a second trainer written for this experiment
would be the obvious place for the two arms to stop being comparable.

    PYTHONPATH="src:." python3 scripts/run_distill.py
"""

from __future__ import annotations

import argparse
import json
import pickle
import time
from pathlib import Path

import numpy as np

from evpil.data.guards import assert_disjoint_groups
from evpil.forecast.baselines import persistence
from evpil.forecast.deploy import (
    BUDGET_BYTES, BUDGET_LATENCY_MS, transformer_cost,
)
from evpil.forecast.metrics import per_horizon
from evpil.forecast.models import fit_transformer
from evpil.forecast.quantise import (
    calibrate_activations,
    deployed_bytes,
    predict_int8,
)
from evpil.forecast.windows import WindowSpec, build_dataset

# The teacher is deliberately over budget. Its job is to be the best model the
# data supports, not a candidate for the device -- if it fitted, there would be
# nothing to distil into.
TEACHER = {"d_model": 64, "layers": 4}

# Two students. The first is the configuration G1 sized and week 6 deployed, so
# its direct arm reproduces a number the project already has and acts as a
# check that this script is measuring the same thing. The second is half its
# width, included because a Pareto front needs more than one point on it.
STUDENTS = {
    "student-d32": {"d_model": 32, "layers": 2},
    "student-d16": {"d_model": 16, "layers": 2},
}


# Inference is chunked. The teacher is asked for its opinion of all 55,125
# training windows at once otherwise, and at the teacher's width that allocates
# more than this 8 GB machine's GPU will give -- attention is quadratic in the
# sequence and linear in the batch. Chunking changes no result: the network has
# no state across windows.
CHUNK = 4096


def predict_chunked(trained, X: np.ndarray) -> np.ndarray:
    out = [trained.predict(X[i:i + CHUNK]) for i in range(0, len(X), CHUNK)]
    return np.concatenate(out, axis=0)


def predict_int8_chunked(trained, X: np.ndarray, ranges) -> np.ndarray:
    out = [predict_int8(trained, X[i:i + CHUNK], ranges)
           for i in range(0, len(X), CHUNK)]
    return np.concatenate(out, axis=0)


def cost_of(cfg: dict, spec: WindowSpec, n_features: int, n_outputs: int
            ) -> dict:
    c = transformer_cost(spec.seq_len, cfg["d_model"], cfg["layers"],
                         n_features=n_features, n_outputs=n_outputs,
                         horizon=spec.horizon)
    # Both budgets, because they do not bind together. The teacher fits the
    # 300 KB and misses the 40 ms by four times over, so a single "fits"
    # column would report it as deployable.
    fits_mem = c.int8_bytes <= BUDGET_BYTES
    fits_lat = c.latency_ms is not None and c.latency_ms <= BUDGET_LATENCY_MS
    return {"macs": c.macs, "int8_bytes": c.int8_bytes,
            "latency_ms": c.latency_ms, "n_params": c.n_params,
            "fits_footprint": fits_mem, "fits_latency": fits_lat,
            "deployable": bool(fits_mem and fits_lat)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--canonical", default="data/i3_canonical.pkl")
    ap.add_argument("--splits", default="data/splits.json")
    ap.add_argument("--seq-len", type=int, default=32)
    ap.add_argument("--horizon", type=int, default=30)
    ap.add_argument("--stride", type=int, default=5)
    ap.add_argument("--epochs", type=int, default=12)
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--alpha", type=float, default=0.5,
                    help="weight on the ground truth; 0 is pure distillation")
    ap.add_argument("--calibration-windows", type=int, default=4096)
    ap.add_argument("--out-json", default="docs/a2-distillation.json")
    ap.add_argument("--out-csv", default="docs/a2-distillation.csv")
    args = ap.parse_args()

    df = pickle.loads(Path(args.canonical).read_bytes())
    sp = json.loads(Path(args.splits).read_text())
    spec = WindowSpec(args.seq_len, args.horizon, args.stride)

    X_tr, Y_tr, g_tr, _ = build_dataset(df, sp["train"], spec)
    X_va, Y_va, g_va, _ = build_dataset(df, sp["val"], spec)
    assert_disjoint_groups(train=g_tr.tolist(), val=g_va.tolist(),
                           test=sp["test"])

    base = per_horizon(Y_va, persistence(X_va, spec.horizon)).rmse[-1]

    step = max(1, len(X_tr) // args.calibration_windows)
    X_cal = X_tr[::step][:args.calibration_windows]
    cal_trips = sorted(set(g_tr[::step][:args.calibration_windows].tolist()))

    n_features = X_tr.shape[-1]
    n_outputs = Y_tr.shape[-1] if Y_tr.ndim == 3 else 1

    print(f"train {len(Y_tr)} windows / {len(set(g_tr))} trips")
    print(f"val   {len(Y_va)} windows / {len(set(g_va))} trips, test sealed")
    print(f"calibration {len(X_cal)} windows from {len(cal_trips)} training "
          f"trips\n")
    print(f"persistence baseline {base / 1000:.3f} kW")
    print(f"distillation target = {args.alpha:.2f} * truth + "
          f"{1 - args.alpha:.2f} * teacher\n")

    rows: list[dict] = []

    def score(name: str, seed: int, out, cfg: dict, secs: float) -> dict:
        trained = out.model
        f_pred = predict_chunked(trained, X_va)
        f_pred = f_pred[:, :, 0] if f_pred.ndim == 3 else f_pred
        ranges = calibrate_activations(trained, X_cal)
        q_pred = predict_int8_chunked(trained, X_va, ranges)
        q_pred = q_pred[:, :, 0] if q_pred.ndim == 3 else q_pred
        m_f = per_horizon(Y_va, f_pred)
        m_q = per_horizon(Y_va, q_pred)
        row = {
            "arm": name, "seed": seed,
            "d_model": cfg["d_model"], "layers": cfg["layers"],
            "float_rmse_w": float(m_f.rmse[-1]),
            "int8_rmse_w": float(m_q.rmse[-1]),
            "deployed_bytes": deployed_bytes(trained.net),
            "float32_bytes": int(sum(p.numel()
                                     for p in trained.net.parameters()) * 4),
            "torch_params": out.n_params,
            "train_s": secs,
        }
        rows.append(row)
        print(f"  {name:18} seed {seed}  {secs:6.1f}s  "
              f"float {m_f.rmse[-1] / 1000:6.3f} kW   "
              f"int8 {m_q.rmse[-1] / 1000:6.3f} kW   "
              f"{row['deployed_bytes'] / 1024:6.1f} KB")
        return row

    for seed in range(args.seeds):
        print(f"seed {seed}")
        # 1. Teacher, over budget on purpose.
        t = time.time()
        teach = fit_transformer(X_tr, Y_tr, X_va, Y_va, epochs=args.epochs,
                                seed=seed, **TEACHER)
        score("teacher", seed, teach, TEACHER, time.time() - t)

        # The teacher's opinion of the training windows. This is the only
        # place the teacher touches the students: it never sees validation.
        Y_teacher = predict_chunked(teach.model, X_tr)
        if Y_teacher.ndim == 3 and Y_tr.ndim == 2:
            Y_teacher = Y_teacher[:, :, 0]
        Y_blend = args.alpha * Y_tr + (1.0 - args.alpha) * Y_teacher

        for name, cfg in STUDENTS.items():
            t = time.time()
            direct = fit_transformer(X_tr, Y_tr, X_va, Y_va,
                                     epochs=args.epochs, seed=seed, **cfg)
            score(f"{name}-direct", seed, direct, cfg, time.time() - t)

            t = time.time()
            distil = fit_transformer(X_tr, Y_blend, X_va, Y_va,
                                     epochs=args.epochs, seed=seed, **cfg)
            score(f"{name}-distilled", seed, distil, cfg, time.time() - t)
        print()

    # ---- aggregate -------------------------------------------------------
    arms = sorted({r["arm"] for r in rows},
                  key=lambda a: (a != "teacher", a))
    summary = {}
    for arm in arms:
        rs = [r for r in rows if r["arm"] == arm]
        cfg = {"d_model": rs[0]["d_model"], "layers": rs[0]["layers"]}
        summary[arm] = {
            "d_model": cfg["d_model"], "layers": cfg["layers"],
            "n_seeds": len(rs),
            "float_mean_rmse_w": float(np.mean([r["float_rmse_w"]
                                                for r in rs])),
            "float_sd_rmse_w": float(np.std([r["float_rmse_w"] for r in rs],
                                            ddof=1)) if len(rs) > 1 else 0.0,
            "int8_mean_rmse_w": float(np.mean([r["int8_rmse_w"] for r in rs])),
            "int8_sd_rmse_w": float(np.std([r["int8_rmse_w"] for r in rs],
                                           ddof=1)) if len(rs) > 1 else 0.0,
            "deployed_bytes": rs[0]["deployed_bytes"],
            "float32_bytes": rs[0]["float32_bytes"],
            "cost_model": cost_of(cfg, spec, n_features, n_outputs),
        }

    print(f"Pareto front, int8, over {args.seeds} seeds. Budgets: "
          f"{BUDGET_BYTES / 1024:.0f} KB and {BUDGET_LATENCY_MS:.0f} ms.\n")
    print(f"  {'arm':22} {'int8 kW':>9} {'sd':>7} {'KB':>7} {'est ms':>8}  "
          f"deployable")
    for arm in arms:
        a = summary[arm]
        cm = a["cost_model"]
        lat = cm["latency_ms"]
        why = ("yes" if cm["deployable"]
               else "no, latency" if cm["fits_footprint"]
               else "no, memory" if cm["fits_latency"]
               else "no, both")
        print(f"  {arm:22} {a['int8_mean_rmse_w'] / 1000:9.3f} "
              f"{a['int8_sd_rmse_w'] / 1000:7.3f} "
              f"{a['deployed_bytes'] / 1024:7.1f} "
              f"{(lat if lat is not None else float('nan')):8.2f}  {why}")

    # ---- the actual question ---------------------------------------------
    print("\nDoes the teacher help? Paired by seed, int8, negative is better.")
    verdicts = {}
    for name in STUDENTS:
        d = [next(r for r in rows
                  if r["arm"] == f"{name}-distilled" and r["seed"] == s)
             ["int8_rmse_w"]
             - next(r for r in rows
                    if r["arm"] == f"{name}-direct" and r["seed"] == s)
             ["int8_rmse_w"]
             for s in range(args.seeds)]
        mean = float(np.mean(d))
        direct_mean = summary[f"{name}-direct"]["int8_mean_rmse_w"]
        same_sign = all(x < 0 for x in d) or all(x > 0 for x in d)
        verdicts[name] = {
            "per_seed_delta_w": [float(x) for x in d],
            "mean_delta_w": mean,
            "relative": mean / direct_mean,
            "consistent_sign": bool(same_sign),
            "helps": bool(mean < 0 and same_sign),
        }
        print(f"  {name:14} {mean:+9.1f} W ({mean / direct_mean:+.2%})  "
              f"per seed {['%+.0f' % x for x in d]}  "
              f"{'consistent' if same_sign else 'SIGN FLIPS ACROSS SEEDS'}")

    Path(args.out_json).write_text(json.dumps({
        "spec": {"seq_len": args.seq_len, "horizon": args.horizon,
                 "stride": args.stride, "epochs": args.epochs,
                 "seeds": args.seeds, "alpha": args.alpha},
        "teacher_config": TEACHER, "student_configs": STUDENTS,
        "persistence_rmse_w": float(base),
        "budget_bytes": BUDGET_BYTES,
        "summary": summary, "verdicts": verdicts, "runs": rows,
    }, indent=2) + "\n")

    import csv
    with open(args.out_csv, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"\nwrote {args.out_json} and {args.out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
