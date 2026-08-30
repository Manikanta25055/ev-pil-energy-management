# scripts/plot_guards.py
"""Figure for the guards and baselines report.

Three panels, because the report makes three separate points and one combined
axis would let the near horizon's easy numbers hide the far horizon's hard ones.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

COLOURS = {
    "persistence": "#1f77b4",
    "drift": "#d62728",
    "ridge": "#2ca02c",
    "gate": "#7f7f7f",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="docs/forecast-baselines.csv")
    ap.add_argument("--out", default="docs/figures/forecast-guards.png")
    args = ap.parse_args()

    df = pd.read_csv(args.csv)
    s = df["seconds"]

    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.2))

    ax = axes[0]
    for arm in ("persistence", "drift", "ridge"):
        ax.plot(s, df[f"{arm}_rmse_w"] / 1000.0, color=COLOURS[arm], lw=1.8, label=arm)
    ax.plot(s, df["g4_threshold_rmse_w"] / 1000.0, color=COLOURS["gate"],
            lw=1.4, ls="--", label="G4 bar (10% under persistence)")
    ax.set_xlabel("horizon, s")
    ax.set_ylabel("RMSE, kW")
    ax.set_title("Error grows with the horizon")
    ax.legend(fontsize=8, loc="upper left")
    ax.grid(alpha=0.3)

    ax = axes[1]
    for arm in ("persistence", "drift", "ridge"):
        ax.plot(s, df[f"{arm}_r2"], color=COLOURS[arm], lw=1.8, label=arm)
    ax.axhline(0.0, color="k", lw=0.8)
    ax.set_xlabel("horizon, s")
    ax.set_ylabel("R^2")
    ax.set_ylim(-0.6, 1.05)
    ax.set_title("Nothing survives 3 s intact")
    ax.legend(fontsize=8, loc="lower left")
    ax.grid(alpha=0.3)

    ax = axes[2]
    ax.plot(s, 100.0 * df["ridge_skill"], color=COLOURS["ridge"], lw=1.8,
            label="ridge, 257 parameters")
    ax.axhline(10.0, color=COLOURS["gate"], lw=1.4, ls="--", label="G4 requires 10%")
    ax.axhline(0.0, color="k", lw=0.8)
    ax.set_xlabel("horizon, s")
    ax.set_ylabel("RMSE reduction over persistence, %")
    ax.set_title("A linear map already clears the gate")
    ax.legend(fontsize=8, loc="upper right")
    ax.grid(alpha=0.3)

    fig.tight_layout()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
