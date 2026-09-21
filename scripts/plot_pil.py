"""Figures for the week-10 PIL campaign.

Two panels, because the campaign answers two questions that should not share
an axis. The upper panel is energy on the comparable scale, which is the
controller comparison. The lower is tracking error, which is the constraint
the controllers are operating under and which has to be shown beside the
energy: an arm that saved energy by tracking worse would look good on the
upper panel alone.

Every point is one run on the chip. There are no intervals because each cell
was run once, and drawing one would invent a spread that was not measured.

    PYTHONPATH="src:." python3 scripts/plot_pil.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from evpil.control.scenarios import AXES

RULE_COLOUR = "#2f6f9f"
ACTOR_COLOUR = "#c26a2f"

AXIS_TITLES = {
    "driving_condition": "Driving",
    "road_grade": "Grade",
    "battery_state": "Battery",
    "sensor_noise": "Noise",
    "comm_delay": "Delay",
    "driver_aggression": "Driver",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--campaign", default="docs/week10-pil-campaign.json")
    ap.add_argument("--out", default="docs/figures/pil-energy.png")
    args = ap.parse_args()

    data = json.loads(Path(args.campaign).read_text())
    cells: dict = {}
    for r in data["runs"]:
        cells.setdefault((r["scenario"], r["level"]), {})[r["controller"]] = r

    order = [(axis, lv.level) for axis in AXES for lv in AXES[axis]
             if (axis, lv.level) in cells]
    labels = [f"{AXIS_TITLES.get(a, a)}\n{lv.replace('_', ' ')}"
              for a, lv in order]
    x = np.arange(len(order), dtype=float)
    width = 0.38

    def series(controller: str, field: str):
        return [cells[k].get(controller, {}).get(field, float("nan"))
                for k in order]

    fig, (ax_e, ax_t) = plt.subplots(
        2, 1, figsize=(13, 8), sharex=True,
        gridspec_kw={"height_ratios": [3, 2], "hspace": 0.12})

    ax_e.bar(x - width / 2, series("rule", "equivalent_wh_per_km"), width,
             label="Rule-based manager", color=RULE_COLOUR)
    ax_e.bar(x + width / 2, series("actor", "equivalent_wh_per_km"), width,
             label="Learned (SAC) policy", color=ACTOR_COLOUR)
    ax_e.set_ylabel("Energy, Wh/km\n(shed cabin heat charged back)")
    ax_e.legend(frameon=False, ncol=2, loc="upper left")
    ax_e.grid(axis="y", alpha=0.25)
    ax_e.set_axisbelow(True)

    ax_t.bar(x - width / 2, series("rule", "tracking_rmse_mps"), width,
             color=RULE_COLOUR)
    ax_t.bar(x + width / 2, series("actor", "tracking_rmse_mps"), width,
             color=ACTOR_COLOUR)
    ax_t.set_ylabel("Tracking error\nRMSE, m/s")
    ax_t.grid(axis="y", alpha=0.25)
    ax_t.set_axisbelow(True)

    # Separators between axes, so the six groups read as six experiments
    # rather than eighteen unrelated bars.
    boundaries = []
    for i in range(1, len(order)):
        if order[i][0] != order[i - 1][0]:
            boundaries.append(i - 0.5)
    for b in boundaries:
        for ax in (ax_e, ax_t):
            ax.axvline(b, color="#999999", lw=0.8, ls=":")

    ax_t.set_xticks(x)
    ax_t.set_xticklabels(labels, fontsize=8)
    ax_e.set_title("The two energy managers across six kinds of variation, "
                   "measured on the chip", loc="left")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150, bbox_inches="tight")
    print(f"wrote {out}  ({len(order)} settings)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
