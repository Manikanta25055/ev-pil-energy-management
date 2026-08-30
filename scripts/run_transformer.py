"""Week 5: the Transformer at the G1 configuration, plain and physics-informed.

Three arms and one ablation.

  1. `plain-1ch`   power only, the like-for-like comparison against the LSTM
  2. `plain-4ch`   power, current, voltage and charge; the A1 control
  3. `pi-4ch`      the same network and the same parameter count, plus the
                   residual loss; the A1 treatment

Arms 2 and 3 differ only in the loss, which is what makes A1 a test of
physics-informing rather than of capacity. Arm 1 exists because arms 2 and 3
receive supervision on three channels the LSTM never saw, and comparing a
four-channel model against a one-channel one would confound the architecture
with the extra targets.

Residual weights are swept on validation, per spec 4.2, before the seeds run.

    PYTHONPATH="src:." python3 scripts/run_transformer.py
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
from evpil.forecast.metrics import bootstrap_ci, per_horizon, per_trip_rmse
from evpil.forecast.models import fit_transformer
from evpil.forecast.physics import (
    PhysicsConstants,
    ResidualWeights,
    residual_terms,
    violation_rate,
)
from evpil.forecast.windows import (
    TARGET_COLUMNS,
    WindowSpec,
    build_multitarget_dataset,
)

# Stated here rather than defaulted in the library, because these numbers
# decide what counts as "violating physics" and belong in the report.
#   r1  500 W of electrical inconsistency, against a 10.8 kW mean |P|
#   r2  the charge a 5 A current error would misplace over the 3 s horizon.
#       r2 is the horizon-integral form, not spec 4.2's pointwise derivative;
#       see evpil.forecast.physics for the measurement that forced the change
#   r3  2 V on a 360 V nominal pack
TOLERANCES = {"r1": 500.0, "r2": 5.0 * 3.0 / (3600.0 * 61.7), "r3": 2.0}


def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(((np.asarray(y_pred) - np.asarray(y_true)) ** 2).mean()))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--canonical", default="data/i3_canonical.pkl")
    ap.add_argument("--splits", default="data/splits.json")
    ap.add_argument("--params", default="data/i3_params.json")
    ap.add_argument("--seq-len", type=int, default=32)
    ap.add_argument("--horizon", type=int, default=30)
    ap.add_argument("--stride", type=int, default=5)
    ap.add_argument("--epochs", type=int, default=12)
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--lambda-grid", type=float, nargs="+",
                    default=[0.1, 1.0, 10.0])
    ap.add_argument("--seed", type=int, default=20260830)
    ap.add_argument("--out-json", default="docs/transformer-a1.json")
    ap.add_argument("--out-csv", default="docs/transformer-a1.csv")
    args = ap.parse_args()

    df = pickle.loads(Path(args.canonical).read_bytes())
    sp = json.loads(Path(args.splits).read_text())
    params = json.loads(Path(args.params).read_text())
    spec = WindowSpec(args.seq_len, args.horizon, args.stride)
    const = PhysicsConstants.from_params(params, dt_s=0.1)

    X_tr, Y_tr, g_tr, _ = build_multitarget_dataset(df, sp["train"], spec)
    X_va, Y_va, g_va, _ = build_multitarget_dataset(df, sp["val"], spec)
    assert_disjoint_groups(train=g_tr.tolist(), val=g_va.tolist(), test=sp["test"])

    print(f"train {len(Y_tr)} windows / {len(set(g_tr))} trips, "
          f"val {len(Y_va)} / {len(set(g_va))} trips, test sealed")
    print(f"targets {TARGET_COLUMNS}")
    print(f"physics: Q {const.capacity_ah} Ah (measured), r0 {const.r0_ohm:.4f} ohm "
          f"(identified), OCV table assumed\n")

    P_va = persistence(X_va, spec.horizon)
    base = per_horizon(Y_va[:, :, 0], P_va).rmse

    # --- sweep the residual weight on validation ---------------------------
    print("sweeping the residual weight, one seed")
    print("  lambda_2 is held at 0: the logged charge channel does not move "
          "within a 3.0 s")
    print("  horizon on this archive, so r2 has nothing to constrain. "
          "Measured cost of")
    print("  switching it on is reported as its own arm below.\n")
    sweep = {}
    for lam in args.lambda_grid:
        t = time.time()
        out = fit_transformer(
            X_tr, Y_tr, X_va, Y_va, epochs=args.epochs, seed=0,
            physics=const, weights=ResidualWeights(lam, 0.0, lam),
        )
        r = per_horizon(Y_va[:, :, 0], out.pred[:, :, 0]).rmse[-1]
        v = violation_rate(out.pred, const, TOLERANCES)
        sweep[lam] = {"rmse_w": float(r), "violation": v}
        print(f"  lambda {lam:>6.2f}  {time.time() - t:6.1f}s  "
              f"RMSE {r / 1000:.3f} kW  "
              f"violations r1 {v['r1']:.3f} r2 {v['r2']:.3f} r3 {v['r3']:.3f}")

    best_lambda = min(sweep, key=lambda k: sweep[k]["rmse_w"])
    print(f"  chosen: lambda {best_lambda} on validation RMSE\n")

    # --- the three arms, several seeds each --------------------------------
    # `pi-4ch-r2` is the sub-ablation that measures what enabling charge
    # conservation costs, rather than leaving the decision to an argument.
    arms = {
        "plain-1ch": dict(single=True, physics=None, use_r2=False),
        "plain-4ch": dict(single=False, physics=None, use_r2=False),
        "pi-4ch": dict(single=False, physics=const, use_r2=False),
        "pi-4ch-r2": dict(single=False, physics=const, use_r2=True),
    }
    results: dict[str, dict] = {}

    for name, cfg in arms.items():
        preds, finals, n_params = [], [], 0
        for s in range(args.seeds):
            t = time.time()
            Yt = Y_tr[:, :, 0] if cfg["single"] else Y_tr
            Yv = Y_va[:, :, 0] if cfg["single"] else Y_va
            kw = {}
            if cfg["physics"] is not None:
                lam2 = best_lambda if cfg["use_r2"] else 0.0
                kw = {"physics": const,
                      "weights": ResidualWeights(best_lambda, lam2, best_lambda)}
            out = fit_transformer(X_tr, Yt, X_va, Yv, epochs=args.epochs,
                                  seed=s, **kw)
            p = out.pred if cfg["single"] else out.pred[:, :, 0]
            preds.append(out.pred)
            f = per_horizon(Y_va[:, :, 0], p).rmse[-1]
            finals.append(float(f))
            n_params = out.n_params
            print(f"  {name:<11} seed {s}  {time.time() - t:6.1f}s  "
                  f"epoch {out.info['best_epoch']:2d}  RMSE {f / 1000:.3f} kW")

        mean_pred = np.mean(preds, axis=0)
        power = mean_pred if cfg["single"] else mean_pred[:, :, 0]
        m = per_horizon(Y_va[:, :, 0], power)
        entry = {
            "final_rmse_w": float(m.rmse[-1]),
            "final_r2": float(m.r2[-1]),
            "per_seed_rmse_w": finals,
            "single_seed_mean_rmse_w": float(np.mean(finals)),
            "n_params": n_params,
            "rmse_w": m.rmse.tolist(),
            "mae_w": m.mae.tolist(),
            "r2": m.r2.tolist(),
        }
        if not cfg["single"]:
            entry["violation"] = violation_rate(mean_pred, const, TOLERANCES)
            entry["mean_abs_residual"] = {
                k: float(np.abs(v).mean())
                for k, v in residual_terms(mean_pred, const).items()
            }
        results[name] = entry
        results[name]["_power_pred"] = power

    # --- report ------------------------------------------------------------
    print(f"\nvalidation, {spec.horizon / 10:.1f} s horizon")
    print(f"{'arm':<12}{'RMSE kW':>10}{'R^2':>9}{'vs persist':>12}"
          f"{'per-seed spread':>18}{'params':>9}")
    for name, e in results.items():
        sk = 1.0 - e["final_rmse_w"] / base[-1]
        spread = max(e["per_seed_rmse_w"]) - min(e["per_seed_rmse_w"])
        print(f"{name:<12}{e['final_rmse_w'] / 1000:>10.3f}{e['final_r2']:>9.4f}"
              f"{sk:>11.1%}{spread / 1000:>17.3f} kW{e['n_params']:>9}")

    print("\nablation A1: physics-informed against plain, matched parameters")
    plain, pi = results["plain-4ch"], results["pi-4ch"]
    delta = 1.0 - pi["single_seed_mean_rmse_w"] / plain["single_seed_mean_rmse_w"]
    print(f"  one model, mean over {args.seeds} seeds: "
          f"plain {plain['single_seed_mean_rmse_w'] / 1000:.3f} kW, "
          f"informed {pi['single_seed_mean_rmse_w'] / 1000:.3f} kW  "
          f"({delta:+.1%})")
    print(f"  per-seed plain    {[round(v / 1000, 3) for v in plain['per_seed_rmse_w']]}")
    print(f"  per-seed informed {[round(v / 1000, 3) for v in pi['per_seed_rmse_w']]}")

    with_r2 = results["pi-4ch-r2"]
    cost = 1.0 - with_r2["single_seed_mean_rmse_w"] / pi["single_seed_mean_rmse_w"]
    print(f"\n  sub-ablation, charge conservation switched on: "
          f"{with_r2['single_seed_mean_rmse_w'] / 1000:.3f} kW ({cost:+.1%} "
          f"against r2 off)")
    print(f"  per-seed with r2  "
          f"{[round(v / 1000, 3) for v in with_r2['per_seed_rmse_w']]}")

    print("\nphysics-violation rate, fraction of predicted steps outside tolerance")
    print(f"  tolerances: r1 {TOLERANCES['r1']:.0f} W, "
          f"r2 {TOLERANCES['r2']:.2e} /s, r3 {TOLERANCES['r3']:.0f} V")
    print(f"  {'arm':<12}{'r1':>9}{'r2':>9}{'r3':>9}   mean |residual|")
    for name in ("plain-4ch", "pi-4ch", "pi-4ch-r2"):
        v = results[name]["violation"]
        a = results[name]["mean_abs_residual"]
        print(f"  {name:<12}{v['r1']:>9.3f}{v['r2']:>9.3f}{v['r3']:>9.3f}   "
              f"r1 {a['r1']:>8.1f} W  r2 {a['r2']:.2e} /s  r3 {a['r3']:>5.2f} V")

    print("\ngate G4, beat persistence by 10% at the final step")
    for name, e in results.items():
        sk = 1.0 - e["final_rmse_w"] / base[-1]
        print(f"  {name:<12}{sk:>7.1%}  {'PASS' if sk >= 0.10 else 'FAIL'}")

    print("\nbootstrap over trips, final step, 95%")
    for name, e in results.items():
        lo, hi = bootstrap_ci(Y_va[:, -1:, 0], e["_power_pred"][:, -1:], g_va,
                              rmse, n_boot=1000, seed=args.seed)
        e["bootstrap_ci_final_w"] = [lo, hi]
        print(f"  {name:<12}[{lo / 1000:6.3f}, {hi / 1000:6.3f}] kW")

    per_trip = {n: per_trip_rmse(Y_va[:, :, 0], e["_power_pred"], g_va,
                                 step=spec.horizon)
                for n, e in results.items()}

    lines = ["step,seconds," + ",".join(
        f"{a}_rmse_w,{a}_mae_w,{a}_r2" for a in results)]
    for i in range(spec.horizon):
        row = [f"{i + 1}", f"{(i + 1) / 10:.1f}"]
        for e in results.values():
            row += [f"{e['rmse_w'][i]:.4f}", f"{e['mae_w'][i]:.4f}",
                    f"{e['r2'][i]:.6f}"]
        lines.append(",".join(row))
    Path(args.out_csv).write_text("\n".join(lines) + "\n")

    for e in results.values():
        e.pop("_power_pred")
    Path(args.out_json).write_text(json.dumps({
        "spec": {"seq_len": spec.seq_len, "horizon": spec.horizon,
                 "stride": spec.stride, "epochs": args.epochs,
                 "seeds": args.seeds},
        "physics": {"capacity_ah": const.capacity_ah, "r0_ohm": const.r0_ohm,
                    "dt_s": const.dt_s},
        "tolerances": TOLERANCES,
        "lambda_sweep": {str(k): v for k, v in sweep.items()},
        "lambda_chosen": best_lambda,
        "persistence_final_rmse_w": float(base[-1]),
        "arms": results,
        "per_trip_final_rmse_w": per_trip,
    }, indent=2) + "\n")
    print(f"\nwrote {args.out_csv} and {args.out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
