"""Figure for the power-ceiling correction: one fixed ceiling on US06, on the
plant before the fix and after it.

    PYTHONPATH="src:." python3 scripts/plot_plant_correction.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BEFORE_COLOUR = "#c26a2f"
AFTER_COLOUR = "#2f6f9f"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="docs/week11-plant-correction.json")
    ap.add_argument("--out", default="docs/figures/plant-correction.png")
    args = ap.parse_args()

    rows = json.loads(Path(args.data).read_text())["rows"]
    series = {}
    for plant in ("before", "after"):
        pts = sorted((int(r["arm"].split("-")[1][:-2]), r) for r in rows
                     if r["plant"] == plant and r["arm"].startswith("ceiling-"))
        series[plant] = pts
    labels = [str(kw) for kw, _ in series["before"]]
    xs = range(len(labels))

    fig, axes = plt.subplots(1, 3, figsize=(13.0, 4.2))
    for ax, key, ylabel, title in (
        (axes[0], "equivalent_wh_per_km", "energy, Wh/km", "Energy billed"),
        (axes[1], "tracking_rmse_mps", "tracking error (RMS), m/s",
         "How far the car falls behind"),
        (axes[2], "distance_km", "distance covered, km", "Distance driven"),
    ):
        for plant, colour, label in (
            ("before", BEFORE_COLOUR, "before the fix"),
            ("after", AFTER_COLOUR, "after the fix"),
        ):
            ax.plot(xs, [r[key] for _, r in series[plant]], "o-",
                    color=colour, label=label)
        ax.set_xticks(list(xs))
        ax.set_xticklabels(labels)
        ax.set_xlabel("power ceiling, kW (not to scale)")
        ax.set_ylabel(ylabel)
        ax.set_ylim(bottom=0)
        ax.set_title(title, fontsize=10)
        ax.grid(alpha=0.25)
        ax.legend(fontsize=8, frameon=False)

    fig.suptitle(
        "A fixed power ceiling held for the whole of US06, SIMULATED on the "
        "laptop.\nBefore the fix a lower ceiling cut the bill and changed "
        "nothing else. Lines join computed points only.",
        fontsize=9, color="#555")
    fig.tight_layout(rect=(0, 0, 1, 0.88))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, dpi=160)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
