"""Loop-period deviation histograms, final build, from docs/ CSV files."""
import csv
import sys; sys.path.insert(0, "paper")
import numpy as np
import figstyle as fs


def read(path):
    with open(path) as f:
        rows = list(csv.DictReader(f))
    return [r["bin_upper_us"] for r in rows], [int(r["count"]) for r in rows]


labels, single = read("docs/g3-jitter-histogram-arduino.csv")
pooled = np.zeros(len(single), dtype=int)
for i in range(1, 6):
    lab, c = read(f"docs/g3-repeat-arduino-{i}-hist.csv")
    assert lab == labels
    pooled += np.array(c)

fig, ax = fs.figure("col", height=2.6)
n = len(labels)
x = np.arange(n)
w = 0.38
floor = 0.5
ax.bar(x - w / 2, np.maximum(single, floor), w, bottom=0, **fs.bar(0),
       label="one run, 59,650 loops")
ax.bar(x + w / 2, np.maximum(pooled, floor), w, **fs.bar(1),
       label="five runs pooled, 298,250 loops")
ax.set_yscale("log")
ax.set_ylim(floor, 1e8)
for xi, (s, p) in enumerate(zip(single, pooled)):
    if s == 0 and p == 0:
        ax.text(xi, 0.75, "0", ha="center", va="bottom", fontsize=8)
tol = labels.index("1000")
ax.axvline(tol + 0.5, color="black", ls="--", lw=0.9)
ax.text(tol + 0.35, 3e2, "1,000 µs: gate tolerance\nand late-step limit", ha="right",
        va="center", fontsize=8)
ax.set_xticks(x)
ax.set_xticklabels([f"{l}" if l != "inf" else ">5000" for l in labels],
                   rotation=60, ha="right")
ax.set_xlabel("Deviation of loop period from 10 ms, upper bin edge (µs)")
ax.set_ylabel("Control loops (log scale)")
ax.legend(loc="upper left", bbox_to_anchor=(0.0, 1.0), fontsize=8)
fs.save(fig, "fig-platform-jitter")
