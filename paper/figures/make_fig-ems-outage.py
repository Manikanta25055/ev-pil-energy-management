"""Worst-case speed error against link-outage length, handling on and off (corrected model)."""
import json
import sys; sys.path.insert(0, "paper")
import figstyle as fs

D = ["0.2", "0.5", "1", "2", "3", "4", "5", "10"]
x = [float(s) for s in D]
on = [json.load(open(f"docs/week11-a4-on-{s}s.json")) for s in D]
off = [json.load(open(f"docs/week11-a4-off-{s}s.json")) for s in D]
fig, ax = fs.figure("col", height=2.5)
ax.plot(x, [d["err_peak_mps"]["worst"] for d in on], label="Handling on", **fs.line(0))
ax.plot(x, [d["err_peak_mps"]["worst"] for d in off], label="Handling off", **fs.line(1))
ax.axvspan(4, 5, color="#b8860b", alpha=0.15, lw=0)
ax.set_xscale("log"); ax.set_yscale("log")
ax.set_xticks(x); ax.set_xticklabels(D)
ax.minorticks_off()
ax.set_xlabel("Outage length (s)")
ax.set_ylabel("Worst speed error (m/s)")
ax.legend(loc="upper left")
ax.text(3.85, 0.5, "crossover\n(4 to 5 s)", ha="right", va="center", fontsize=8)
fs.save(fig, "fig-ems-outage")
