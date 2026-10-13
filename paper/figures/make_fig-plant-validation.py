import sys; sys.path.insert(0, "paper")
import csv
import figstyle as fs

rows = list(csv.DictReader(open("docs/g2-per-trip.csv")))
ids = [r["trip_id"].replace("Trip", "") for r in rows]
soc = [float(r["soc_abs_error"]) * 100.0 for r in rows]
bound = 2.0
fig, ax = fs.figure("col", height=2.3)
for i, (t, v) in enumerate(zip(ids, soc)):
    fail = v > bound
    k = fs.bar(1 if fail else 0)
    ax.bar(i, v, width=0.65, **k)
    ax.text(i, v + 0.05, f"{v:.2f}", ha="center", va="bottom", fontsize=8, zorder=5,
            bbox=dict(facecolor="white", edgecolor="none", pad=0.8))
ax.axhline(bound, color="black", linestyle="--", linewidth=0.9)
ax.text(len(ids) - 0.5, bound + 0.12, "bound, 2.00 pp", ha="right", va="bottom", fontsize=8)
ax.set_xticks(range(len(ids)))
ax.set_xticklabels(ids)
ax.set_xlabel("validation trip")
ax.set_ylabel("terminal SOC error (pp)")
ax.set_ylim(0, 3.1)
ax.grid(axis="x", visible=False)
fs.save(fig, "fig-plant-validation")
