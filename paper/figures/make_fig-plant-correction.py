import sys; sys.path.insert(0, "paper")
import json
import figstyle as fs

rows = json.load(open("docs/week11-plant-correction.json"))["rows"]
ser = {}
for plant in ("before", "after"):
    pts = sorted(((int(r["arm"].split("-")[1][:-2]), r) for r in rows
                  if r["plant"] == plant and r["arm"].startswith("ceiling-")),
                 key=lambda p: -p[0])
    ser[plant] = pts
labels = [str(k) for k, _ in ser["before"]]
xs = list(range(len(labels)))
fig, axes = fs.figure("col", nrows=2, ncols=1, height=3.5, sharex=True)
for ax, key, yl in ((axes[0], "equivalent_wh_per_km", "billed energy (Wh/km)"),
                    (axes[1], "distance_km", "distance driven (km)")):
    for i, (plant, lab) in enumerate((("before", "before the fix"), ("after", "after the fix"))):
        ax.plot(xs, [r[key] for _, r in ser[plant]], label=lab, **fs.line(i + 1 if i == 0 else 0))
    ax.set_ylabel(yl)
    ax.set_ylim(bottom=0)
axes[0].legend(loc="lower left")
axes[1].set_xticks(xs)
axes[1].set_xticklabels(labels)
axes[1].set_xlabel("constant battery power ceiling (kW, ticks not to scale)")
fs.save(fig, "fig-plant-correction")
