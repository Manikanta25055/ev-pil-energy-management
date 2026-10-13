import sys, json; sys.path.insert(0, "paper")
import figstyle as fs

cor = json.load(open("docs/week14-corridor-planner.json"))["routes"]
emp = json.load(open("docs/week13-energy-planner.json"))
ref = {"us06": emp["arms"]["classical"]["saving_vs_tracked_frac"],
       "hwfet": emp["validation"]["arms"]["classical"]["saving_vs_tracked_frac"]}
names = {"us06": "US06-derived route", "hwfet": "HWFET-derived route"}

fig, ax = fs.figure("col", height=2.6)
for i, r in enumerate(["us06", "hwfet"]):
    rows = [v for k, v in cor[r]["rows"].items() if k != "recorded"]
    rows.sort(key=lambda v: v["width_m"])
    w = [v["width_m"] for v in rows]
    s = [100 * v["saving_vs_recorded_frac"] for v in rows]
    ax.plot(w, s, color=fs.C[i], marker=fs.MARKERS[i], linestyle=fs.LINES[0],
            label=names[r] + ", corridor")
    ax.axhline(100 * ref[r], color=fs.C[i], linestyle=fs.LINES[2], linewidth=0.9,
               label=names[r] + ", no traffic")
ax.set_xscale("log")
ax.set_xticks([5, 10, 25, 50, 100, 200])
ax.set_xticklabels(["5", "10", "25", "50", "100", "200"])
ax.minorticks_off()
ax.set_xlabel("Corridor half-width (m)")
ax.set_ylabel("Energy saving against recorded drive (%)")
ax.set_ylim(-1.5, 15.5)
ax.legend(loc="upper left", fontsize=7.5)
fs.save(fig, "fig-planning-corridor")
