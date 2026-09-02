"""Figure for ablation A4 as measured on the board.

The companion to `plot_a4.py`, which draws the prediction. Same two colours for
the same two modes, so the measured figure and the predicted one can be read
against each other, and the same insistence on saying on the face of the figure
which is which.

Two panels, because A4 turned out to cost something the prediction said it did
not. The left panel is tracking error, where the prediction's direction holds:
switching the handling off tracks better. The right is peak battery current
during the recovery, where the two modes separate by a wide margin, against a
prediction that they would not separate at all. Plotting only tracking would
report the handling as a pure cost, which is the reading the current panel
refutes.

Both panels are paired: the same eight blackout onsets, in the same cycle, run
against each build in turn.

    PYTHONPATH="src:." python3 scripts/plot_a4_measured.py
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
    ap.add_argument("--on-json", default="docs/week9-a4-closed-on.json")
    ap.add_argument("--off-json", default="docs/week9-a4-closed-off.json")
    ap.add_argument("--out", default="docs/figures/week9-a4-measured.png")
    args = ap.parse_args()

    on = json.loads(Path(args.on_json).read_text())
    off = json.loads(Path(args.off_json).read_text())

    on_rows = on["blackouts"]
    off_rows = off["blackouts"]
    onsets_on = [r["onset_s"] for r in on_rows]
    onsets_off = [r["onset_s"] for r in off_rows]
    if onsets_on != onsets_off:
        raise SystemExit(
            "the two runs do not share onsets, so they are not paired:\n"
            f"  on:  {onsets_on}\n  off: {onsets_off}")

    x = np.arange(len(on_rows))
    labels = [f"{r['onset_s']:.0f}" for r in on_rows]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.0, 4.2))

    for ax, key, ylabel, title in (
        (ax1, "err_peak_mps", "peak |speed error|, m/s",
         "Tracking: the handling costs error"),
        (ax2, "i_peak_recovery_a", "peak |battery current| in recovery, A",
         "Recovery current: the handling costs stress too"),
    ):
        w = 0.38
        ax.bar(x - w / 2, [r[key] for r in on_rows], w, color=ON_COLOUR,
               label="handling on (shipped)")
        ax.bar(x + w / 2, [r[key] for r in off_rows], w, color=OFF_COLOUR,
               label="handling off (A4)")
        ax.set_xticks(x, labels)
        ax.set_xlabel("blackout onset in the cycle, s")
        ax.set_ylabel(ylabel)
        ax.set_title(title, fontsize=10)
        ax.grid(alpha=0.25, axis="y")
        ax.legend(fontsize=8, frameon=False)

    cyc = on["cycle"]
    n = len(on_rows)
    fig.suptitle(
        f"Ablation A4, MEASURED on the board. {n} paired blackouts of "
        f"{on['blackout_s']:g} s on {cyc.upper()}, closed loop: the plant is "
        f"stepped with the torque the board commanded.",
        fontsize=9, color="#555")
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, dpi=160)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
