import sys, json; sys.path.insert(0, "paper")
import figstyle as fs
import numpy as np

rows = [("none", "A0 b7"), ("rule monitor", "A2 monitor"),
        ("GRU", "A2 gru16v3"), ("FastGRNN", "A2 fastgrnn16v3")]
vals = {}
for sp in ("val", "test"):
    d = json.load(open(f"docs/week13-arch-{sp}.json"))["rows"]
    vals[sp] = [d[k]["summary"]["worst_peak_err_mps"] for _, k in rows]

fig, ax = fs.figure("col")
x = np.arange(len(rows)); w = 0.38
for i, (sp, lab) in enumerate([("val", "Validation (HWFET)"), ("test", "Test (US06)")]):
    bars = ax.bar(x + (i - 0.5) * w, vals[sp], w, label=lab, **fs.bar(i * 1 if i == 0 else 1))
    for r in bars:
        ax.text(r.get_x() + r.get_width() / 2, r.get_height() + 0.15,
                f"{r.get_height():.1f}", ha="center", va="bottom", fontsize=8)
ax.set_xticks(x); ax.set_xticklabels([r[0] for r in rows])
ax.set_ylim(0, 16.5)
ax.set_xlabel("Reviewer in the supervisory slot")
ax.set_ylabel("Worst peak tracking error (m/s)")
ax.legend(loc="upper left")
fs.save(fig, "fig-estimation-reviewers")
