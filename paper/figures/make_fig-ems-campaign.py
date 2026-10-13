"""Corrected PIL campaign: energy difference and tracking error, 16 valid settings."""
import json
import sys; sys.path.insert(0, "paper")
import numpy as np
import figstyle as fs

runs = json.load(open("docs/week11-pil-corrected.json"))["runs"]
cell = {}
for r in runs:
    cell.setdefault((r["scenario"], r["level"]), {})[r["controller"]] = r

order = [
    ("driving_condition", "urban", "urban"),
    ("driving_condition", "highway", "highway"),
    ("driving_condition", "aggressive_mixed", "mixed"),
    ("comm_delay", "none", "no delay"),
    ("road_grade", "uphill", "uphill"),
    ("road_grade", "flat", "flat"),
    ("road_grade", "downhill", "downhill"),
    ("battery_state", "high", "SOC 0.85"),
    ("battery_state", "medium", "SOC 0.55"),
    ("battery_state", "low", "SOC 0.25"),
    ("sensor_noise", "floor", "noise 1x"),
    ("sensor_noise", "elevated", "noise 3x"),
    ("sensor_noise", "severe", "noise 10x"),
    ("driver_aggression", "normal", "driver 1.0"),
    ("driver_aggression", "brisk", "driver 1.25"),
    ("driver_aggression", "aggressive", "driver 1.5"),
]
labels, diff, trk_r, trk_a, cyc = [], [], [], [], []
for ax_, lv, lab in order:
    c = cell[(ax_, lv)]
    rule, act = c["rule"], c["actor"]
    assert max(rule["tracking_rmse_mps"], act["tracking_rmse_mps"]) < 1.0
    labels.append(lab)
    diff.append(100 * (act["equivalent_wh_per_km"] / rule["equivalent_wh_per_km"] - 1))
    trk_r.append(rule["tracking_rmse_mps"])
    trk_a.append(act["tracking_rmse_mps"])
    cyc.append(rule["cycle"])
assert len(order) == 16

fig, axs = fs.figure("page", nrows=2, ncols=1, height=4.3)
x = np.arange(16)
a0, a1 = axs
a0.bar(x, diff, width=0.65, **fs.bar(0))
a0.axhline(0, color="black", lw=0.6)
a0.set_ylabel("Learned minus rules (%)")
a0.set_xticks(x); a0.set_xticklabels([])
a0.set_ylim(-1, 6.6)
for i, d in enumerate(diff):
    if d > 2:
        a0.text(i, d + 0.12, f"{d:+.2f}", ha="center", va="bottom", fontsize=8)
fs.panel_label(a0, "(a)")

w = 0.38
a1.bar(x - w / 2, trk_r, width=w, label="Rule-based", **fs.bar(0))
a1.bar(x + w / 2, trk_a, width=w, label="Learned (SAC)", **fs.bar(1))
a1.set_yscale("log")
a1.set_ylabel("Tracking RMSE (m/s)")
a1.set_xticks(x); a1.set_xticklabels(labels, rotation=40, ha="right")
a1.legend(loc="upper left", ncol=2)
a1.set_ylim(1e-3, 3)
fs.panel_label(a1, "(b)")

# cycle brackets under panel (a): UDDS, HWFET, US06
for ax_ in (a0, a1):
    ax_.axvline(1.5, color="#7a7a7a", lw=0.5, ls=":")
    ax_.axvline(0.5, color="#7a7a7a", lw=0.5, ls=":")
a0.text(0, 6.2, "UDDS", ha="center", fontsize=8)
a0.text(1, 6.2, "HWFET", ha="center", fontsize=8)
a0.text(8.5, 6.2, "US06 (14 settings)", ha="center", fontsize=8)
fs.save(fig, "fig-ems-campaign")
