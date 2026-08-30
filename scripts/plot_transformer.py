# scripts/plot_transformer.py
"""Figures for the Transformer arms and ablation A1.

The third panel is the one A1 turns on: whether the residual loss bought
physical consistency, and at what cost in accuracy. Plotting accuracy alone
would answer only half of the ablation.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

COLOURS = {
    "plain-1ch": "#1f77b4",
    "plain-4ch": "#2ca02c",
    "pi-4ch": "#d62728",
    "lstm": "#ff7f0e",
    "persistence": "#7f7f7f",
}
RESIDUAL_LABEL = {
    "r1": "r1  P - V*I\n(W)",
    "r2": "r2  charge\n(1/s)",
    "r3": "r3  terminal V\n(V)",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="docs/transformer-a1.json")
    ap.add_argument("--csv", default="docs/transformer-a1.csv")
    ap.add_argument("--ladder-csv", default="docs/forecast-ladder.csv")
    ap.add_argument("--out", default="docs/figures/transformer-a1.png")
    args = ap.parse_args()

    meta = json.loads(Path(args.json).read_text())
    df = pd.read_csv(args.csv)
    ladder = pd.read_csv(args.ladder_csv)
    s = df["seconds"]

    fig, axes = plt.subplots(1, 4, figsize=(18.0, 4.2))

    ax = axes[0]
    ax.plot(ladder["seconds"], ladder["persistence_rmse_w"] / 1000.0,
            color=COLOURS["persistence"], lw=1.4, ls=":", label="persistence")
    ax.plot(ladder["seconds"], ladder["lstm_rmse_w"] / 1000.0,
            color=COLOURS["lstm"], lw=1.6, ls="--", label="lstm (ladder)")
    for arm in ("plain-1ch", "plain-4ch", "pi-4ch"):
        ax.plot(s, df[f"{arm}_rmse_w"] / 1000.0, color=COLOURS[arm], lw=1.8,
                label=arm)
    ax.set_xlabel("horizon, s")
    ax.set_ylabel("RMSE, kW")
    ax.set_title("Transformer against the ladder")
    ax.legend(fontsize=8, loc="upper left")
    ax.grid(alpha=0.3)

    # A1: every seed, so the reader sees the spread the claim rests on.
    ax = axes[1]
    for k, arm in enumerate(("plain-4ch", "pi-4ch")):
        seeds = np.array(meta["arms"][arm]["per_seed_rmse_w"]) / 1000.0
        ax.scatter(np.full(len(seeds), k) + np.linspace(-0.06, 0.06, len(seeds)),
                   seeds, s=55, color=COLOURS[arm], zorder=3)
        ax.hlines(seeds.mean(), k - 0.22, k + 0.22, color=COLOURS[arm], lw=2.0)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["plain", "physics-informed"])
    ax.set_ylabel("RMSE at 3.0 s, kW")
    ax.set_title(f"A1, matched at {meta['arms']['pi-4ch']['n_params']:,} parameters")
    ax.grid(alpha=0.3, axis="y")

    # What the residual loss actually bought, normalised so three quantities
    # in three different units share one axis.
    ax = axes[2]
    keys = ["r1", "r2", "r3"]
    x = np.arange(len(keys))
    plain = [meta["arms"]["plain-4ch"]["mean_abs_residual"][k] for k in keys]
    pi = [meta["arms"]["pi-4ch"]["mean_abs_residual"][k] for k in keys]
    ratio = [p / b if b > 0 else np.nan for p, b in zip(pi, plain)]
    ax.bar(x - 0.19, np.ones(len(keys)), 0.38, color=COLOURS["plain-4ch"],
           label="plain")
    ax.bar(x + 0.19, ratio, 0.38, color=COLOURS["pi-4ch"], label="informed")
    for k, (xi, r) in enumerate(zip(x, ratio)):
        ax.annotate(f"{r:.2f}x", (xi + 0.19, r), textcoords="offset points",
                    xytext=(0, 3), ha="center", fontsize=8)
    ax.set_xticks(x)
    ax.set_xticklabels([RESIDUAL_LABEL[k] for k in keys], fontsize=8)
    ax.set_ylabel("mean |residual|, relative to plain")
    ax.set_ylim(0, 1.35)
    ax.set_title("What the residual loss bought")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3, axis="y")

    # The trade the weight controls.
    ax = axes[3]
    lam = sorted(float(k) for k in meta["lambda_sweep"])
    rms = [meta["lambda_sweep"][str(k) if str(k) in meta["lambda_sweep"]
                                else repr(k)]["rmse_w"] / 1000.0 for k in lam]
    viol = [np.mean([meta["lambda_sweep"][str(k) if str(k) in meta["lambda_sweep"]
                                          else repr(k)]["violation"][r]
                     for r in keys]) for k in lam]
    ax.plot(lam, rms, "o-", color=COLOURS["pi-4ch"], lw=1.8, label="RMSE at 3.0 s")
    ax.set_xscale("log")
    ax.set_xlabel("residual weight (lambda)")
    ax.set_ylabel("RMSE at 3.0 s, kW", color=COLOURS["pi-4ch"])
    ax.axvline(meta["lambda_chosen"], color="k", lw=1.1, ls="--")
    twin = ax.twinx()
    twin.plot(lam, viol, "s--", color="#9467bd", lw=1.6, label="violation rate")
    twin.set_ylabel("mean violation rate", color="#9467bd")
    ax.set_title("The weight trades accuracy for consistency")
    ax.grid(alpha=0.3)

    fig.tight_layout()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
