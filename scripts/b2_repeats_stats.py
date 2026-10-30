"""Measurement round B2: the twelve-condition paired test on three noise draws.

Plan: docs/2026-10-14-measurement-plan.md (B2) and
docs/2026-10-14-paper-validation-addendum-plan.md (Revision 4, section B).

The twelve conditions are the cells the board script ran
(.claude/night/round2_board.sh, B2_CELLS), selected by
scripts/run_pil_campaign.py::select_runs. Offset 0 is the corrected campaign
(docs/week11-pil-corrected.json); offsets 100 and 200 are the repeat files.
The nominal US06 condition is driving_condition/aggressive_mixed, seeds
2/102/202; the four other nominal rows of the corrected campaign stay in its
historical summary and are not used here.

For each condition and offset, d_pct = 100 * (actor / rule - 1) on
equivalent_wh_per_km; the three offsets are averaged per condition. The
registered verdict: an exact two-sided Wilcoxon signed-rank test over the 12
condition means gives p < 0.05 with a positive median -> the learned policy
used more energy; otherwise no measurable difference (not equivalence).

Writes docs/2026-10-14-b2-manifest.json and docs/2026-10-14-b2-wilcoxon.json.
"""
from __future__ import annotations

import json
import statistics as st
from itertools import product
from pathlib import Path

CELLS = ["driving_condition/urban", "driving_condition/highway",
         "driving_condition/aggressive_mixed", "road_grade/uphill",
         "road_grade/downhill", "battery_state/high", "battery_state/medium",
         "battery_state/low", "sensor_noise/elevated", "sensor_noise/severe",
         "driver_aggression/brisk", "driver_aggression/aggressive"]
OFFSETS = (0, 100, 200)
ORIGINAL = Path("docs/week11-pil-corrected.json")
REPEAT = "docs/2026-10-14-pil-repeats-{ctrl}-s{off}.json"
PHYSICAL = ("cycle", "grade_offset_rad", "soc0", "noise_scale",
            "comm_delay_s", "aggression")
DROP_LIMIT = 16
OUT_MANIFEST = Path("docs/2026-10-14-b2-manifest.json")
OUT_STATS = Path("docs/2026-10-14-b2-wilcoxon.json")
EPS = 1e-9


def average_ranks(values):
    """Ranks 1..n of `values`, ties sharing the mean of their positions."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and abs(values[order[j + 1]] - values[order[i]]) <= EPS:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return ranks


def wilcoxon_exact(d):
    """Exact two-sided signed-rank test. Zeros dropped, average ranks for
    tied magnitudes, T = min(W+, W-), p = share of the 2^n sign assignments
    of the nonzero ranks whose min(W+, W-) is at most T. All-zero gives 1."""
    nz = [x for x in d if x != 0.0]
    n = len(nz)
    if n == 0:
        return {"n_nonzero": 0, "w_plus": 0.0, "w_minus": 0.0, "T": 0.0, "p_two_sided": 1.0}
    r = average_ranks([abs(x) for x in nz])
    w_plus = sum(rk for rk, x in zip(r, nz) if x > 0)
    w_minus = sum(rk for rk, x in zip(r, nz) if x < 0)
    t = min(w_plus, w_minus)
    total = sum(r)
    hits = 0
    for signs in product((0, 1), repeat=n):
        wp = sum(rk for rk, s in zip(r, signs) if s)
        if min(wp, total - wp) <= t + EPS:
            hits += 1
    return {"n_nonzero": n, "w_plus": w_plus, "w_minus": w_minus, "T": t,
            "p_two_sided": min(1.0, hits / 2 ** n)}


def _runs(path, ctrl=None):
    runs = json.loads(Path(path).read_text())["runs"]
    return [r for r in runs if ctrl is None or r["controller"] == ctrl]


def _pick(runs, cell, seed):
    axis, level = cell.split("/")
    hit = [r for r in runs if r["scenario"] == axis and r["level"] == level and r["seed"] == seed]
    return hit


def build_manifest():
    from scripts.run_pil_campaign import select_runs

    base = {f"{r.axis}/{r.level}": r.seed
            for r in select_runs("rule", axes=None, cells=CELLS, seed_offset=0)}
    if sorted(base) != sorted(CELLS):
        raise SystemExit(f"select_runs does not give the twelve cells: {sorted(base)}")
    sources = {0: {c: _runs(ORIGINAL, c) for c in ("rule", "actor")}}
    for off in OFFSETS[1:]:
        sources[off] = {c: _runs(REPEAT.format(ctrl=c, off=off), c) if Path(REPEAT.format(ctrl=c, off=off)).exists() else []
                        for c in ("rule", "actor")}
    disturbed = {0: {"rule": [], "actor": []}}
    for off in OFFSETS[1:]:
        disturbed[off] = {}
        for c in ("rule", "actor"):
            side = Path(REPEAT.format(ctrl=c, off=off).replace(".json", "-disturbed.json"))
            disturbed[off][c] = _runs(side, c) if side.exists() else []
    rows, gaps, retakes = [], [], []
    for cell in CELLS:
        for off in OFFSETS:
            seed = base[cell] + off
            pair, problems = {}, []
            for ctrl in ("rule", "actor"):
                hit = _pick(sources[off][ctrl], cell, seed)
                if len(hit) != 1:
                    problems.append(f"{ctrl}: {len(hit)} accepted runs")
                    continue
                r = hit[0]
                # Board rule: a run over the limit is set aside and taken once
                # more; the retake stands whatever its count. Only a first take
                # over the limit (no set-aside record) is invalid.
                if r["dropped_frames"] > DROP_LIMIT and r["tracking_rmse_mps"] < 1.0:
                    if _pick(disturbed[off][ctrl], cell, seed):
                        retakes.append({"cell": cell, "offset": off, "controller": ctrl,
                                        "dropped_frames": r["dropped_frames"]})
                    else:
                        problems.append(f"{ctrl}: {r['dropped_frames']} dropped frames, not retaken")
                if (r["actor_steps"] > 0) != (ctrl == "actor"):
                    problems.append(f"{ctrl}: actor_steps {r['actor_steps']}")
                if r.get("speed_est_mode", 0) != 0:
                    problems.append(f"{ctrl}: speed_est_mode {r['speed_est_mode']}")
                pair[ctrl] = r
            if len(pair) == 2:
                for k in PHYSICAL:
                    if pair["rule"][k] != pair["actor"][k]:
                        problems.append(f"{k} differs: {pair['rule'][k]} vs {pair['actor'][k]}")
            row = {"cell": cell, "offset": off, "seed": seed,
                   "source": str(ORIGINAL) if off == 0 else REPEAT.format(ctrl="{rule,actor}", off=off),
                   "valid": not problems, "problems": problems}
            if len(pair) == 2:
                row.update({k: pair["rule"][k] for k in PHYSICAL})
                for ctrl in ("rule", "actor"):
                    r = pair[ctrl]
                    row[ctrl] = {k: r[k] for k in ("equivalent_wh_per_km", "tracking_rmse_mps",
                                                   "dropped_frames", "actor_steps", "ctrl_late",
                                                   "peak_current_a")}
                    row[ctrl]["speed_est_mode"] = r.get("speed_est_mode")
                row["d_pct"] = 100 * (pair["actor"]["equivalent_wh_per_km"]
                                      / pair["rule"]["equivalent_wh_per_km"] - 1)
            if problems:
                gaps.append(row)
            rows.append(row)
    return rows, gaps, retakes


def firmware_provenance():
    # Fixed at the build, not read from the checkout: an analysis re-run on a
    # later commit must not restamp the images. The firmware/ tree is the same
    # from 8a6dda7 to 0aee7a8, so its tree hash identifies the source.
    return {"repeat_images": [
                "17:26 b2-rule image flashed (-DSPEED_KALMAN=0 -DSPEED_FILTER_ALPHA=1.0f)",
                "22:28 b2-actor image flashed (-DSPEED_KALMAN=0 -DSPEED_FILTER_ALPHA=1.0f)"],
            "build_switches": "-DFAULT_INJECT=0 -DFALLBACK_ENABLED=1 -DSPEED_KALMAN=0 -DSPEED_FILTER_ALPHA=1.0f",
            "rule_image": "built without firmware/main/sac_actor_weights.h",
            "actor_image": "built with the committed firmware/main/sac_actor_weights.h",
            "image_sha256": {
                "rule": "a0da796f4bf9d44bbf1d2bee7eb8a63aa5929f7936e6360df53169fd8e9e2007",
                "actor": "0ee13d54986a84528cecd3e66d8cadbfbe4ef32e6f876d4ef222fcc97ffd1520"},
            "offset_0": "corrected campaign as recorded in docs/week11-pil-corrected.json",
            "head": "0aee7a8efbc5517b0d12ace67b5ed1bd075fe178",
            "firmware_tree": "af1f5fc42d6c6ac9ec0c82304d0deafa8a79815e"}


def main() -> int:
    rows, gaps, retakes = build_manifest()
    OUT_MANIFEST.write_text(json.dumps({
        "plan": "docs/2026-10-14-measurement-plan.md B2; docs/2026-10-14-paper-validation-addendum-plan.md Rev 4",
        "cells": CELLS, "offsets": list(OFFSETS), "nominal_cell": "driving_condition/aggressive_mixed",
        "firmware": firmware_provenance(), "pairs": rows, "gaps": gaps,
        "retakes_over_limit": retakes}, indent=1) + "\n")
    if gaps:
        print(f"{len(gaps)} invalid or missing pairs; the twelve-condition verdict is withheld")
        for g in gaps:
            print(" ", g["cell"], g["offset"], g["problems"])
        OUT_STATS.write_text(json.dumps({"verdict": "withheld", "gaps": len(gaps)}, indent=1) + "\n")
        return 1
    cond = {c: st.mean(r["d_pct"] for r in rows if r["cell"] == c) for c in CELLS}
    vals = [cond[c] for c in CELLS]
    w = wilcoxon_exact(vals)
    med = st.median(vals)
    more = w["p_two_sided"] < 0.05 and med > 0
    by_off = {off: [r["d_pct"] for r in rows if r["offset"] == off] for off in OFFSETS}
    out = {
        "source_manifest": str(OUT_MANIFEST),
        "condition_mean_d_pct": cond,
        "n_conditions": len(vals),
        "positive_conditions": sum(x > 0 for x in vals),
        "median_d_pct": med, "mean_d_pct": st.mean(vals),
        "wilcoxon_exact": w,
        "verdict": "learned policy used more energy" if more else "no measurable difference",
        "verdict_rule": "two-sided exact Wilcoxon p < 0.05 and positive median -> learned used more; otherwise no measurable difference (not equivalence)",
        "per_offset": {str(off): {"median_d_pct": st.median(v), "mean_d_pct": st.mean(v),
                                  "positive": sum(x > 0 for x in v), "wilcoxon_exact": wilcoxon_exact(v)}
                       for off, v in by_off.items()},
        "per_pair_d_pct_range": [min(r["d_pct"] for r in rows), max(r["d_pct"] for r in rows)],
        "condition_spread_d_pct": {c: [min(r["d_pct"] for r in rows if r["cell"] == c),
                                       max(r["d_pct"] for r in rows if r["cell"] == c)] for c in CELLS},
        "tracking_rmse_mps_mean": {ctrl: {c: st.mean(r[ctrl]["tracking_rmse_mps"] for r in rows if r["cell"] == c)
                                          for c in CELLS} for ctrl in ("rule", "actor")},
        "note": "fixed scenario panel; seeds replay only the noise draw; not a fleet-population result",
    }
    OUT_STATS.write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({k: out[k] for k in ("positive_conditions", "median_d_pct", "mean_d_pct",
                                          "wilcoxon_exact", "verdict")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
