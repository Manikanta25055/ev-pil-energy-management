"""Week 8: SAC over five seeds, and ablation A3.

Spec 6.2 requires five seeds reported as a mean with a confidence interval,
because a single reinforcement-learning result is not publishable. Spec 6.3's
ablation A3 asks whether the controller needs the forecast in its state, and
runs both arms through the identical training and evaluation path so the only
difference between them is two observation channels.

Week 7's dynamic program already says what this should find: with the speed
trajectory fixed by the tracking constraint, the optimal policy is a constant
and a preview cannot help. That prediction is written down before the run
rather than after it, and this script is the measurement that confirms or
refutes it. It is run either way -- a null A3 was pre-accepted in spec 3.2,
and a predicted null still has to be measured before it can be reported.

Three things this script refuses to do:

  * report raw consumption alone. An arm that sheds cabin heat shows a lower
    number without having managed any energy, so every arm is also reported on
    the comparable scale that charges shed load back at what it saved;
  * evaluate on the sealed test cycle. US06 stays untouched until the final
    campaign; tuning happens on HWFET;
  * report accuracy without cost. The actor's footprint and MAC count are
    printed at the moment it is trained, which is why the network is 64 wide
    and not the library default.

    PYTHONPATH="src:." python3 scripts/run_sac.py
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

from evpil.forecast import _openmp        # noqa: F401  (import-order guard)

from evpil.control.actor import Actor, from_sb3, summarise
from evpil.control.cycles import CONTROL_SPLIT, load_cycle
from evpil.control.env import EnergyManagementEnv, RewardWeights
from evpil.control.rule_ems import RuleParams, rule_action
from evpil.control.sac_policy import actor_policy
from evpil.control.sim import Result, simulate
from scripts.identify_params import params_from_json

# 64 wide, not the library's 256. The default costs 269 KB in float32, which
# is 90% of the entire G5 memory budget that the forecaster also has to fit
# inside. Measured in the pilot: 68,867 parameters against 4,931.
NET_ARCH = [64, 64]


def evaluate(actor: Actor, params, cycle, *, use_forecast: bool,
             soc0: float, t_ambient_c: float) -> Result:
    return simulate(params, cycle,
                    actor_policy(actor, cycle, params,
                                 use_forecast=use_forecast),
                    soc0=soc0, t_ambient_c=t_ambient_c)


def bootstrap_ci(values: list[float], n: int = 10000, seed: int = 0
                 ) -> tuple[float, float]:
    """Percentile bootstrap on five points. Wide on purpose: five seeds is
    five seeds, and a narrow interval drawn from them would be a fiction."""
    rng = np.random.default_rng(seed)
    arr = np.asarray(values, dtype=float)
    draws = rng.choice(arr, size=(n, len(arr)), replace=True).mean(axis=1)
    return float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--params", default="data/i3_params.json")
    ap.add_argument("--steps", type=int, default=200000)
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--episode-steps", type=int, default=300)
    ap.add_argument("--eval-every", type=int, default=25000)
    ap.add_argument("--soc0", type=float, default=0.80)
    ap.add_argument("--t-ambient", type=float, default=12.0)
    ap.add_argument("--out-json", default="docs/week8-sac.json")
    ap.add_argument("--out-csv", default="docs/week8-sac.csv")
    ap.add_argument("--actor-dir", default="data/actors")
    args = ap.parse_args()

    from stable_baselines3 import SAC

    params = params_from_json(args.params)
    train = [load_cycle(c) for c in CONTROL_SPLIT["train"]]
    val = load_cycle(CONTROL_SPLIT["val"][0])
    print(f"train {[c.name for c in train]}, validate {val.name}, "
          f"test sealed ({CONTROL_SPLIT['test'][0]})")

    rules = RuleParams()
    baseline = simulate(params, val,
                        lambda o: rule_action(rules, soc_frac=o.soc_frac,
                                              v_mps=o.v_mps),
                        soc0=args.soc0, t_ambient_c=args.t_ambient)
    print(f"rule-based baseline on {val.name}: "
          f"{baseline.wh_per_km:.2f} Wh/km raw, "
          f"{baseline.equivalent_wh_per_km:.2f} comparable\n")

    actor_dir = Path(args.actor_dir)
    actor_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    curves: dict[str, list] = {}
    cost_reported = False

    for arm, use_forecast in (("with-forecast", True),
                              ("without-forecast", False)):
        print(f"--- A3 arm: {arm} ---")
        for seed in range(args.seeds):
            env = EnergyManagementEnv(
                params, train, weights=RewardWeights(),
                episode_steps=args.episode_steps,
                use_forecast=use_forecast, seed=seed,
            )
            model = SAC("MlpPolicy", env, seed=seed, verbose=0,
                        learning_starts=1000,
                        policy_kwargs=dict(net_arch=NET_ARCH))

            curve = []
            t0 = time.time()
            done = 0
            while done < args.steps:
                chunk = min(args.eval_every, args.steps - done)
                model.learn(total_timesteps=chunk, reset_num_timesteps=False,
                            progress_bar=False)
                done += chunk
                r = evaluate(from_sb3(model), params, val,
                             use_forecast=use_forecast, soc0=args.soc0,
                             t_ambient_c=args.t_ambient)
                curve.append({"steps": done,
                              "equivalent_wh_per_km": r.equivalent_wh_per_km,
                              "wh_per_km": r.wh_per_km})
            wall = time.time() - t0

            actor = from_sb3(model)
            actor.save(actor_dir / f"sac-{arm}-seed{seed}.npz")
            if not cost_reported:
                print("  " + summarise(actor))
                cost_reported = True

            r = evaluate(actor, params, val, use_forecast=use_forecast,
                         soc0=args.soc0, t_ambient_c=args.t_ambient)
            rows.append({
                "arm": arm, "seed": seed, "cycle": val.name,
                "steps": args.steps, "wall_s": wall,
                **{k: v for k, v in r.summary().items() if k != "cycle"},
                "gap_to_rule_pct": 100.0 * (r.equivalent_wh - baseline.equivalent_wh)
                                   / baseline.equivalent_wh,
            })
            curves[f"{arm}-seed{seed}"] = curve
            print(f"  seed {seed}: {r.wh_per_km:7.2f} Wh/km raw, "
                  f"{r.equivalent_wh_per_km:7.2f} comparable, "
                  f"shed {r.aux_shed_wh:6.1f} Wh, "
                  f"tracking {r.tracking_rmse_mps:.5f} m/s, "
                  f"{wall / 60:.1f} min")

    # --- summary ---------------------------------------------------------
    print("\narm                 comparable Wh/km      vs rule      shed Wh")
    summary = {}
    for arm in ("with-forecast", "without-forecast"):
        vals = [r["equivalent_wh_per_km"] for r in rows if r["arm"] == arm]
        gaps = [r["gap_to_rule_pct"] for r in rows if r["arm"] == arm]
        shed = [r["aux_shed_wh"] for r in rows if r["arm"] == arm]
        lo, hi = bootstrap_ci(vals)
        summary[arm] = {
            "mean": float(np.mean(vals)), "std": float(np.std(vals, ddof=1)),
            "ci95": [lo, hi], "per_seed": vals,
            "gap_to_rule_pct_mean": float(np.mean(gaps)),
            "aux_shed_wh_mean": float(np.mean(shed)),
        }
        print(f"  {arm:18} {np.mean(vals):7.2f} +- {np.std(vals, ddof=1):5.2f}"
              f"  [{lo:.2f}, {hi:.2f}]   {np.mean(gaps):+6.2f}%   "
              f"{np.mean(shed):6.1f}")
    print(f"  {'rule-based':18} {baseline.equivalent_wh_per_km:7.2f}"
          f"                        {0.0:+6.2f}%   "
          f"{baseline.aux_shed_wh:6.1f}")

    # A3: the difference between the arms, with a paired interval. Seeds are
    # paired because arm and seed share an initialisation and a cycle order.
    with_v = summary["with-forecast"]["per_seed"]
    without_v = summary["without-forecast"]["per_seed"]
    diff = [a - b for a, b in zip(with_v, without_v)]
    d_lo, d_hi = bootstrap_ci(diff)
    a3_null = d_lo <= 0.0 <= d_hi
    print(f"\nA3: forecast minus no-forecast = {np.mean(diff):+.3f} Wh/km, "
          f"95% CI [{d_lo:+.3f}, {d_hi:+.3f}]")
    print(f"    {'NULL: the interval contains zero' if a3_null else
             'the forecast changes the result'}")

    out = {
        "steps": args.steps, "seeds": args.seeds, "net_arch": NET_ARCH,
        "cycle": val.name, "test_cycle_sealed": CONTROL_SPLIT["test"][0],
        "soc0": args.soc0, "t_ambient_c": args.t_ambient,
        "actor_cost": Actor.load(
            actor_dir / f"sac-with-forecast-seed0.npz").cost(),
        "baseline": baseline.summary(),
        "summary": summary,
        "a3": {"diff_mean_wh_per_km": float(np.mean(diff)),
               "ci95": [d_lo, d_hi], "per_seed_diff": diff, "null": bool(a3_null)},
        "rows": rows, "curves": curves,
    }
    Path(args.out_json).write_text(json.dumps(out, indent=2) + "\n")

    head = ["arm", "seed", "wh_per_km", "equivalent_wh_per_km", "aux_shed_wh",
            "regen_wh", "tracking_rmse_mps", "soc_end", "peak_current_a",
            "gap_to_rule_pct", "wall_s"]
    lines = [",".join(head)]
    for r in rows:
        lines.append(",".join(f"{r[k]:.6g}" if isinstance(r[k], float)
                              else str(r[k]) for k in head))
    Path(args.out_csv).write_text("\n".join(lines) + "\n")
    print(f"\nwrote {args.out_json} and {args.out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
