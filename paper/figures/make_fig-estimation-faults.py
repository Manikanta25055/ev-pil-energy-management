import sys, json; sys.path.insert(0, "paper")
import figstyle as fs
import numpy as np

d = json.load(open("docs/week13-b7-pil.json"))["arms"]
types = ["stuck", "dropout", "bias +0.5", "bias -0.5", "bias +3.0"]
labels = ["stuck", "dropout", "+0.5", "-0.5", "+3.0"]
old = [d["B6"]["by_fault"][t]["detected_in_time"] for t in types]
new = [d["B7"]["by_fault"][t]["detected_in_time"] for t in types]
n = [d["B7"]["by_fault"][t]["runs"] for t in types]

fig, ax = fs.figure("col")
x = np.arange(len(types)); w = 0.38
b1 = ax.bar(x - w / 2, old, w, label="Acceleration-residual detector", **fs.bar(1))
b2 = ax.bar(x + w / 2, new, w, label="Bias-aware detector", **fs.bar(0))
for bars in (b1, b2):
    for r in bars:
        ax.text(r.get_x() + r.get_width() / 2, r.get_height() + 0.1,
                f"{int(r.get_height())}", ha="center", va="bottom", fontsize=8)
ax.set_xticks(x); ax.set_xticklabels(labels)
ax.set_ylim(0, 10.8); ax.set_yticks([0, 2, 4, 6, 8])
ax.set_xlabel("Injected fault (offsets in m/s)")
ax.set_ylabel("Caught within 0.5 s (of 8)")
ax.legend(loc="upper center", ncol=1, bbox_to_anchor=(0.5, 1.02))
fs.save(fig, "fig-estimation-faults")
