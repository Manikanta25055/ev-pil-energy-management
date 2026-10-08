"""Run one sensor arm through the registered evaluation.

The cases, splits and criteria are in `evpil.control.sensor_eval`; this only
builds the arm and farms the cases out. SIMULATED on the laptop.

    PYTHONPATH="src:." python3 scripts/run_sensor_eval.py --arm b7 --split val

Do not run this while a board campaign is on: it uses several processes.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from multiprocessing import Pool
from pathlib import Path

from evpil.control import sensor_eval as se
from scripts.sensor_arms import ARMS, make_arm

_NOMINAL = None
_TUNED = None


def _setup():
    global _NOMINAL, _TUNED
    if _NOMINAL is None:
        from scripts.identify_params import params_from_json
        _NOMINAL = params_from_json("data/i3_params.json")
        _TUNED = json.loads(
            Path("docs/week11-speed-arms-tuned.json").read_text())
    return _NOMINAL, _TUNED


def _one(job):
    arm, settings, case = job
    nominal, tuned = _setup()
    q, q_d = tuned["b3a"]["q_mps"], tuned["b5"]["q_d_mps2"]
    make = lambda: make_arm(arm, nominal, q, q_d, settings)
    if case.fault:
        return "fault", se.run_fault_case(nominal, case, make)
    return "clean", se.run_clean_case(nominal, case, make, q_mps=q,
                                      q_d_mps2=q_d)


def evaluate(arm: str, split: str, *, settings: dict | None = None,
             procs: int = 4, accels=None, clean: bool = True,
             faults: bool = True, noise_x=se.NOISE_X,
             fault_labels=None, cycles=None) -> dict:
    """The keyword filters cut the registered set down for tuning. A
    result that is reported is run with none of them."""
    cases = []
    if faults:
        cases += [c for c in se.fault_cases(split, accels=accels,
                                            noise_x=noise_x)
                  if fault_labels is None or c.fault in fault_labels]
    if clean:
        cases += [c for c in se.clean_cases(split)
                  if accels is None or c.accel in accels]
    if cycles is not None:
        cases = [c for c in cases if c.cycle in cycles]
    jobs = [(arm, settings, c) for c in cases]
    t0 = time.time()
    with Pool(procs) as pool:
        res = pool.map(_one, jobs, chunksize=4)
    f = [r for kind, r in res if kind == "fault"]
    c = [r for kind, r in res if kind == "clean"]
    return {"arm": arm, "split": split, "settings": settings,
            "seconds": time.time() - t0, "verdict": se.verdict(f, c),
            "faults": f, "clean": c}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True, choices=sorted(ARMS))
    ap.add_argument("--split", required=True, choices=("train", "val", "test"))
    ap.add_argument("--settings", default=None,
                    help="JSON file of settings for the arm")
    ap.add_argument("--procs", type=int, default=4)
    ap.add_argument("--out-json", default=None)
    args = ap.parse_args()

    settings = (json.loads(Path(args.settings).read_text())
                if args.settings else None)
    out = evaluate(args.arm, args.split, settings=settings, procs=args.procs)
    out["provenance"] = "SIMULATED on the laptop; no board involved"
    out["commit"] = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], capture_output=True,
        text=True).stdout.strip()
    path = args.out_json or f"docs/week13-sensor-{args.arm}-{args.split}.json"
    Path(path).write_text(json.dumps(out, indent=1) + "\n")
    v = out["verdict"]
    for name, g in v["by_accel"].items():
        print(f"{name:22s} " + "  ".join(
            f"{k}={g[k]:.3g}" if isinstance(g[k], float) else f"{k}={g[k]}"
            for k in ("detected_in_time", "named_faults", "false_clears",
                      "lingering_flags", "cleared_within_2s_frac",
                      "false_alarms_per_hour_floor", "worst_peak_err_mps",
                      "worst_clean_rmse_mps", "passes") if k in g))
    print(f"passed {v['cases_passed']} of {v['cases_judged']} cases, "
          f"{out['seconds']:.0f} s, wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
