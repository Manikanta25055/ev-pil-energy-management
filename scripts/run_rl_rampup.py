"""Week 7: the RL ramp-up. Toolchain first, then the real environment.

Risk R1 says the reinforcement-learning work is the identified skill gap and
that SAC is finicky, and the mitigation is to spend week 7 on the ramp-up so
that week 8 spends its time on convergence. This script is that ramp-up. It
does not train a controller and it does not report one.

Two runs, in this order, because they fail for different reasons and mixing
them makes a failure unattributable:

  1. Pendulum-v1. A problem with a known solution and a known score. If SAC
     does not reach roughly -200 average return here, the fault is in the
     installation or the hyperparameters, not in the energy environment.
  2. The energy-management environment, briefly. This measures throughput --
     how many environment steps per second the plant sustains -- which is
     what sets whether week 8's five seeds are an afternoon or a weekend.

    PYTHONPATH="src:." python3 scripts/run_rl_rampup.py
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

from evpil.forecast import _openmp        # noqa: F401  (import-order guard)

from evpil.control.cycles import load_cycle
from evpil.control.env import EnergyManagementEnv, RewardWeights
from evpil.control.rule_ems import RuleParams, rule_action
from scripts.identify_params import params_from_json

PENDULUM_TARGET = -300.0     # SAC clears this comfortably at 10k steps


def evaluate(model, env, episodes: int = 5, deterministic: bool = True) -> dict:
    returns, energies, rmses = [], [], []
    for ep in range(episodes):
        obs, _ = env.reset(seed=1000 + ep)
        total, energy, err = 0.0, 0.0, []
        while True:
            action, _ = model.predict(obs, deterministic=deterministic)
            obs, r, term, trunc, info = env.step(action)
            total += r
            energy += info.get("energy_wh", 0.0)
            err.append(info.get("tracking_rmse_mps", 0.0))
            if term or trunc:
                break
        returns.append(total)
        energies.append(energy)
        rmses.append(float(np.mean(err)))
    return {"return_mean": float(np.mean(returns)),
            "return_std": float(np.std(returns)),
            "energy_wh_mean": float(np.mean(energies)),
            "tracking_rmse_mps": float(np.mean(rmses))}


def evaluate_rule(env, rules: RuleParams, episodes: int = 5) -> dict:
    """The same evaluation for the rule-based manager, on the same episodes.

    Same seeds, so the two are compared on identical initial states, ambient
    temperatures and cycle windows rather than on the luck of the reset.
    """
    returns, energies, rmses = [], [], []
    for ep in range(episodes):
        obs, _ = env.reset(seed=1000 + ep)
        total, energy, err = 0.0, 0.0, []
        while True:
            act = rule_action(rules,
                              soc_frac=float(obs[0]),
                              v_mps=float(obs[1]) * 40.0)
            a = np.array([
                2.0 * act.regen_blend - 1.0,
                2.0 * (act.p_limit_w - 40000.0) / (125000.0 - 40000.0) - 1.0,
                2.0 * act.aux_derate / 0.30 - 1.0,
            ], dtype=np.float32)
            obs, r, term, trunc, info = env.step(a)
            total += r
            energy += info.get("energy_wh", 0.0)
            err.append(info.get("tracking_rmse_mps", 0.0))
            if term or trunc:
                break
        returns.append(total)
        energies.append(energy)
        rmses.append(float(np.mean(err)))
    return {"return_mean": float(np.mean(returns)),
            "return_std": float(np.std(returns)),
            "energy_wh_mean": float(np.mean(energies)),
            "tracking_rmse_mps": float(np.mean(rmses))}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--params", default="data/i3_params.json")
    ap.add_argument("--pendulum-steps", type=int, default=10000)
    ap.add_argument("--ev-steps", type=int, default=15000)
    ap.add_argument("--episode-steps", type=int, default=300)
    ap.add_argument("--seed", type=int, default=20260831)
    ap.add_argument("--out-json", default="docs/week7-rl-rampup.json")
    args = ap.parse_args()

    import gymnasium as gym
    import stable_baselines3 as sb3
    from stable_baselines3 import SAC

    report: dict = {
        "versions": {
            "stable_baselines3": sb3.__version__,
            "gymnasium": gym.__version__,
        },
        "seed": args.seed,
    }
    print(f"stable-baselines3 {sb3.__version__}, gymnasium {gym.__version__}")

    # --- 1. toolchain check on a problem with a known answer ---------------
    print(f"\nPendulum-v1, SAC, {args.pendulum_steps} steps")
    t0 = time.time()
    pend = gym.make("Pendulum-v1")
    model = SAC("MlpPolicy", pend, seed=args.seed, verbose=0)
    model.learn(total_timesteps=args.pendulum_steps, progress_bar=False)
    pend_wall = time.time() - t0

    scores = []
    for ep in range(10):
        obs, _ = pend.reset(seed=500 + ep)
        total = 0.0
        while True:
            a, _ = model.predict(obs, deterministic=True)
            obs, r, term, trunc, _ = pend.step(a)
            total += r
            if term or trunc:
                break
        scores.append(total)
    pend_return = float(np.mean(scores))
    ok = pend_return >= PENDULUM_TARGET
    print(f"  return {pend_return:.1f} (target >= {PENDULUM_TARGET:.0f}) "
          f"-> {'PASS' if ok else 'FAIL'}   {pend_wall:.0f} s wall, "
          f"{args.pendulum_steps / pend_wall:.0f} steps/s")
    report["pendulum"] = {
        "steps": args.pendulum_steps, "return_mean": pend_return,
        "target": PENDULUM_TARGET, "pass": bool(ok),
        "wall_s": pend_wall, "steps_per_s": args.pendulum_steps / pend_wall,
    }

    # --- 2. the real environment, briefly ---------------------------------
    params = params_from_json(args.params)
    train = [load_cycle(c) for c in ("wltc3b", "udds")]
    env = EnergyManagementEnv(params, train, weights=RewardWeights(),
                              episode_steps=args.episode_steps,
                              seed=args.seed)

    print("\nenvironment throughput, random actions")
    obs, _ = env.reset(seed=0)
    t0 = time.time()
    n_probe = 2000
    for _ in range(n_probe):
        _, _, term, trunc, _ = env.step(env.action_space.sample())
        if term or trunc:
            env.reset()
    env_sps = n_probe / (time.time() - t0)
    print(f"  {env_sps:.0f} outer steps/s "
          f"({env_sps * 10:.0f} plant steps/s)")

    rule_score = evaluate_rule(env, RuleParams())
    print(f"  rule-based manager on the evaluation episodes: "
          f"return {rule_score['return_mean']:.1f}, "
          f"{rule_score['energy_wh_mean']:.1f} Wh")

    print(f"\nenergy environment, SAC, {args.ev_steps} steps "
          f"(a ramp-up, not a trained controller)")
    t0 = time.time()
    ev_model = SAC("MlpPolicy", env, seed=args.seed, verbose=0,
                   learning_starts=1000)
    ev_model.learn(total_timesteps=args.ev_steps, progress_bar=False)
    ev_wall = time.time() - t0
    sac_score = evaluate(ev_model, env)

    print(f"  {ev_wall:.0f} s wall, {args.ev_steps / ev_wall:.0f} steps/s")
    print(f"  SAC  return {sac_score['return_mean']:8.2f} +- "
          f"{sac_score['return_std']:.2f}   "
          f"{sac_score['energy_wh_mean']:6.1f} Wh   "
          f"rmse {sac_score['tracking_rmse_mps']:.4f} m/s")
    print(f"  rule return {rule_score['return_mean']:8.2f} +- "
          f"{rule_score['return_std']:.2f}   "
          f"{rule_score['energy_wh_mean']:6.1f} Wh   "
          f"rmse {rule_score['tracking_rmse_mps']:.4f} m/s")

    # Week 8 needs a number, not a feeling, for how long five seeds will take.
    per_seed_s = 300_000 / (args.ev_steps / ev_wall)
    print(f"\n  projected: 300k steps per seed = {per_seed_s / 60:.0f} min, "
          f"5 seeds = {5 * per_seed_s / 3600:.1f} h on this machine")

    report["energy_env"] = {
        "steps": args.ev_steps, "episode_steps": args.episode_steps,
        "wall_s": ev_wall, "steps_per_s": args.ev_steps / ev_wall,
        "env_only_steps_per_s": env_sps,
        "sac": sac_score, "rule": rule_score,
        "projected_5_seed_hours": 5 * per_seed_s / 3600,
    }

    Path(args.out_json).write_text(json.dumps(report, indent=2) + "\n")
    print(f"\nwrote {args.out_json}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
