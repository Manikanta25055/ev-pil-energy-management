"""Figure for ablation A4 swept over outage length, on the Arduino build.

`plot_a4_measured.py` draws one outage length at a time, as paired bars over
the eight onsets. This draws the sweep: the same statistics against outage
length, so the crossover is read off one axis instead of across two figures.

Every point is from the Arduino build with the SAC actor driving the outer
loop. The IDF points in `docs/week9-a4.md` predate the actor and are not
plotted here, because mixing them would put a firmware change on the same axis
as the variable being swept.

    PYTHONPATH="src:." python3 scripts/plot_a4_sweep.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ON_COLOUR = "#2f6f9f"
OFF_COLOUR = "#c26a2f"
# File-name tags, so 0.2 s reads week9-a4-arduino-on-0.2s.json.
DURATIONS = ("0.2", "0.5", "1", "2", "3", "4", "5", "10")
SECONDS = [float(s) for s in DURATIONS]


def load_pair(docs: Path, s: str):
    on = json.loads((docs / f"week9-a4-arduino-on-{s}s.json").read_text())
    off = json.loads((docs / f"week9-a4-arduino-off-{s}s.json").read_text())
    onsets_on = [r["onset_s"] for r in on["blackouts"]]
    onsets_off = [r["onset_s"] for r in off["blackouts"]]
    if onsets_on != onsets_off:
        raise SystemExit(
            f"{s} s: the two runs do not share onsets, so they are not paired:\n"
            f"  on:  {onsets_on}\n  off: {onsets_off}")
    return on, off


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", default="docs")
    ap.add_argument("--out", default="docs/figures/week9-a4-arduino-sweep.png")
    args = ap.parse_args()

    docs = Path(args.docs)
    pairs = [load_pair(docs, s) for s in DURATIONS]

    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(13.0, 4.2))

    for ax, key, stat, ylabel, title in (
        (ax1, "err_peak_mps", "median", "peak |speed error|, m/s",
         "Typical outage"),
        (ax2, "err_peak_mps", "worst", "peak |speed error|, m/s",
         "Worst of eight outages"),
        (ax3, "i_peak_recovery_a", "median",
         "peak |battery current| in recovery, A", "Recovery current, typical"),
    ):
        for idx, colour, label in ((0, ON_COLOUR, "handling on (shipped)"),
                                   (1, OFF_COLOUR, "handling off (A4)")):
            ys = [p[idx][key][stat] for p in pairs]
            ax.plot(SECONDS, ys, "o-", color=colour, label=label)
        # 0.2 s to 10 s spans a factor of fifty; a linear axis would pile the
        # short outages on top of each other.
        ax.set_xscale("log")
        ax.set_xticks(SECONDS)
        ax.set_xticklabels(DURATIONS)
        ax.minorticks_off()
        ax.set_xlabel("outage length, s (log scale)")
        ax.set_ylabel(ylabel)
        ax.set_title(title, fontsize=10)
        ax.grid(alpha=0.25)
        ax.legend(fontsize=8, frameon=False)

    on0 = pairs[0][0]
    fig.suptitle(
        f"Ablation A4 swept over outage length, MEASURED on the board "
        f"(Arduino build, actor in the loop).\n{on0['n_blackouts']} paired "
        f"blackouts per point on {on0['cycle'].upper()}, closed loop. Lines "
        f"join measured points only; nothing between them was measured.",
        fontsize=9, color="#555")
    fig.tight_layout(rect=(0, 0, 1, 0.88))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, dpi=160)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
