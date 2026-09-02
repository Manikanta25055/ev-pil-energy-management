"""Figures for ablation A2's third rung, the distilled students.

Two panels. The left is claim C4's Pareto front: accuracy against what the arm
costs to run. The right is the only question the experiment was built to
answer, which the front cannot show because it plots arms rather than pairs --
whether the same student taught by the teacher beats itself taught by the data.

The latency axis is an ESTIMATE and is labelled as one on the axis rather than
in a caption. This project has already measured what that estimate is worth:
the deployed encoder was predicted at 22.28 ms and timed on silicon at 36.46,
so the estimate ran 64% low. It ranks arms correctly and must not be read as a
latency.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

COLOUR = {"teacher": "#6a6a6a", "direct": "#2f6f9f", "distilled": "#c26a2f"}


def kind(arm: str) -> str:
    if arm == "teacher":
        return "teacher"
    return "distilled" if arm.endswith("distilled") else "direct"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="docs/a2-distillation.json")
    ap.add_argument("--out", default="docs/figures/a2-distillation.png")
    args = ap.parse_args()

    d = json.loads(Path(args.json).read_text())
    S = d["summary"]
    budget_ms = 40.0

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.4, 4.4))

    # ---- left: the Pareto front ----------------------------------------
    #
    # A student and its distilled twin are the same architecture, so they cost
    # exactly the same and sit at the same x. Labelling each point separately
    # therefore writes both labels on top of each other, which the first draft
    # of this figure did. The size is labelled once per column and the two
    # teaching methods are separated by colour, with a line joining the pair so
    # the vertical distance -- which is the entire result -- is what the eye
    # lands on.
    by_x: dict[float, list] = {}
    for arm, a in S.items():
        by_x.setdefault(a["cost_model"]["latency_ms"], []).append((arm, a))

    for x, entries in by_x.items():
        ys = [a["int8_mean_rmse_w"] / 1000.0 for _, a in entries]
        if len(entries) > 1:
            ax1.plot([x, x], [min(ys), max(ys)], color="#999", lw=1.2,
                     zorder=1)
        for arm, a in entries:
            y = a["int8_mean_rmse_w"] / 1000.0
            ax1.errorbar(x, y, yerr=a["int8_sd_rmse_w"] / 1000.0, fmt="o",
                         color=COLOUR[kind(arm)], ms=9, capsize=3, zorder=3)
        label = entries[0][0].replace("student-", "").split("-")[0]
        ax1.annotate(label, xy=(x, max(ys)), xytext=(0, 12),
                     textcoords="offset points", fontsize=9, color="#333",
                     ha="center", fontweight="bold")

    ax1.axvline(budget_ms, color="#b03030", lw=1.4, ls="--")
    ax1.annotate(f"{budget_ms:.0f} ms budget", xy=(budget_ms, 0.06),
                 xycoords=("data", "axes fraction"), rotation=90,
                 fontsize=8, color="#b03030", ha="right", va="bottom")

    # The persistence baseline is 13.2 kW against a spread of about 0.25 kW
    # across the arms. Drawing it squashes every point this figure is about
    # into the bottom eighth of the axis, so it is stated instead of plotted.
    base = d["persistence_rmse_w"] / 1000.0
    ax1.set_xscale("log")
    ax1.set_xlabel("estimated latency, ms (MAC-count estimate, known to run "
                   "~64% low)")
    ax1.set_ylabel("int8 RMSE at 3 s, kW")
    ax1.set_title(f"Accuracy against cost (persistence baseline {base:.2f} kW, "
                  f"above this axis)", fontsize=10)
    ax1.grid(alpha=0.25, which="both")
    ax1.margins(y=0.22)

    handles = [plt.Line2D([], [], marker="o", ls="", color=c, label=k)
               for k, c in COLOUR.items()]
    ax1.legend(handles=handles, fontsize=8, frameon=False, loc="upper right")

    # ---- right: the paired comparison ----------------------------------
    names = list(d["verdicts"])
    x = np.arange(len(names))
    for i, name in enumerate(names):
        v = d["verdicts"][name]
        deltas = np.array(v["per_seed_delta_w"])
        ax2.scatter([i] * len(deltas), deltas, color=COLOUR["distilled"],
                    alpha=0.75, zorder=3)
        ax2.scatter([i], [v["mean_delta_w"]], marker="_", s=460, zorder=4,
                    color="#1a1a1a")
    ax2.axhline(0.0, color="#1a1a1a", lw=1.3)
    ax2.set_xticks(x, [n.replace("student-", "") for n in names])
    ax2.set_xlim(-0.6, len(names) - 0.4)
    ax2.set_ylabel("distilled minus direct, W (negative = distillation helps)")
    ax2.set_title("The same student, taught two ways", fontsize=10)
    ax2.grid(axis="y", alpha=0.25)

    bits = []
    for name in names:
        v = d["verdicts"][name]
        bits.append(f"{name.replace('student-', '')}: {v['mean_delta_w']:+.0f} W "
                    f"({v['relative']:+.2%})"
                    + ("" if v["consistent_sign"] else ", sign flips"))
    ax2.set_xlabel("   ".join(bits), fontsize=8, color="#555")

    fig.suptitle(
        f"Ablation A2, third rung: distillation. Teacher "
        f"d_model {d['teacher_config']['d_model']}, "
        f"{d['teacher_config']['layers']} layers; target = "
        f"{d['spec']['alpha']:.2f} truth + {1 - d['spec']['alpha']:.2f} "
        f"teacher; {d['spec']['seeds']} seeds.", fontsize=9, color="#555")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, dpi=160)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
