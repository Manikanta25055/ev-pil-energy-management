# scripts/plot_sac.py
"""Figures for the week 8 SAC campaign and ablation A3.

Both panels are drawn against the rule-based baseline and the dynamic-
programming optimum rather than against the untrained policy. Plotting a
learning curve on its own shows a line going up and says nothing about whether
the destination was worth reaching.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ARM_COLOUR = {"with-forecast": "#2f6f9f", "without-forecast": "#c26a2f"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="docs/week8-sac.json")
    ap.add_argument("--baselines", default="docs/week7-control-baselines.json")
    ap.add_argument("--out", default="docs/figures/week8-sac.png")
    args = ap.parse_args()

    d = json.loads(Path(args.json).read_text())
    base = d["baseline"]["equivalent_wh_per_km"]

    optimum = None
    bpath = Path(args.baselines)
    if bpath.exists():
        rows = json.loads(bpath.read_text())["rows"]
        for r in rows:
            if r["cycle"] == d["cycle"] and r["arm"] == "dp-comfort-priced":
                optimum = r["equivalent_wh_per_km"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.5, 4.4))

    # --- learning curves -------------------------------------------------
    for arm, colour in ARM_COLOUR.items():
        seeds = [k for k in d["curves"] if k.startswith(arm)]
        for i, key in enumerate(sorted(seeds)):
            c = d["curves"][key]
            ax1.plot([p["steps"] / 1000 for p in c],
                     [p["equivalent_wh_per_km"] for p in c],
                     color=colour, alpha=0.45, lw=1.0,
                     label=arm if i == 0 else None)
    ax1.axhline(base, color="#1a1a1a", lw=1.4, ls="-", label="rule-based")
    if optimum is not None:
        ax1.axhline(optimum, color="#7a7a7a", lw=1.2, ls="--",
                    label="DP optimum")
    ax1.set_xlabel("training steps (thousands)")
    ax1.set_ylabel("comparable Wh/km on the validation cycle")
    ax1.set_title("Five seeds per arm, evaluated on whole cycles")
    # Lower is better, and no run ends below the two reference lines.
    ax1.set_ylim(top=max(ax1.get_ylim()[1], base + 0.2))
    ax1.legend(fontsize=8, frameon=False)
    ax1.grid(alpha=0.25)

    # --- final distribution ----------------------------------------------
    arms = list(ARM_COLOUR)
    for i, arm in enumerate(arms):
        vals = d["summary"][arm]["per_seed"]
        lo, hi = d["summary"][arm]["ci95"]
        ax2.scatter([i] * len(vals), vals, s=36, zorder=3,
                    color=ARM_COLOUR[arm], label=arm)
        ax2.plot([i, i], [lo, hi], color=ARM_COLOUR[arm], lw=2.4, alpha=0.5,
                 zorder=2)
        ax2.scatter([i], [np.mean(vals)], marker="_", s=420, zorder=4,
                    color=ARM_COLOUR[arm])

    ax2.axhline(base, color="#1a1a1a", lw=1.4, label="rule-based")
    if optimum is not None:
        # These two lines coincide to within the thickness of the ink, and
        # that is week 7's result rather than a plotting fault: the offline
        # optimum and two thresholds land on the same number.
        ax2.axhline(optimum, color="#7a7a7a", lw=1.2, ls="--",
                    label="DP optimum (coincides)")
    ax2.set_xticks(range(len(arms)),
                   ["forecast\nin state", "forecast\nremoved"])
    ax2.set_xlim(-0.6, len(arms) - 0.4)
    ax2.set_ylabel("comparable Wh/km")
    ax2.set_title("Ablation A3, with 95% bootstrap intervals")
    ax2.legend(fontsize=8, frameon=False)
    ax2.grid(axis="y", alpha=0.25)

    a3 = d["a3"]
    ax2.set_xlabel(
        f"A3: forecast minus no-forecast = {a3['diff_mean_wh_per_km']:+.3f} "
        f"Wh/km, 95% CI [{a3['ci95'][0]:+.3f}, {a3['ci95'][1]:+.3f}]"
        + ("\nthe interval contains zero" if a3["null"] else ""),
        fontsize=8, color="#555")

    fig.tight_layout()
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, dpi=160)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
