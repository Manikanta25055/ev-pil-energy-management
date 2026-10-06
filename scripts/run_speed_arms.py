"""Stage 1 of the decision-model study, for the classical arms.

The question is whether a learned model is needed at all. Four ways of turning
a noisy speed measurement into the speed the loop controls on are run across
the noise scenarios of the design's section 7.1, and each is checked against
the criteria of section 7.3, which were written before this script was.

  B0   the loop as shipped (no filter)
  B1   a fixed first-order filter, alpha 0.30
  B2   a variance threshold picking the filter from a table
  B3   a Kalman filter with a fixed noise assumption
  B3a  the same filter with the noise measured from the speed jitter

Nothing is chosen on the test cycle. `--tune` picks B2's table and the Kalman
settings on the first 600 s of UDDS, a training cycle, with a seed the
evaluation never uses, and writes them to a file the evaluation reads.

SIMULATED on the laptop. No board is involved.

    PYTHONPATH="src:." python3 scripts/run_speed_arms.py --tune
    PYTHONPATH="src:." python3 scripts/run_speed_arms.py
"""

from __future__ import annotations

import argparse
import json
import math
import time
from dataclasses import replace
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from evpil.control.cycles import Cycle, load_cycle
from evpil.control.rule_ems import RuleParams, rule_action
from evpil.control.sim import simulate
from evpil.control.speed_estimators import (
    FixedFilter, KalmanSpeed, PassThrough, RegimeTable, VarianceThreshold,
)
from scripts.identify_params import params_from_json

PARAMS = "data/i3_params.json"
FLOOR = 0.02                    # NOISE_SIGMA["v_mps"] in evpil.control.scenarios
TUNE_SEED = 100
TUNE_STEPS = 60000              # first 600 s of UDDS
ALPHAS = (1.0, 0.3, 0.1)
RMSE_LIMIT = 0.1                # section 7.3: tracking under 0.1 m/s under noise

# Section 7.1. (name, cycle, speed noise in multiples of the floor or a
# schedule, plant mass factor, grade offset in rad)
SCENARIOS = (
    ("clean-udds",   "udds",  1.0,    1.0, 0.0),
    ("clean-hwfet",  "hwfet", 1.0,    1.0, 0.0),
    ("clean-us06",   "us06",  1.0,    1.0, 0.0),
    ("noise-3x",     "us06",  3.0,    1.0, 0.0),
    ("noise-10x",    "us06",  10.0,   1.0, 0.0),
    ("noise-25x",    "us06",  25.0,   1.0, 0.0),
    ("noise-step",   "us06",  "step", 1.0, 0.0),
    ("mass-clean",   "us06",  1.0,    1.1, 0.0),
    ("mass-10x",     "us06",  10.0,   1.1, 0.0),
    ("grade-clean",  "us06",  1.0,    1.0, 0.03),
    ("grade-10x",    "us06",  10.0,   1.0, 0.03),
)
STEP_ON_S, STEP_OFF_S = 200.0, 400.0     # floor, then 10x, then floor again
ARMS = ("B0", "B1", "B2", "B3", "B3a")
SEEDS = (0, 1, 2, 3, 4)


def make_estimator(arm: str, params, tuned: dict):
    if arm == "B0":
        return PassThrough()
    if arm == "B1":
        return FixedFilter(0.3)
    if arm == "B2":
        return VarianceThreshold(RegimeTable(
            alphas=tuple(tuned["b2"]["alphas"]),
            bounds_mps=tuple(tuned["b2"]["bounds_mps"])))
    if arm == "B3":
        return KalmanSpeed(params, q_mps=tuned["b3"]["q_mps"],
                           r_mps=tuned["b3"]["r_mps"])
    if arm == "B3a":
        return KalmanSpeed(params, q_mps=tuned["b3a"]["q_mps"],
                           r_mps=FLOOR, adaptive=True)
    if arm.startswith("alpha="):
        return FixedFilter(float(arm.split("=")[1]))
    if arm.startswith("kf:"):                      # kf:q:r or kf:q:adaptive
        _, q, r = arm.split(":")
        if r == "adaptive":
            return KalmanSpeed(params, q_mps=float(q), r_mps=FLOOR,
                               adaptive=True)
        return KalmanSpeed(params, q_mps=float(q), r_mps=float(r))
    raise ValueError(arm)


def run_cell(job: dict) -> dict:
    """One simulation. Top-level so a worker process can be handed it."""
    nominal = params_from_json(PARAMS)
    plant = replace(nominal, mass_kg=nominal.mass_kg * job["mass"])
    cycle = load_cycle(job["cycle"])
    if job.get("steps"):
        n = job["steps"]
        cycle = Cycle(name=cycle.name, dt_s=cycle.dt_s,
                      v_ref_mps=cycle.v_ref_mps[:n],
                      grade_rad=cycle.grade_rad[:n])
    if job["grade"]:
        cycle = replace(cycle, grade_rad=cycle.grade_rad + job["grade"])
    n = len(cycle.v_ref_mps)

    if job["noise"] == "step":
        t = np.arange(n) * cycle.dt_s
        noise = np.where((t >= STEP_ON_S) & (t < STEP_OFF_S),
                         10.0 * FLOOR, FLOOR)
    else:
        noise = float(job["noise"]) * FLOOR

    rules = RuleParams()
    est = make_estimator(job["arm"], nominal, job.get("tuned") or {})
    r = simulate(
        plant, cycle,
        lambda o: rule_action(rules, soc_frac=o.soc_frac, v_mps=o.v_mps),
        ff_params=nominal, speed_noise_mps=noise, seed=job["seed"],
        speed_estimator=est, keep_trace=True)

    tq = r.trace.torque_nm
    flips = int(np.sum(tq[1:] * tq[:-1] < 0.0))
    out = {k: job[k] for k in ("scenario", "cycle", "arm", "seed", "noise",
                               "mass", "grade")}
    out.update({
        "equivalent_wh_per_km": r.equivalent_wh_per_km,
        "distance_km": r.distance_km,
        "tracking_rmse_mps": r.tracking_rmse_mps,
        "tracking_max_mps": r.tracking_max_mps,
        "peak_current_a": r.peak_current_a,
        "torque_flips_per_km": flips / r.distance_km,
    })
    if isinstance(est, VarianceThreshold):
        h = np.array(est.regime_history)
        out["regime_share"] = [float(np.mean(h == k)) for k in range(3)]
        if job["noise"] == "step":
            on, off = int(STEP_ON_S * 10), int(STEP_OFF_S * 10)
            up = np.nonzero(h[on:off] == 2)[0]
            dn = np.nonzero(h[off:] == 0)[0]
            out["switch_up_s"] = float(up[0]) * 0.1 if len(up) else None
            out["switch_down_s"] = float(dn[0]) * 0.1 if len(dn) else None
    return out


def run_all(jobs: list[dict], workers: int) -> list[dict]:
    t0 = time.time()
    done: list[dict] = []
    with Pool(workers) as pool:
        for k, res in enumerate(pool.imap_unordered(run_cell, jobs), 1):
            done.append(res)
            if k % 10 == 0 or k == len(jobs):
                print(f"  {k}/{len(jobs)}  {time.time() - t0:5.0f} s", flush=True)
    return done


# --------------------------------------------------------------------------
# tuning, on a training cycle
# --------------------------------------------------------------------------

def tune(workers: int, out_path: Path) -> None:
    base = dict(cycle="udds", steps=TUNE_STEPS, seed=TUNE_SEED, grade=0.0,
                scenario="tune")
    levels = (0.0, 1.0, 2.0, 3.0, 5.0, 7.5, 10.0, 15.0, 25.0)
    jobs = [dict(base, arm=f"alpha={a}", noise=m, mass=1.0)
            for m in levels for a in ALPHAS]
    qs = (0.0005, 0.002, 0.008)
    rs = (0.02, 0.06, 0.2)
    kf_levels = (1.0, 10.0, 25.0)
    for q in qs:
        for r in rs + ("adaptive",):
            for m in kf_levels:
                jobs.append(dict(base, arm=f"kf:{q}:{r}", noise=m, mass=1.0))
            jobs.append(dict(base, arm=f"kf:{q}:{r}", noise=1.0, mass=1.1))
    print(f"tuning: {len(jobs)} runs on the first "
          f"{TUNE_STEPS // 100} s of UDDS, seed {TUNE_SEED}")
    res = run_all(jobs, workers)

    def get(arm, noise, mass=1.0):
        return next(r for r in res if r["arm"] == arm and r["noise"] == noise
                    and r["mass"] == mass)

    # B2: the best alpha at each level, lowest energy among those that track.
    best = []
    for m in levels:
        cands = [(get(f"alpha={a}", m), a) for a in ALPHAS]
        ok = [(r["equivalent_wh_per_km"], a) for r, a in cands
              if r["tracking_rmse_mps"] < RMSE_LIMIT]
        # A filter has to earn its place: it is taken over a lighter one only
        # if it saves more than 0.05% of energy, so that at low noise the
        # choice is not made on rounding.
        ok.sort(key=lambda x: -x[1])
        pick = ok[0]
        for e, a in ok[1:]:
            if e < pick[0] * (1 - 5e-4):
                pick = (e, a)
        best.append(pick[1])
        print(f"  noise {m:5.1f}x  " + "  ".join(
            f"a={a}: {r['equivalent_wh_per_km']:.2f}/{r['tracking_rmse_mps']:.3f}"
            for r, a in cands) + f"   -> {pick[1]}")
    alphas, bounds = [best[0]], []
    for (m0, a0), (m1, a1) in zip(zip(levels, best), zip(levels[1:], best[1:])):
        if a1 != a0:
            lo = max(m0, 0.5) * FLOOR
            bounds.append(math.sqrt(lo * m1 * FLOOR))
            alphas.append(a1)
    if sorted(alphas, reverse=True) != alphas:
        raise SystemExit(f"best alpha is not monotone in noise: {best}")

    # Kalman: must hold clean tracking, nominal and heavy; then least energy
    # summed over the noise levels.
    b0_clean = get("alpha=1.0", 1.0)
    limit = b0_clean["tracking_rmse_mps"] + 0.005

    def score(q, r):
        arm = f"kf:{q}:{r}"
        clean, heavy = get(arm, 1.0), get(arm, 1.0, 1.1)
        feasible = (clean["tracking_rmse_mps"] <= limit
                    and heavy["tracking_rmse_mps"] <= RMSE_LIMIT)
        total = sum(get(arm, m)["equivalent_wh_per_km"] for m in kf_levels)
        print(f"  {arm:22s} clean rmse {clean['tracking_rmse_mps']:.4f}  "
              f"heavy rmse {heavy['tracking_rmse_mps']:.4f}  "
              f"energy sum {total:.2f}  {'ok' if feasible else 'no'}")
        return feasible, total

    fixed = [(score(q, r), q, r) for q in qs for r in rs]
    adapt = [(score(q, "adaptive"), q) for q in qs]
    fixed_ok = [(s[1], q, r) for s, q, r in fixed if s[0]] or \
               [(s[1], q, r) for s, q, r in fixed]
    adapt_ok = [(s[1], q) for s, q in adapt if s[0]] or \
               [(s[1], q) for s, q in adapt]
    _, q3, r3 = min(fixed_ok)
    _, q3a = min(adapt_ok)

    tuned = {
        "tuned_on": f"udds, first {TUNE_STEPS // 100} s, seed {TUNE_SEED}",
        "b2": {"alphas": alphas, "bounds_mps": bounds,
               "best_alpha_by_level": dict(zip(map(str, levels), best))},
        "b3": {"q_mps": q3, "r_mps": r3,
               "feasible": any(s[0] for s, _, _ in fixed)},
        "b3a": {"q_mps": q3a, "feasible": any(s[0] for s, _ in adapt)},
        "runs": res,
    }
    out_path.write_text(json.dumps(tuned, indent=1))
    print(f"B2 table: alphas {alphas}, bounds {[round(b, 4) for b in bounds]} m/s")
    print(f"B3: q {q3}, r {r3}.  B3a: q {q3a}.")
    print(f"wrote {out_path}")


# --------------------------------------------------------------------------
# evaluation
# --------------------------------------------------------------------------

def mean_sd(xs):
    a = np.asarray(xs, dtype=float)
    return float(a.mean()), float(a.std(ddof=1)) if len(a) > 1 else 0.0


def boot_ci(diffs, n=10000, seed=0):
    rng = np.random.default_rng(seed)
    a = np.asarray(diffs, dtype=float)
    d = rng.choice(a, size=(n, len(a)), replace=True).mean(axis=1)
    return float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))


def evaluate(workers: int, tuned_path: Path, out_path: Path) -> None:
    tuned = json.loads(tuned_path.read_text())
    tuned_small = {k: tuned[k] for k in ("b2", "b3", "b3a")}
    jobs = [dict(scenario=s, cycle=c, noise=nz, mass=m, grade=g, arm=arm,
                 seed=seed, tuned=tuned_small)
            for s, c, nz, m, g in SCENARIOS for arm in ARMS for seed in SEEDS]
    print(f"stage 1: {len(jobs)} runs")
    res = run_all(jobs, workers)

    cell: dict[tuple, list[dict]] = {}
    for r in res:
        cell.setdefault((r["scenario"], r["arm"]), []).append(r)
    for v in cell.values():
        v.sort(key=lambda r: r["seed"])

    def stat(s, arm, key):
        return mean_sd([r[key] for r in cell[(s, arm)]])

    summary = []
    for s, *_ in SCENARIOS:
        for arm in ARMS:
            e, e_sd = stat(s, arm, "equivalent_wh_per_km")
            t, t_sd = stat(s, arm, "tracking_rmse_mps")
            d = [a["equivalent_wh_per_km"] - b["equivalent_wh_per_km"]
                 for a, b in zip(cell[(s, arm)], cell[(s, "B0")])]
            summary.append({
                "scenario": s, "arm": arm,
                "wh_per_km": e, "wh_per_km_sd": e_sd,
                "rmse_mps": t, "rmse_mps_sd": t_sd,
                "max_err_mps": stat(s, arm, "tracking_max_mps")[0],
                "peak_current_a": stat(s, arm, "peak_current_a")[0],
                "torque_flips_per_km": stat(s, arm, "torque_flips_per_km")[0],
                "vs_b0_wh_per_km": float(np.mean(d)),
                "vs_b0_ci95": boot_ci(d) if arm != "B0" else (0.0, 0.0),
            })
    by = {(r["scenario"], r["arm"]): r for r in summary}

    dp = {r["cycle"]: r["equivalent_wh_per_km"]
          for r in json.loads(Path("docs/week7-control-baselines.json")
                              .read_text())["rows"]
          if r["arm"] == "dp-comfort-priced"}

    clean = ("clean-udds", "clean-hwfet", "clean-us06")
    noisy = ("noise-3x", "noise-10x", "noise-25x", "noise-step")
    verdicts = {}
    for arm in ARMS[1:]:
        c = {}
        c["clean energy within 0.2% of B0"] = all(
            abs(by[(s, arm)]["wh_per_km"] / by[(s, "B0")]["wh_per_km"] - 1)
            <= 0.002 for s in clean)
        c["clean tracking within 0.005 m/s of B0"] = all(
            by[(s, arm)]["rmse_mps"] <= by[(s, "B0")]["rmse_mps"] + 0.005
            for s in clean)
        base = by[("clean-us06", "B0")]["wh_per_km"]
        for s, need in (("noise-10x", 0.5), ("noise-25x", 0.8)):
            pen0 = by[(s, "B0")]["wh_per_km"] - base
            rec = (by[(s, "B0")]["wh_per_km"] - by[(s, arm)]["wh_per_km"]) / pen0
            c[f"{s}: recovers {need:.0%} of the penalty"] = bool(rec >= need)
            c[f"{s}: recovered fraction"] = float(rec)
        c["tracking under 0.1 m/s in every noise scenario"] = all(
            by[(s, arm)]["rmse_mps"] < RMSE_LIMIT for s in noisy)
        if arm == "B2":
            ups = [r["switch_up_s"] for r in cell[("noise-step", arm)]]
            dns = [r["switch_down_s"] for r in cell[("noise-step", arm)]]
            c["regime switch, worst seed, up / down, s"] = (
                max(u if u is not None else 1e9 for u in ups),
                max(d if d is not None else 1e9 for d in dns))
            c["regime correct within 1 s of a change"] = bool(
                all(u is not None and u <= 1.0 for u in ups)
                and all(d is not None and d <= 1.0 for d in dns))
        # The week-10 guard. Nominal vehicle only: a heavier car or a hill has
        # a different optimum and this one does not apply to it.
        c["no run below the DP optimum at equal tracking"] = not any(
            r["equivalent_wh_per_km"] < dp[r["cycle"]] * (1 - 5e-4)
            and r["tracking_rmse_mps"]
            <= by[(r["scenario"], "B0")]["rmse_mps"] + 0.005
            for (s, a), rows in cell.items()
            if a == arm and s in clean + noisy for r in rows)
        gates = [v for k, v in c.items() if isinstance(v, bool)]
        c["meets every criterion it can be tested on"] = all(gates)
        verdicts[arm] = c

    out = {
        "provenance": "SIMULATED on the laptop; no board involved",
        "floor_mps": FLOOR, "seeds": list(SEEDS), "arms": list(ARMS),
        "scenarios": [dict(zip(("name", "cycle", "noise", "mass", "grade"), s))
                      for s in SCENARIOS],
        "tuned": tuned_small, "tuned_on": tuned["tuned_on"],
        "dp_optimum_wh_per_km": dp,
        "summary": summary, "verdicts": verdicts, "runs": res,
    }
    out_path.write_text(json.dumps(out, indent=1))

    print(f"\n{'scenario':13s}" + "".join(f"{a:>22s}" for a in ARMS))
    for s, *_ in SCENARIOS:
        print(f"{s:13s}" + "".join(
            f"{by[(s, a)]['wh_per_km']:13.2f} /{by[(s, a)]['rmse_mps']:7.4f}"
            for a in ARMS))
    print("  (energy Wh/km / tracking RMSE m/s, mean of five seeds)\n")
    for arm, c in verdicts.items():
        print(arm)
        for k, v in c.items():
            print(f"   {k}: {v}")
    print(f"wrote {out_path}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tune", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--tuned", default="docs/week11-speed-arms-tuned.json")
    ap.add_argument("--out-json", default="docs/week11-speed-arms.json")
    args = ap.parse_args()
    if args.tune:
        tune(args.workers, Path(args.tuned))
    else:
        evaluate(args.workers, Path(args.tuned), Path(args.out_json))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
