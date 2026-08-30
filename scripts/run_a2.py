"""Ablation A2: what does 8-bit arithmetic cost the forecaster?

Spec 6.3 lists A2 as float32 to int8 to distilled student. This measures the
first step of that: the same trained network scored in float and then with
every weight and every activation rounded to the values an 8-bit tensor can
hold.

The spec's deployment path is PyTorch to ONNX to TFLite to esp-tflite-micro,
and that toolchain is not installed here. What this measures is the
arithmetic, not the converter. The distinction is kept in the report: an int8
number produced here says whether 8-bit precision is survivable, and G5 on the
device says what the runtime does with it.

Calibration windows come from **training trips only**. A calibration set drawn
from the data a model is about to be scored on is the same class of leak as a
test-set hyperparameter, and it is one the spec names explicitly.

    PYTHONPATH="src:." python3 scripts/run_a2.py
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
from evpil.forecast.deploy import BUDGET_BYTES, transformer_cost
from evpil.forecast.metrics import per_horizon
from evpil.forecast.models import fit_transformer
from evpil.forecast.quantise import (
    calibrate_activations,
    deployed_bytes,
    predict_int8,
    quantisable_parameters,
)
from evpil.forecast.windows import WindowSpec, build_dataset


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--canonical", default="data/i3_canonical.pkl")
    ap.add_argument("--splits", default="data/splits.json")
    ap.add_argument("--seq-len", type=int, default=32)
    ap.add_argument("--horizon", type=int, default=30)
    ap.add_argument("--stride", type=int, default=5)
    ap.add_argument("--epochs", type=int, default=12)
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--calibration-windows", type=int, default=4096)
    ap.add_argument("--out-json", default="docs/a2-quantisation.json")
    ap.add_argument("--out-csv", default="docs/a2-quantisation.csv")
    args = ap.parse_args()

    df = pickle.loads(Path(args.canonical).read_bytes())
    sp = json.loads(Path(args.splits).read_text())
    spec = WindowSpec(args.seq_len, args.horizon, args.stride)

    X_tr, Y_tr, g_tr, _ = build_dataset(df, sp["train"], spec)
    X_va, Y_va, g_va, _ = build_dataset(df, sp["val"], spec)
    assert_disjoint_groups(train=g_tr.tolist(), val=g_va.tolist(), test=sp["test"])

    base = per_horizon(Y_va, persistence(X_va, spec.horizon)).rmse

    # Evenly spaced across the training windows so the calibration set spans
    # every training trip rather than the first few.
    step = max(1, len(X_tr) // args.calibration_windows)
    X_cal = X_tr[::step][:args.calibration_windows]
    cal_trips = sorted(set(g_tr[::step][:args.calibration_windows].tolist()))

    print(f"train {len(Y_tr)} windows / {len(set(g_tr))} trips")
    print(f"val   {len(Y_va)} windows / {len(set(g_va))} trips, test sealed")
    print(f"calibration {len(X_cal)} windows drawn from {len(cal_trips)} "
          f"training trips, no validation or test data\n")

    rows = []
    for seed in range(args.seeds):
        t = time.time()
        out = fit_transformer(X_tr, Y_tr, X_va, Y_va, epochs=args.epochs,
                              seed=seed)
        trained = out.model

        # Both scored from the same final weights, so the comparison isolates
        # precision. `out.pred` is the best epoch and is reported separately.
        float_pred = trained.predict(X_va)[:, :, 0]
        ranges = calibrate_activations(trained, X_cal)
        int8_pred = predict_int8(trained, X_va, ranges)[:, :, 0]

        m_f = per_horizon(Y_va, float_pred)
        m_q = per_horizon(Y_va, int8_pred)
        rows.append({
            "seed": seed,
            "float_rmse_w": float(m_f.rmse[-1]),
            "int8_rmse_w": float(m_q.rmse[-1]),
            "best_epoch_rmse_w": float(per_horizon(Y_va, out.pred).rmse[-1]),
            "float_curve": m_f.rmse.tolist(),
            "int8_curve": m_q.rmse.tolist(),
            "n_activation_points": len(ranges),
            "n_weight_tensors": len(quantisable_parameters(trained.net)),
            "deployed_bytes": deployed_bytes(trained.net),
            "float32_bytes": int(sum(p.numel() for p in trained.net.parameters()) * 4),
        })
        delta = m_q.rmse[-1] / m_f.rmse[-1] - 1.0
        print(f"  seed {seed}  {time.time() - t:5.1f}s   "
              f"float {m_f.rmse[-1] / 1000:.3f} kW   "
              f"int8 {m_q.rmse[-1] / 1000:.3f} kW   ({delta:+.2%})")

    f_mean = float(np.mean([r["float_rmse_w"] for r in rows]))
    q_mean = float(np.mean([r["int8_rmse_w"] for r in rows]))
    cost = q_mean / f_mean - 1.0

    print(f"\nover {args.seeds} seeds")
    print(f"  float32          {f_mean / 1000:.3f} kW")
    print(f"  int8             {q_mean / 1000:.3f} kW   ({cost:+.2%})")
    print(f"  persistence      {base[-1] / 1000:.3f} kW")
    print(f"  int8 skill over persistence  {1 - q_mean / base[-1]:.1%}  "
          f"(G4 needs 10%)")

    weights = rows[0]["n_weight_tensors"]
    points = rows[0]["n_activation_points"]
    f32 = rows[0]["float32_bytes"]
    i8 = rows[0]["deployed_bytes"]
    print(f"\n  {weights} weight tensors quantised, {points} activation points")
    print(f"  float32 {f32 / 1024:.1f} KB  ->  int8 {i8 / 1024:.1f} KB  "
          f"({f32 / i8:.2f}x smaller, {i8 / BUDGET_BYTES:.1%} of the G5 budget)")

    model = transformer_cost(spec.seq_len, 32, 2, n_features=8, n_outputs=1,
                             horizon=spec.horizon)
    print(f"  cost model predicts {model.int8_bytes} bytes, "
          f"measured {i8} bytes")

    lines = ["step,seconds,float_rmse_w,int8_rmse_w,penalty_fraction"]
    for i in range(spec.horizon):
        f = float(np.mean([r["float_curve"][i] for r in rows]))
        q = float(np.mean([r["int8_curve"][i] for r in rows]))
        lines.append(f"{i + 1},{(i + 1) / 10:.1f},{f:.4f},{q:.4f},{q / f - 1:.6f}")
    Path(args.out_csv).write_text("\n".join(lines) + "\n")

    Path(args.out_json).write_text(json.dumps({
        "spec": {"seq_len": spec.seq_len, "horizon": spec.horizon,
                 "stride": spec.stride, "epochs": args.epochs,
                 "seeds": args.seeds},
        "calibration": {"windows": int(len(X_cal)), "trips": cal_trips,
                        "source": "training split only"},
        "per_seed": rows,
        "float_mean_rmse_w": f_mean,
        "int8_mean_rmse_w": q_mean,
        "quantisation_penalty": cost,
        "persistence_rmse_w": float(base[-1]),
        "int8_skill_vs_persistence": 1 - q_mean / base[-1],
        "float32_bytes": f32,
        "int8_bytes": i8,
        "budget_bytes": BUDGET_BYTES,
        "cost_model_bytes": model.int8_bytes,
    }, indent=2) + "\n")
    print(f"\nwrote {args.out_csv} and {args.out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
