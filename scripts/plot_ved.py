# scripts/plot_ved.py
"""Figures for the VED generalisation report."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

COLOURS = {"A transfer": "#d62728", "B measured chassis": "#ff7f0e",
           "C re-identified": "#1f77b4"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-trip", default="docs/ved-per-trip.csv")
    ap.add_argument("--outdir", default="docs/figures")
    args = ap.parse_args()
    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)
    per = pd.read_csv(args.per_trip)

    fig, axes = plt.subplots(1, 3, figsize=(14, 4.8), constrained_layout=True)

    # Energy error, as a distribution rather than one number per arm.
    ax = axes[0]
    arms = list(COLOURS)
    ax.boxplot([per[per.arm == a].energy_err * 100 for a in arms],
               tick_labels=[a.split()[0] for a in arms], showfliers=False,
               medianprops=dict(color="black"))
    for i, a in enumerate(arms, 1):
        y = per[per.arm == a].energy_err * 100
        ax.scatter(np.random.default_rng(0).normal(i, 0.05, len(y)), y, s=9,
                   alpha=0.35, color=COLOURS[a], zorder=3)
    ax.set_ylabel("absolute trip energy error (%)")
    ax.set_ylim(0, 60)
    ax.set_title("A: transfer costs 3.5 points\nover in-domain identification")
    ax.grid(alpha=0.25, axis="y")

    # Terminal SoC against the 2 pp criterion carried over from G2.
    ax = axes[1]
    for a in arms:
        y = np.sort(per[per.arm == a].soc_abs_error * 100)
        ax.plot(y, np.arange(1, len(y) + 1) / len(y) * 100, lw=1.8,
                color=COLOURS[a], label=a)
    ax.axvline(2.0, color="#555555", ls="--", lw=1.2)
    ax.set_xlim(0, 6)
    ax.set_xlabel("terminal SoC error (percentage points)")
    ax.set_ylabel("trips within (%)")
    ax.set_title("B: SoC transfers well\ndashed line is the G2 criterion")
    ax.legend(loc="lower right", frameon=False, fontsize=8)
    ax.grid(alpha=0.25)

    # The residual that no arm removes.
    ax = axes[2]
    bins = [(-20, 0), (0, 12), (12, 24), (24, 40)]
    x = np.arange(len(bins))
    for k, a in enumerate(arms):
        g = per[per.arm == a]
        y = [100 * g.energy_signed[(g.oat >= lo) & (g.oat < hi)].median()
             for lo, hi in bins]
        ax.plot(x, y, "o-", color=COLOURS[a], label=a, lw=1.8)
    ax.axhline(0, color="#555555", lw=1.0)
    ax.set_xticks(x)
    ax.set_xticklabels([f"{lo} to {hi}" for lo, hi in bins])
    ax.set_xlabel("ambient temperature (deg C)")
    ax.set_ylabel("signed trip energy error (%)")
    ax.set_title("C: every arm slopes with temperature\n"
                 "a fixed-parameter plant cannot track it")
    ax.legend(loc="upper left", frameon=False, fontsize=8)
    ax.grid(alpha=0.25)

    fig.savefig(out / "ved-generalisation.png", dpi=150)
    plt.close(fig)
    print(f"wrote {out}/ved-generalisation.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
