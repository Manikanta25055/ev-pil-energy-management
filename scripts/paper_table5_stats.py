"""Paired statistics for the corrected board campaign (paper Table 5).

Reads docs/week11-pil-corrected.json and writes docs/paper-table5-stats.json.
The 16 valid settings contain 5 runs of the nominal US06 condition, so the
paired test is run on 12 distinct conditions (the 5 replicates averaged).
"""
import json
import math
import random
import statistics as st
from itertools import product
from pathlib import Path

SRC = Path("docs/week11-pil-corrected.json")
OUT = Path("docs/paper-table5-stats.json")
NOMINAL = ("us06", 0.0, 0.8, 1.0, 1.0)


def nominal(r):
    return (r["cycle"], r["grade_offset_rad"], r["soc0"], r["noise_scale"], r["aggression"]) == NOMINAL


def main():
    runs = json.loads(SRC.read_text())["runs"]
    key = lambda r: (r["scenario"], r["level"])
    rule = {key(r): r for r in runs if r["controller"] == "rule"}
    actor = {key(r): r for r in runs if r["controller"] == "actor"}
    valid = [k for k in rule if rule[k]["comm_delay_s"] == 0]
    reps = [k for k in valid if nominal(rule[k])]
    e = lambda m, k: m[k]["equivalent_wh_per_km"]
    diff = {k: 100 * (e(actor, k) / e(rule, k) - 1) for k in valid}

    rep_diff = [diff[k] for k in reps]
    t975_4 = 2.7764451051977987  # Student t, 4 degrees of freedom
    half = t975_4 * st.stdev(rep_diff) / math.sqrt(len(rep_diff))
    cond = [diff[k] for k in valid if k not in reps] + [st.mean(rep_diff)]
    n = len(cond)
    pos = sum(x > 0 for x in cond)
    sign_p = min(1.0, 2 * sum(math.comb(n, i) for i in range(pos, n + 1)) / 2 ** n)
    order = sorted(range(n), key=lambda i: abs(cond[i]))
    w_minus = sum(r + 1 for r, i in enumerate(order) if cond[i] < 0)
    hits = sum(sum(r + 1 for r, b in enumerate(s) if b) <= w_minus for s in product((0, 1), repeat=n))
    wil_p = min(1.0, 2 * hits / 2 ** n)
    random.seed(1)
    bm, bmed = [], []
    for _ in range(20000):
        s = [random.choice(cond) for _ in cond]
        bm.append(st.mean(s))
        bmed.append(st.median(s))
    bm.sort()
    bmed.sort()
    rule_rep = [e(rule, k) for k in reps]
    actor_rep = [e(actor, k) for k in reps]
    drop_x = [actor[k]["dropped_frames"] - rule[k]["dropped_frames"] for k in valid]
    drop_y = [diff[k] for k in valid]
    mx, my = st.mean(drop_x), st.mean(drop_y)
    corr = sum((a - mx) * (b - my) for a, b in zip(drop_x, drop_y)) / math.sqrt(
        sum((a - mx) ** 2 for a in drop_x) * sum((b - my) ** 2 for b in drop_y))

    out = {
        "source": str(SRC),
        "valid_settings": len(valid),
        "nominal_us06_replicates": [list(k) for k in reps],
        "distinct_conditions": n,
        "settings_learned_lower": sum(x < 0 for x in diff.values()),
        "paired_diff_pct_by_setting": {f"{k[0]}/{k[1]}": round(diff[k], 3) for k in valid},
        "mean_diff_pct_16": round(st.mean(diff.values()), 3),
        "median_diff_pct_16": round(st.median(diff.values()), 3),
        "nominal_replicates": {
            "rule_wh_per_km": [round(x, 2) for x in rule_rep],
            "actor_wh_per_km": [round(x, 2) for x in actor_rep],
            "rule_range_pct": round(100 * (max(rule_rep) - min(rule_rep)) / min(rule_rep), 3),
            "actor_range_pct": round(100 * (max(actor_rep) - min(actor_rep)) / min(actor_rep), 3),
            "paired_diff_pct": [round(x, 3) for x in rep_diff],
            "paired_diff_mean_pct": round(st.mean(rep_diff), 3),
            "paired_diff_sd_pct": round(st.stdev(rep_diff), 3),
            "paired_diff_t95_pct": [round(st.mean(rep_diff) - half, 3), round(st.mean(rep_diff) + half, 3)],
        },
        "conditions_12": {
            "diff_pct_sorted": sorted(round(x, 3) for x in cond),
            "mean_pct": round(st.mean(cond), 3),
            "median_pct": round(st.median(cond), 3),
            "bootstrap95_mean_pct": [round(bm[500], 3), round(bm[19499], 3)],
            "bootstrap95_median_pct": [round(bmed[500], 3), round(bmed[19499], 3)],
            "bootstrap_resamples": 20000,
            "sign_test": {"positive": pos, "n": n, "p_two_sided": round(sign_p, 4)},
            "wilcoxon_exact": {"w_minus": w_minus, "p_two_sided": round(wil_p, 4)},
        },
        "dropped_frames_vs_energy_corr": round(corr, 3),
    }
    OUT.write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
