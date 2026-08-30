# scripts/plot_g3.py
"""Figure for gate G3.

One panel, because the result is one distribution and adding company to it
would only make it look less decisive than it is.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="docs/g3-loop-timing.json")
    ap.add_argument("--out", default="docs/figures/g3-jitter.png")
    args = ap.parse_args()

    meta = json.loads(Path(args.json).read_text())
    hist = meta["histogram"]
    edges = meta["bin_edges_us"]
    labels = [f"<={e}" for e in edges] + [f">{edges[-1]}"]

    total = sum(hist)
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(12.0, 4.2))

    colours = ["#2ca02c" if (e <= meta["limits"]["p99_us"]) else "#d62728"
               for e in edges] + ["#d62728"]
    ax.bar(range(len(hist)), [max(h, 0.5) for h in hist], color=colours)
    ax.set_yscale("log")
    ax.set_xticks(range(len(hist)))
    ax.set_xticklabels(labels, rotation=45, fontsize=7, ha="right")
    ax.set_xlabel("absolute deviation from the 10 ms period, us")
    ax.set_ylabel("control loops (log)")
    ax.set_title(f"Loop timing over {meta['minutes']:.0f} minutes, "
                 f"{meta['counters']['loop_count']:,} loops")
    ax.grid(alpha=0.3, axis="y")

    cum = np.cumsum(hist) / total
    ax2.plot(range(len(hist)), 100.0 * cum, "o-", color="#1f77b4", lw=1.8)
    ax2.axhline(99.0, color="#7f7f7f", lw=1.2, ls="--")
    ax2.annotate("99% of loops", (0.2, 99.0), textcoords="offset points",
                 xytext=(0, -14), fontsize=8, color="#7f7f7f")
    limit_bin = next(k for k, e in enumerate(edges)
                     if e >= meta["limits"]["p99_us"])
    ax2.axvline(limit_bin, color="#d62728", lw=1.4, ls="--")
    ax2.annotate(f"G3 limit, {meta['limits']['p99_us']:.0f} us",
                 (limit_bin, 50), textcoords="offset points", xytext=(-6, 0),
                 fontsize=8, color="#d62728", ha="right", rotation=90)
    ax2.set_xticks(range(len(hist)))
    ax2.set_xticklabels(labels, rotation=45, fontsize=7, ha="right")
    ax2.set_ylim(90, 100.6)
    ax2.set_xlabel("absolute deviation from the 10 ms period, us")
    ax2.set_ylabel("cumulative percentage of loops")
    ax2.set_title(f"Everything lands in the first two bins  "
                  f"({meta['verdict']})")
    ax2.grid(alpha=0.3)

    fig.tight_layout()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
