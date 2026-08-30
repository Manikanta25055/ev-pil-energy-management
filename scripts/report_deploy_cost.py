"""Cost every ladder arm against the G5 budget, and pair it with its accuracy.

Deliberately a separate step from `run_ladder.py`. Training produces a
measurement; this produces arithmetic over shapes, and the two have different
error bars. Keeping them apart means a change to the cost model never silently
edits a reported accuracy, and re-costing an arm never means retraining it.

    PYTHONPATH="src:." python3 scripts/report_deploy_cost.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evpil.forecast.deploy import (
    BUDGET_BYTES,
    BUDGET_LATENCY_MS,
    MEASURED_MMAC_PER_S,
    DeployCost,
    constant_cost,
    lstm_cost,
    ridge_cost,
    transformer_cost,
    tree_ensemble_cost,
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ladder-json", default="docs/forecast-ladder.json")
    ap.add_argument("--n-features", type=int, default=8)
    ap.add_argument("--lstm-hidden", type=int, default=64)
    ap.add_argument("--lstm-layers", type=int, default=1)
    ap.add_argument("--xgb-max-depth", type=int, default=4)
    ap.add_argument("--out-csv", default="docs/forecast-deploy-cost.csv")
    args = ap.parse_args()

    meta = json.loads(Path(args.ladder_json).read_text())
    seq_len = meta["spec"]["seq_len"]
    horizon = meta["spec"]["horizon"]
    rmse = dict(meta["final_step_rmse_w"])
    skill = dict(meta["skill_vs_persistence"])

    # meta's "lstm" entry is the seed-mean prediction. Move it to the ensemble
    # row it actually belongs to, and give the single-model row the mean of
    # the per-seed scores, which is what one deployed model achieves.
    per_seed = meta["notes"].get("lstm_final_rmse_per_seed") or []
    n_seeds_meta = int(meta["notes"].get("lstm_seeds", 1))
    if n_seeds_meta > 1 and per_seed:
        base = meta["final_step_rmse_w"]["persistence"]
        rmse[f"lstm x{n_seeds_meta} (as reported)"] = rmse["lstm"]
        skill[f"lstm x{n_seeds_meta} (as reported)"] = skill["lstm"]
        rmse["lstm"] = sum(per_seed) / len(per_seed)
        skill["lstm"] = 1.0 - rmse["lstm"] / base

    costs: dict[str, DeployCost] = {
        "persistence": constant_cost(),
        "drift": constant_cost(),
        "ridge": ridge_cost(seq_len, args.n_features, horizon),
        "xgboost": tree_ensemble_cost(meta["params"]["xgboost"], args.xgb_max_depth),
        "lstm": lstm_cost(seq_len, args.n_features, args.lstm_hidden,
                          args.lstm_layers, horizon),
    }
    # The reported LSTM number is a mean over seeds, which is an ensemble and
    # costs like one. Separating the two rows is the difference between a
    # number that can be published and a number that can be flashed.
    n_seeds = int(meta["notes"].get("lstm_seeds", 1))
    if n_seeds > 1:
        one = costs["lstm"]
        costs[f"lstm x{n_seeds} (as reported)"] = DeployCost(
            macs=one.macs * n_seeds,
            int8_bytes=one.int8_bytes * n_seeds,
            latency_ms=one.latency_ms * n_seeds,
            footprint_estimated=False,
        )

    # Not trained yet. Carried so the Week 5 decision is made against a number
    # rather than an intention.
    costs["transformer (G1 trimmed)"] = transformer_cost(seq_len, 32, 2)

    print(f"G1 measured throughput  {MEASURED_MMAC_PER_S:.2f} MMAC/s, int8, one core")
    print(f"G5 budget               {BUDGET_LATENCY_MS:.0f} ms, "
          f"{BUDGET_BYTES / 1024:.0f} KB model plus arena\n")

    print(f"{'arm':<26}{'RMSE kW':>9}{'skill':>8}{'MACs':>10}"
          f"{'ms':>8}{'% lat':>8}{'KB':>9}{'% mem':>8}  fits")
    for name, c in costs.items():
        r = rmse.get(name)
        s = skill.get(name)
        r_txt = f"{r / 1000:>9.3f}" if r is not None else f"{'-':>9}"
        s_txt = f"{s:>8.1%}" if s is not None else f"{'-':>8}"
        mac_txt = f"{c.macs:>10,}" if c.macs is not None else f"{'n/a':>10}"
        ms_txt = f"{c.latency_ms:>8.2f}" if c.latency_ms is not None else f"{'n/a':>8}"
        lf = c.latency_fraction
        lf_txt = f"{lf:>8.1%}" if lf is not None else f"{'n/a':>8}"
        star = "*" if c.footprint_estimated else " "
        print(f"{name:<26}{r_txt}{s_txt}{mac_txt}{ms_txt}{lf_txt}"
              f"{c.int8_bytes / 1024:>8.1f}{star}{c.memory_fraction:>8.1%}"
              f"  {'yes' if c.fits else 'NO'}")
    print("\n* footprint estimated from node counts, not arithmetic over shapes")

    over = [n for n, c in costs.items() if not c.fits]
    if over:
        print(f"\nexceeds the G5 budget: {', '.join(over)}")

    lines = ["arm,final_rmse_w,skill_vs_persistence,macs,latency_ms,"
             "latency_fraction,int8_bytes,memory_fraction,footprint_estimated,fits"]
    for name, c in costs.items():
        r = rmse.get(name)
        s = skill.get(name)
        lines.append(
            f"{name},{'' if r is None else f'{r:.4f}'},"
            f"{'' if s is None else f'{s:.6f}'},"
            f"{'' if c.macs is None else c.macs},"
            f"{'' if c.latency_ms is None else f'{c.latency_ms:.4f}'},"
            f"{'' if c.latency_fraction is None else f'{c.latency_fraction:.6f}'},"
            f"{c.int8_bytes},{c.memory_fraction:.6f},"
            f"{int(c.footprint_estimated)},{int(c.fits)}"
        )
    Path(args.out_csv).write_text("\n".join(lines) + "\n")
    print(f"\nwrote {args.out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
