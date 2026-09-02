"""Figure for the ablation A4 prediction.

Two panels, because the A4 prediction has two halves that disagree and a single
panel would have to pick one. The left panel is the median case, where turning
the handling off tracks better at every duration tried. The right is the worst
case, where that reverses. Plotting only the median would say the limp path is
a pure cost; plotting only the worst case would say it is a pure benefit.
Neither is the result.

The figure is labelled as a prediction on its face. It is drawn from a host
simulation with no board attached, and it sits next to measured figures in the
same directory, so the axis title says so rather than relying on the filename.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ON_COLOUR = "#2f6f9f"
OFF_COLOUR = "#c26a2f"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="docs/week9-a4-prediction.json")
    ap.add_argument("--out", default="docs/figures/week9-a4-prediction.png")
    args = ap.parse_args()

    d = json.loads(Path(args.json).read_text())
    by = d["by_duration"]
    durs = sorted(float(k) for k in by)
    x = np.arange(len(durs))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.0, 4.2), sharex=True)

    for ax, stat, title in (
        (ax1, "median", "Median case: the handling costs tracking"),
        (ax2, "worst", "Worst case: the handling buys the tail back"),
    ):
        on = [by[_k(d_)][f"on_{stat}_peak_err_mps"] for d_ in durs]
        off = [by[_k(d_)][f"off_{stat}_peak_err_mps"] for d_ in durs]
        ax.plot(x, on, "o-", color=ON_COLOUR, lw=1.8,
                label="handling on (shipped)")
        ax.plot(x, off, "s-", color=OFF_COLOUR, lw=1.8,
                label="handling off (A4)")
        ax.set_xticks(x, [f"{v:g}" for v in durs])
        ax.set_xlabel("host outage, s")
        ax.set_yscale("log")
        ax.set_title(title, fontsize=10)
        ax.grid(alpha=0.25, which="both")
        ax.legend(fontsize=8, frameon=False)

        # Mark where the two lines cross, which is the whole point of the
        # right-hand panel and is easy to miss on a log axis.
        for i in range(1, len(durs)):
            if (off[i] > on[i]) != (off[i - 1] > on[i - 1]):
                ax.axvline(i - 0.5, color="#555", ls=":", lw=1.2)
                ax.annotate("crossover", xy=(i - 0.5, max(on) * 0.35),
                            fontsize=8, color="#555", rotation=90,
                            ha="right", va="center")
                break

    ax1.set_ylabel("peak |speed error|, m/s")

    n = d["n_paired_blackouts"]
    fig.suptitle(
        f"Ablation A4, PREDICTED on the host -- not measured. "
        f"{n} paired blackouts, 4 cycles, {len(durs)} durations, "
        f"20 swept onsets each.",
        fontsize=9, color="#555")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, dpi=160)
    print(f"wrote {args.out}")
    return 0


def _k(v: float) -> str:
    """by_duration keys were written with str(float), so 1.0 is '1.0'."""
    return str(v)


if __name__ == "__main__":
    raise SystemExit(main())
