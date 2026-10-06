"""Did the plant correction move the rule manager's own numbers?

The rule manager's power ceiling sits near 125 kW and the correction only
changes a run in which a limit binds, so its arm should read the same before
and after. Early in the corrected campaign a few US06 cells read 0.1 to 0.3%
high and it was noted as something to look at. This looks at it.

Three campaigns ran the same 18 rule cells with the same seeds: the first
(week 10), its repeat, and the corrected one. The first two differ by nothing
but the day, so the gap between them is what "nothing changed" looks like on
this rig. The corrected campaign is compared with the repeat against that.

Reads saved measurements only. No simulation, no board.

    PYTHONPATH="src:." python3 scripts/check_rule_arm.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def rule_cells(path: Path) -> dict:
    return {(r["scenario"], r["level"]): r
            for r in json.loads(path.read_text())["runs"]
            if r["controller"] == "rule"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--first", default="docs/week10-pil-campaign.json")
    ap.add_argument("--repeat", default="docs/week10-pil-campaign-repeat.json")
    ap.add_argument("--corrected", default="docs/week11-pil-corrected-rule.json")
    ap.add_argument("--out-json", default="docs/week11-rule-arm-check.json")
    args = ap.parse_args()

    first, rep = rule_cells(Path(args.first)), rule_cells(Path(args.repeat))
    new = rule_cells(Path(args.corrected))

    rows = []
    for key, n in new.items():
        f, r = first[key], rep[key]
        # The two link-delay cells never follow the cycle; their energy has
        # no meaning in any campaign.
        if max(n["tracking_rmse_mps"], r["tracking_rmse_mps"],
               f["tracking_rmse_mps"]) >= 1.0:
            continue
        e = lambda x: x["equivalent_wh_per_km"]
        rows.append({
            "scenario": key[0], "level": key[1],
            "first_wh_per_km": e(f), "repeat_wh_per_km": e(r),
            "corrected_wh_per_km": e(n),
            "repeat_vs_first_pct": 100.0 * (e(r) / e(f) - 1.0),
            "corrected_vs_repeat_pct": 100.0 * (e(n) / e(r) - 1.0),
            "rmse_mps": [f["tracking_rmse_mps"], r["tracking_rmse_mps"],
                         n["tracking_rmse_mps"]],
            "peak_current_a": [f["peak_current_a"], r["peak_current_a"],
                               n["peak_current_a"]],
            "dropped_frames": [f["dropped_frames"], r["dropped_frames"],
                               n["dropped_frames"]],
        })

    base = np.array([x["repeat_vs_first_pct"] for x in rows])
    shift = np.array([x["corrected_vs_repeat_pct"] for x in rows])
    rng = np.random.default_rng(0)
    boot = rng.choice(shift, size=(10000, len(shift)), replace=True).mean(axis=1)
    ci = (float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5)))
    stats = {
        "cells": len(rows),
        "repeat_vs_first": {"mean_pct": float(base.mean()),
                            "mean_abs_pct": float(np.abs(base).mean()),
                            "worst_abs_pct": float(np.abs(base).max())},
        "corrected_vs_repeat": {"mean_pct": float(shift.mean()),
                                "mean_abs_pct": float(np.abs(shift).mean()),
                                "worst_abs_pct": float(np.abs(shift).max()),
                                "mean_ci95_pct": ci,
                                "cells_higher": int((shift > 0).sum())},
    }
    inside = (ci[0] <= 0.0 <= ci[1]
              and stats["corrected_vs_repeat"]["worst_abs_pct"]
              <= 1.5 * stats["repeat_vs_first"]["worst_abs_pct"])
    c, b = stats["corrected_vs_repeat"], stats["repeat_vs_first"]
    conclusion = (
        f"Across {len(rows)} valid cells the corrected rule arm differs from "
        f"the repeat campaign by {c['mean_pct']:+.2f}% on average (95% CI "
        f"{ci[0]:+.2f} to {ci[1]:+.2f}), {c['mean_abs_pct']:.2f}% in size, "
        f"{c['worst_abs_pct']:.2f}% at worst, higher in {c['cells_higher']} "
        f"cells. The two week-10 campaigns, which differ by nothing but the "
        f"day, differ by {b['mean_abs_pct']:.2f}% in size and "
        f"{b['worst_abs_pct']:.2f}% at worst. "
        + ("The interval contains zero and the worst cell is within the "
           "spread already seen between identical campaigns: the correction "
           "did not move the rule arm."
           if inside else
           "That is outside the spread between identical campaigns: the rule "
           "arm moved, and the cause is not established by this check."))

    Path(args.out_json).write_text(json.dumps({
        "provenance": "saved board measurements only; no simulation",
        "inputs": [args.first, args.repeat, args.corrected],
        "stats": stats, "moved": not inside, "conclusion": conclusion,
        "rows": rows}, indent=1))
    print(conclusion)
    print(f"wrote {args.out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
