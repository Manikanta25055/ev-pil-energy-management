"""Record what a reviewer would have been shown, with the truth beside it.

Runs the registered train and validation cases with B7 alone in the loop and
a recording supervisor around it that gives no advice. Each 100 ms block
becomes one row: the twelve features the chip could compute, and a label
from the simulation's own schedule, which the chip could not:

  0 healthy   1 sensor fault   2 acceleration channel degraded   3 both

The sensor label is the fault being on at the end of the block. The
acceleration label is the channel's slow error, averaged over the block,
being larger than `supervisor.ACCEL_DEGRADED_MPS2`.

The test split is never built here. SIMULATED on the laptop.

    PYTHONPATH="src:." python3 scripts/build_reviewer_data.py
"""

from __future__ import annotations

import argparse
import json
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from evpil.control import sensor_eval as se
from evpil.control.block_features import BLOCK_STEPS
from evpil.control.speed_estimators import BiasAwareFaultKalman
from evpil.control.supervisor import ACCEL_DEGRADED_MPS2, Supervisor

CLEAN_MAX_S = 600.0
_CTX = None


def _ctx():
    global _CTX
    if _CTX is None:
        from scripts.identify_params import params_from_json
        tuned = json.loads(
            Path("docs/week11-speed-arms-tuned.json").read_text())
        _CTX = (params_from_json("data/i3_params.json"),
                tuned["b3a"]["q_mps"], tuned["b5"]["q_d_mps2"])
    return _CTX


def labels(n_blocks: int, a: int, b: int, err: np.ndarray) -> np.ndarray:
    y = np.zeros(n_blocks, dtype=np.int64)
    for i in range(n_blocks):
        end = (i + 1) * BLOCK_STEPS - 1
        fault = a <= end < b
        slow = abs(float(np.mean(err[i * BLOCK_STEPS:(i + 1) * BLOCK_STEPS])))
        y[i] = int(fault) + 2 * int(slow > ACCEL_DEGRADED_MPS2)
    return y


def _one(case: se.Case):
    nominal, q, q_d = _ctx()
    sup = Supervisor(BiasAwareFaultKalman(nominal, q_mps=q, q_d_mps2=q_d),
                     record=True)
    if case.fault:
        _, a, b, err = se.simulate_fault_case(nominal, case, sup)
    else:
        _, cyc, err = se.simulate_clean_case(nominal, case, sup,
                                             max_s=CLEAN_MAX_S)
        a = b = -1
        if err is None:
            err = np.zeros(len(cyc.v_ref_mps))
    x = np.array([s.x for s in sup.snapshots], dtype=np.float32)
    return x, labels(len(x), a, b, err)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/reviewer")
    ap.add_argument("--procs", type=int, default=4)
    args = ap.parse_args()
    Path(args.out).mkdir(parents=True, exist_ok=True)
    for split in ("train", "val"):
        cases = se.fault_cases(split) + se.clean_cases(split)
        t0 = time.time()
        with Pool(args.procs) as pool:
            rows = pool.map(_one, cases, chunksize=8)
        lens = np.array([len(x) for x, _ in rows])
        x = np.concatenate([x for x, _ in rows])
        y = np.concatenate([y for _, y in rows])
        np.savez_compressed(
            f"{args.out}/{split}.npz", x=x, y=y, lens=lens,
            fault=np.array([c.fault for c in cases]),
            accel=np.array([c.accel for c in cases]),
            noise_x=np.array([c.noise_x for c in cases]),
            config=se.config_hash())
        print(f"{split}: {len(cases)} runs, {len(y)} blocks, labels "
              f"{np.bincount(y, minlength=4).tolist()}, "
              f"{time.time() - t0:.0f} s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
