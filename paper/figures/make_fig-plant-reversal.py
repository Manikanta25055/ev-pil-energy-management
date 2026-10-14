import sys; sys.path.insert(0, "paper")
import json
import figstyle as fs

LAB = {("driving_condition", "urban"): "UDDS", ("driving_condition", "highway"): "HWFET",
       ("driving_condition", "aggressive_mixed"): "US06 mixed",
       ("road_grade", "uphill"): "Uphill", ("road_grade", "flat"): "Flat",
       ("road_grade", "downhill"): "Downhill",
       ("battery_state", "high"): "SOC 0.85", ("battery_state", "medium"): "SOC 0.55",
       ("battery_state", "low"): "SOC 0.25",
       ("sensor_noise", "floor"): "Noise 1x", ("sensor_noise", "elevated"): "Noise 3x",
       ("sensor_noise", "severe"): "Noise 10x",
       ("comm_delay", "none"): "No delay",
       ("driver_aggression", "normal"): "Driver 1.0",
       ("driver_aggression", "brisk"): "Driver 1.25",
       ("driver_aggression", "aggressive"): "Driver 1.5"}


def diffs(path):
    runs = json.load(open(path))["runs"]
    by = {}
    for r in runs:
        by.setdefault((r["scenario"], r["level"]), {})[r["controller"]] = r
    out = {}
    for k in LAB:
        c = by[k]
        out[k] = (100 * (c["actor"]["equivalent_wh_per_km"]
                         / c["rule"]["equivalent_wh_per_km"] - 1))
    return out

early = diffs("docs/week10-pil-campaign.json")
late = diffs("docs/week11-pil-corrected.json")
order = sorted(LAB, key=lambda k: early[k], reverse=True)
ys = list(range(len(order)))
fig, ax = fs.figure("col", height=4.3)
ax.axvline(0, color="black", linewidth=0.6)
ax.scatter([early[k] for k in order], ys, s=18, facecolors="none",
           edgecolors=fs.C[1], marker="o", linewidths=1.0,
           label="earlier campaign", zorder=3)
ax.scatter([late[k] for k in order], ys, s=16, color=fs.C[0], marker="s",
           label="corrected campaign", zorder=3)
ax.set_yticks(ys)
ax.set_yticklabels([LAB[k] for k in order])
ax.invert_yaxis()
ax.set_xlabel("learned minus rules, comparable energy (%)")
ax.legend(loc="upper left")
fs.save(fig, "fig-plant-reversal")
