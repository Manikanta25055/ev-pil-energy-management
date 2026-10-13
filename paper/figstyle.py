"""Shared figure style for the mock IEEE Access manuscript.

Usage, from the repository root:

    import sys; sys.path.insert(0, "paper")
    import figstyle as fs
    fig, ax = fs.figure("col")
    ax.plot(x, y, **fs.line(0))
    fs.save(fig, "fig-name")
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

COL_W = 3.5    # inches, one column
PAGE_W = 7.16  # inches, both columns

# Colour-blind-safe, distinct in greyscale by lightness. Use in this order.
C = ["#1f3b73", "#c8553d", "#6b8e23", "#7a7a7a", "#b8860b", "#5d3a9b"]
MARKERS = ["o", "s", "^", "D", "v", "x"]
LINES = ["-", "--", "-.", ":", (0, (5, 1)), (0, (1, 1))]
HATCHES = ["", "///", "...", "xx", "\\\\\\", "--"]

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
    "mathtext.fontset": "stix",
    "font.size": 8.5,
    "axes.labelsize": 8.5,
    "axes.titlesize": 8.5,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "legend.fontsize": 8,
    "axes.linewidth": 0.6,
    "lines.linewidth": 1.1,
    "lines.markersize": 3.5,
    "axes.grid": True,
    "grid.linewidth": 0.3,
    "grid.color": "#c8c8c8",
    "axes.axisbelow": True,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "legend.frameon": False,
    "legend.handlelength": 1.8,
    "savefig.dpi": 300,
    "figure.dpi": 150,
})


def figure(width="col", nrows=1, ncols=1, height=None, **kw):
    """Return (fig, ax). `width` is "col" or "page". Height in inches."""
    w = COL_W if width == "col" else PAGE_W
    if height is None:
        height = 2.4 * nrows if width == "col" else 2.5 * nrows
    return plt.subplots(nrows, ncols, figsize=(w, height),
                        constrained_layout=True, **kw)


def line(i):
    """Keyword arguments for the i-th line series."""
    return {"color": C[i % 6], "marker": MARKERS[i % 6], "linestyle": LINES[i % 6]}


def bar(i):
    """Keyword arguments for the i-th bar series."""
    return {"color": C[i % 6], "hatch": HATCHES[i % 6],
            "edgecolor": "black", "linewidth": 0.4}


def panel_label(ax, text):
    """Put "(a)" style label at the top-left corner of an axes."""
    ax.text(0.0, 1.03, text, transform=ax.transAxes, ha="left", va="bottom",
            fontsize=8.5)


def save(fig, name):
    out = Path(__file__).resolve().parent / "figures" / f"{name}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out)
    plt.close(fig)
    print(out)
