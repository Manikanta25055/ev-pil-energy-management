# scripts/plot_control.py
"""Figures for the week 7 controller baselines.

Two panels, chosen so the week's actual result is the thing the eye lands on:
the rule-based manager sits almost on top of the optimum, and the distance
between "no regeneration" and "any regeneration" is the whole energy story.
Plotting only the proposed arm against the weakest baseline would hide that.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ARM_ORDER = ["no-regen", "always-regen", "rule-ems", "dp-comfort-priced",
             "dp-comfort-free"]
ARM_COLOUR = {
    "no-regen": "#b0b0b0", "always-regen": "#7aa6c2", "rule-ems": "#2f6f9f",
    "dp-comfort-priced": "#1a1a1a", "dp-comfort-free": "#c26a2f",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="docs/week7-control-baselines.csv")
    ap.add_argument("--robustness", default="docs/week7-pid-robustness.csv")
    ap.add_argument("--out", default="docs/figures/week7-control.png")
    args = ap.parse_args()

    df = pd.read_csv(args.csv)
    rb = pd.read_csv(args.robustness)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.5, 4.4))

    cycles = list(dict.fromkeys(df.cycle))
    arms = [a for a in ARM_ORDER if a in set(df.arm)]
    width = 0.8 / len(arms)
    x = np.arange(len(cycles))

    for i, arm in enumerate(arms):
        sub = df[df.arm == arm].set_index("cycle").reindex(cycles)
        ax1.bar(x + i * width - 0.4 + width / 2, sub.wh_per_km, width,
                label=arm, color=ARM_COLOUR.get(arm, "#888"))

    ax1.set_xticks(x, [c.upper() for c in cycles])
    ax1.set_ylabel("Wh/km")
    ax1.set_title("Consumption by arm")
    ax1.legend(fontsize=8, frameon=False)
    ax1.grid(axis="y", alpha=0.25)

    # The gap to the optimum, on a log axis, because the interesting numbers
    # span two orders of magnitude and a linear axis renders four of the five
    # arms as a flat line at zero.
    gaps = df[df.arm.isin(["no-regen", "always-regen", "rule-ems"])]
    for arm in ["no-regen", "always-regen", "rule-ems"]:
        sub = gaps[gaps.arm == arm].set_index("cycle").reindex(cycles)
        ax2.plot(x, np.maximum(sub.gap_to_dp_pct, 1e-3), "o-", label=arm,
                 color=ARM_COLOUR[arm])
    ax2.set_yscale("log")
    ax2.set_xticks(x, [c.upper() for c in cycles])
    ax2.set_ylabel("gap to DP optimum (%)")
    ax2.set_ylim(bottom=8e-4)
    ax2.set_title("How much was left on the table")
    # always-regen is exactly the optimum on every cycle, so its true value is
    # zero and a log axis cannot show it. It is drawn on the floor and said so
    # here rather than left to look like a small positive number.
    ax2.text(0.5, 0.02, "always-regen is exactly optimal: gap 0.000%, "
             "drawn on the floor of the log axis",
             transform=ax2.transAxes, ha="center", fontsize=7.5,
             color="#555")
    ax2.axhline(1.0, color="#c26a2f", lw=0.9, ls="--")
    ax2.text(0.02, 1.05, "1%", color="#c26a2f", fontsize=8,
             transform=ax2.get_yaxis_transform())
    ax2.legend(fontsize=8, frameon=False)
    ax2.grid(alpha=0.25, which="both")

    fig.tight_layout()
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, dpi=160)
    print(f"wrote {args.out}")

    # Second figure: what the inner loop is worth. The clean-run tracking
    # error is a property of an exact feedforward, so it is plotted alongside
    # the perturbed cases rather than on its own.
    fig2, ax = plt.subplots(figsize=(7.6, 4.0))
    for cyc, marker in zip(sorted(rb.cycle.unique()), ("o", "s")):
        sub = rb[(rb.cycle == cyc) & (rb.grade == "flat")]
        ax.barh(np.arange(len(sub)) + (0.2 if marker == "s" else -0.2),
                sub.tracking_rmse_mps, 0.38, label=cyc.upper())
        labels = list(sub.case)
    ax.set_yticks(np.arange(len(labels)), labels)
    ax.set_xscale("log")
    ax.set_xlabel("speed-tracking RMSE (m/s), log scale")
    ax.set_title("Inner loop under model error and disturbance")
    ax.legend(fontsize=8, frameon=False)
    ax.grid(axis="x", alpha=0.25, which="both")
    fig2.tight_layout()
    out2 = Path(args.out).with_name("week7-pid-robustness.png")
    fig2.savefig(out2, dpi=160)
    print(f"wrote {out2}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
