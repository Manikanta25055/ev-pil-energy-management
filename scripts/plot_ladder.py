# scripts/plot_ladder.py
"""Figures for the model ladder.

The panels are chosen to make the ladder's actual result visible rather than
flattering: the arms are plotted against each other and against the linear
solve, not only against the naive baseline that all of them beat.
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
    "persistence": "#1f77b4",
    "drift": "#d62728",
    "ridge": "#2ca02c",
    "xgboost": "#9467bd",
    "lstm": "#ff7f0e",
}
ARMS = ("persistence", "drift", "ridge", "xgboost", "lstm")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="docs/forecast-ladder.csv")
    ap.add_argument("--json", default="docs/forecast-ladder.json")
    ap.add_argument("--cost-csv", default="docs/forecast-deploy-cost.csv")
    ap.add_argument("--out", default="docs/figures/forecast-ladder.png")
    args = ap.parse_args()

    df = pd.read_csv(args.csv)
    meta = json.loads(Path(args.json).read_text())
    s = df["seconds"]

    cost = pd.read_csv(args.cost_csv)

    fig, axes = plt.subplots(1, 4, figsize=(18.0, 4.2))

    ax = axes[0]
    for arm in ARMS:
        ax.plot(s, df[f"{arm}_rmse_w"] / 1000.0, color=COLOURS[arm], lw=1.8, label=arm)
    ax.set_xlabel("horizon, s")
    ax.set_ylabel("RMSE, kW")
    ax.set_ylim(0, 1.05 * df["drift_rmse_w"].max() / 1000.0)
    ax.set_title("The ladder, against the horizon")
    ax.legend(fontsize=8, loc="upper left")
    ax.grid(alpha=0.3)

    # The panel that matters: everything measured against the linear solve.
    ax = axes[1]
    ridge = df["ridge_rmse_w"]
    for arm in ("persistence", "xgboost", "lstm"):
        ax.plot(s, 100.0 * (1.0 - df[f"{arm}_rmse_w"] / ridge),
                color=COLOURS[arm], lw=1.8, label=arm)
    ax.axhline(0.0, color=COLOURS["ridge"], lw=1.6, ls="--", label="ridge")
    ax.set_xlabel("horizon, s")
    ax.set_ylabel("RMSE reduction over ridge, %")
    ax.set_ylim(-25, 15)
    ax.set_title("The recurrent gain is only in the far half")
    ax.legend(fontsize=8, loc="lower left")
    ax.grid(alpha=0.3)

    # Per-trip, final step. Seven trips is few enough to show every one.
    ax = axes[2]
    per_trip = meta["per_trip_final_rmse_w"]
    trips = sorted(per_trip["persistence"])
    x = np.arange(len(trips))
    width = 0.27
    for k, arm in enumerate(("persistence", "ridge", "lstm")):
        vals = [per_trip[arm][t] / 1000.0 for t in trips]
        ax.bar(x + (k - 1) * width, vals, width, color=COLOURS[arm], label=arm)
    ax.set_xticks(x)
    ax.set_xticklabels([t.replace("Trip", "") for t in trips], fontsize=8)
    ax.set_xlabel("validation trip")
    ax.set_ylabel("RMSE at 3.0 s, kW")
    ax.set_title("Trip decides more than model")
    ax.legend(fontsize=8, loc="upper left")
    ax.grid(alpha=0.3, axis="y")

    # The panel the deployment decision is actually made on. Accuracy alone
    # cannot say which arm goes on the device.
    ax = axes[3]
    # Zero-latency rows carry no information on a log axis, and persistence is
    # more useful as the line every arm has to get under.
    fits = cost[(cost["latency_ms"] > 0.0) & (cost["final_rmse_w"].notna())]
    p_rmse = float(cost.loc[cost["arm"] == "persistence", "final_rmse_w"].iloc[0])
    ax.axhline(p_rmse / 1000.0, color=COLOURS["persistence"], lw=1.4, ls=":")
    ax.annotate("persistence, free", (1.0, p_rmse / 1000.0),
                textcoords="offset points", xytext=(0, 4), fontsize=7.5,
                color=COLOURS["persistence"])

    for _, row in fits.iterrows():
        name = row["arm"]
        ax.scatter(row["latency_ms"], row["final_rmse_w"] / 1000.0, s=80,
                   color=COLOURS.get(name.split()[0], "#7f7f7f"),
                   marker="o" if row["fits"] else "X", zorder=3)
        ax.annotate(name, (row["latency_ms"], row["final_rmse_w"] / 1000.0),
                    textcoords="offset points", xytext=(0, -14), fontsize=7.5,
                    ha="center")

    ax.axvline(40.0, color="k", lw=1.2, ls="--")
    ax.set_ylim(10.6, p_rmse / 1000.0 + 0.45)
    ax.annotate("G5 budget, 40 ms", (40.0, p_rmse / 1000.0 + 0.30),
                textcoords="offset points", xytext=(-5, 0), fontsize=7.5,
                ha="right", va="top")
    ax.set_xscale("log")
    ax.set_xlim(0.1, 400.0)
    ax.set_xlabel("estimated latency on one S3 core, ms (log)")
    ax.set_ylabel("RMSE at 3.0 s, kW")
    ax.set_title("Accuracy against the compute budget")
    ax.grid(alpha=0.3)

    fig.tight_layout()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
