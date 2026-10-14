"""Corrected PIL campaign: paired energy difference per setting and tracking error.

Panel (a) reads docs/paper-table5-stats.json (paired differences, nominal
repeats); panel (b) reads docs/week11-pil-corrected.json (tracking RMSE).
"""
import json
import sys; sys.path.insert(0, "paper")
import numpy as np
import matplotlib.patches as mp
import figstyle as fs

stats = json.load(open("docs/paper-table5-stats.json"))
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
nominal = {tuple(k) for k in stats["nominal_us06_replicates"]}
assert len(order) == 16 and len(nominal) == 5

labels, diff, is_nom, trk_r, trk_a = [], [], [], [], []
for ax_, lv, lab in order:
    c = cell[(ax_, lv)]
    rule, act = c["rule"], c["actor"]
    assert max(rule["tracking_rmse_mps"], act["tracking_rmse_mps"]) < 1.0
    labels.append(lab)
    diff.append(stats["paired_diff_pct_by_setting"][f"{ax_}/{lv}"])
    is_nom.append((ax_, lv) in nominal)
    trk_r.append(rule["tracking_rmse_mps"])
    trk_a.append(act["tracking_rmse_mps"])
lo, hi = min(stats["nominal_replicates"]["paired_diff_pct"]), max(stats["nominal_replicates"]["paired_diff_pct"])

fig, axs = fs.figure("page", nrows=2, ncols=1, height=4.6)
x = np.arange(16)
a0, a1 = axs
a0.axhspan(lo, hi, color=fs.C[4], alpha=0.25, lw=0, zorder=0)
for i, d in enumerate(diff):
    kw = fs.bar(2) if is_nom[i] else fs.bar(0)
    a0.bar(i, d, width=0.65, **kw)
a0.axhline(0, color="black", lw=0.6)
a0.set_ylabel("Learned minus rules (%)")
a0.set_xticks(x); a0.set_xticklabels([])
a0.set_ylim(-0.6, 7.4)
for i, d in enumerate(diff):
    if d > 2:
        a0.text(i, d + 0.12, f"{d:+.2f}", ha="center", va="bottom", fontsize=8)
a0.text(0.9, 1.0, f"shaded band: range of the five\nnominal repeats ({lo:.2f} to {hi:.2f}%)",
        ha="left", va="bottom", fontsize=8)
handles = [mp.Patch(facecolor=fs.C[0], edgecolor="black", linewidth=0.4, label="Single condition"),
           mp.Patch(facecolor=fs.C[2], edgecolor="black", linewidth=0.4, hatch=fs.HATCHES[2],
                    label="Nominal US06 repeat")]
a0.legend(handles=handles, loc="upper left", ncol=1, bbox_to_anchor=(0.0, 0.88))
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

for ax_ in (a0, a1):
    ax_.axvline(1.5, color="#7a7a7a", lw=0.5, ls=":")
    ax_.axvline(0.5, color="#7a7a7a", lw=0.5, ls=":")
a0.text(0, 6.95, "UDDS", ha="center", fontsize=8)
a0.text(1, 6.95, "HWFET", ha="center", fontsize=8)
a0.text(8.5, 6.95, "US06 (14 settings)", ha="center", fontsize=8)
fs.save(fig, "fig-ems-campaign")
