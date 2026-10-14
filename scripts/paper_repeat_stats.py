"""Measurement-round item B2: the corrected campaign with three noise seeds.

The corrected campaign (docs/week11-pil-corrected.json, seed offset 0) ran each
setting once. B2 ran the 12 distinct conditions again with noise seed offsets
100 and 200 (docs/2026-10-14-pil-repeats-{rule,actor}-s{100,200}.json). For
each condition the learned-minus-rule energy difference (comparable scale) is
taken per seed and averaged over the three seeds. The decision rule, fixed in
docs/2026-10-14-measurement-plan.md before the runs: the verdict "the learned
policy used more energy" stands if the exact two-sided Wilcoxon signed-rank
test over the 12 seed-averaged conditions gives p < 0.05 with a positive
median. The nominal US06 condition uses its driving-condition cell, the one B2
repeated. MEASURED.

    python3 scripts/paper_repeat_stats.py
"""
import json
import math
import random
import statistics as st
from itertools import product
from pathlib import Path

OUT = Path("docs/2026-10-14-pil-repeats-stats.json")
CELLS = [("driving_condition", "urban"), ("driving_condition", "highway"),
         ("driving_condition", "aggressive_mixed"), ("road_grade", "uphill"),
         ("road_grade", "downhill"), ("battery_state", "high"),
         ("battery_state", "medium"), ("battery_state", "low"),
         ("sensor_noise", "elevated"), ("sensor_noise", "severe"),
         ("driver_aggression", "brisk"), ("driver_aggression", "aggressive")]


def load(path):
    return {(r["scenario"], r["level"]): r for r in json.loads(Path(path).read_text())["runs"]}


def wilcoxon_exact(x):
    n = len(x)
    order = sorted(range(n), key=lambda i: abs(x[i]))
    w_minus = sum(r + 1 for r, i in enumerate(order) if x[i] < 0)
    hits = sum(sum(r + 1 for r, b in enumerate(s) if b) <= w_minus
               for s in product((0, 1), repeat=n))
    return w_minus, min(1.0, 2 * hits / 2 ** n)


def main():
    orig = json.loads(Path("docs/week11-pil-corrected.json").read_text())["runs"]
    rule0 = {(r["scenario"], r["level"]): r for r in orig if r["controller"] == "rule"}
    act0 = {(r["scenario"], r["level"]): r for r in orig if r["controller"] == "actor"}
    seeds = {0: (rule0, act0)}
    for off in (100, 200):
        seeds[off] = (load(f"docs/2026-10-14-pil-repeats-rule-s{off}.json"),
                      load(f"docs/2026-10-14-pil-repeats-actor-s{off}.json"))
    e = lambda r: r["equivalent_wh_per_km"]
    rows = []
    for cell in CELLS:
        per = []
        for off, (rule, act) in seeds.items():
            rr, aa = rule[cell], act[cell]
            assert rr["seed"] == aa["seed"], (cell, off)
            per.append({"seed": rr["seed"], "rule_wh_per_km": e(rr), "learned_wh_per_km": e(aa),
                        "diff_pct": 100 * (e(aa) / e(rr) - 1),
                        "rule_rmse_mps": rr["tracking_rmse_mps"],
                        "learned_rmse_mps": aa["tracking_rmse_mps"]})
        d = [p["diff_pct"] for p in per]
        rule_e = [p["rule_wh_per_km"] for p in per]
        rows.append({"cell": "/".join(cell), "runs": per,
                     "mean_diff_pct": st.mean(d), "min_diff_pct": min(d), "max_diff_pct": max(d),
                     "learned_higher_in_seeds": sum(x > 0 for x in d),
                     "rule_seed_range_pct": 100 * (max(rule_e) - min(rule_e)) / min(rule_e)})
    m = [r["mean_diff_pct"] for r in rows]
    w_minus, p = wilcoxon_exact(m)
    random.seed(1)
    bmed = sorted(st.median(random.choices(m, k=len(m))) for _ in range(20000))
    bmean = sorted(st.mean(random.choices(m, k=len(m))) for _ in range(20000))
    all_d = [x["diff_pct"] for r in rows for x in r["runs"]]
    out = {
        "provenance": "MEASURED on the ESP32-S3; seed offsets 0 (corrected campaign), 100, 200; plan item B2",
        "rows": rows,
        "conditions": len(m),
        "conditions_learned_higher_on_average": sum(x > 0 for x in m),
        "median_of_condition_means_pct": st.median(m),
        "mean_of_condition_means_pct": st.mean(m),
        "bootstrap95_median_pct": [bmed[500], bmed[19499]],
        "bootstrap95_mean_pct": [bmean[500], bmean[19499]],
        "wilcoxon_exact": {"w_minus": w_minus, "p_two_sided": p},
        "runs_learned_higher": f"{sum(x > 0 for x in all_d)} of {len(all_d)}",
        "verdict_rule": "learned uses more energy if p < 0.05 and median > 0",
        "verdict_stands": p < 0.05 and st.median(m) > 0,
    }
    OUT.write_text(json.dumps(out, indent=1) + "\n")
    for r in rows:
        print(f"{r['cell']:34s} " + "  ".join(f"{x['diff_pct']:+.2f}" for x in r["runs"])
              + f"   mean {r['mean_diff_pct']:+.2f}   rule spread {r['rule_seed_range_pct']:.2f}%")
    print({k: v for k, v in out.items() if k != "rows"})


if __name__ == "__main__":
    main()
