"""Week 8: verify the exported actor on the board, and time it there.

The chain from a trained policy to a running one has four links and every one
of them can break quietly:

    PyTorch  ->  numpy arrays  ->  a generated C header  ->  inference in C

A transposed weight matrix, a row-major mix-up, or a stale header produces a
controller that runs, produces plausible actions, and is not the controller
that was trained. Nothing downstream would notice. So each link is checked
against the one before it on the same fixed inputs, and the last check runs on
the silicon that will carry the policy.

    PYTHONPATH="src:." python3 scripts/verify_actor.py --export
    ./scripts/idf.sh -DRUN_ACTOR_BENCH=1 build
    ./scripts/idf.sh -p /dev/cu.usbmodem1101 flash
    PYTHONPATH="src:." python3 scripts/verify_actor.py --check

The probe set mirrors `k_probe` in firmware/main/bench_actor.c. It is corners
and centre rather than random draws: saturation and sign changes are where a
layout error shows, and a uniform sample would visit them almost never.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

from evpil.control.actor import Actor, G5_LATENCY_BUDGET_MS, actor_checksum

PROBES = np.array([
    [0.80,  0.30,  0.00,  0.33,  0.00,  0.00,  0.00,  0.00],
    [0.20,  0.00,  0.00,  0.33,  0.00,  0.00,  0.00,  0.00],
    [0.94,  0.75, -0.40,  0.33,  0.30, -0.20, -0.50, -0.10],
    [0.07,  0.10,  0.40,  0.50, -0.30,  0.20,  0.90,  1.00],
    [0.50,  0.50,  0.20,  0.33,  0.10,  0.05,  0.25,  0.40],
    [-1.00, -1.00, -1.00, -1.00, -1.00, -1.00, -1.00, -1.00],
    [1.00,  1.00,  1.00,  1.00,  1.00,  1.00,  1.00,  1.00],
    [10.00, 10.00, 10.00, 10.00, 10.00, 10.00, 10.00, 10.00],
    [0.00,  0.00,  0.00,  0.00,  0.00,  0.00,  0.00,  0.00],
], dtype=np.float32)

# float32 on the device against float64 here, accumulated over 64-wide dot
# products. Set from the measured difference, not chosen for comfort.
TOL = 2e-5

HEADER = Path("firmware/main/sac_actor_weights.h")


def read_board(port: str, seconds: float = 6.0) -> list[str]:
    """Collect the benchmark's console output after a reset.

    Uses the same reset-then-reopen sequence gate G3 needs: the S3's native
    USB-Serial-JTAG delivers nothing on the first connection after a reset.
    """
    import serial

    from evpil.link import usb_jtag_hard_reset

    usb_jtag_hard_reset(port)
    lines: list[str] = []
    for _ in range(6):
        try:
            ser = serial.Serial(port, 115200, timeout=0.2)
        except OSError:
            time.sleep(0.5)
            continue
        # Each attempt gets its own window. Sharing one deadline across the
        # retries meant the first attempt -- the one that always receives
        # nothing -- consumed the whole budget and the retry never ran.
        buf = b""
        deadline = time.perf_counter() + seconds
        while time.perf_counter() < deadline:
            buf += ser.read(4096)
            if b"EVPIL-ACTOR done" in buf:
                break
        ser.close()
        lines = buf.decode("utf-8", errors="replace").splitlines()
        if any("EVPIL-ACTOR" in l for l in lines):
            return lines
        time.sleep(0.3)
    return lines


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--actor", default="data/actors/sac-with-forecast-seed0.npz")
    ap.add_argument("--params", default="data/i3_params.json")
    ap.add_argument("--export", action="store_true",
                    help="write the C header from the saved actor")
    ap.add_argument("--check", action="store_true",
                    help="read the board and compare against numpy")
    ap.add_argument("--port", default="/dev/cu.usbmodem1101")
    ap.add_argument("--out-json", default="docs/week8-actor-onchip.json")
    args = ap.parse_args()
    if not (args.export or args.check):
        args.export = args.check = True

    actor = Actor.load(args.actor)
    cost = actor.cost()
    want = np.array([actor.forward(p) for p in PROBES])

    print(f"actor {args.actor}")
    print(f"  {'-'.join(str(s) for s in actor.layer_sizes)}, "
          f"{cost['n_params']:,} parameters, {cost['macs']:,} MACs, "
          f"{cost['footprint_kb']:.1f} KB float32")

    if args.export:
        from evpil.control.actor import write_c_header
        from scripts.identify_params import params_from_json
        # The decode bounds go into the header with the weights. Two of the
        # three are properties of the action space; the third is the vehicle's
        # maximum motor power, so the params file is read here rather than the
        # number being written down twice.
        vp = params_from_json(args.params)
        write_c_header(actor, HEADER, p_limit_hi_w=vp.motor.power_max_w)
        print(f"  wrote {HEADER} ({HEADER.stat().st_size / 1024:.0f} KB), "
              f"decode p_limit up to {vp.motor.power_max_w:,.0f} W")

    if not args.check:
        return 0

    print(f"\nreading the board on {args.port}")
    lines = read_board(args.port)
    if not any("EVPIL-ACTOR" in l for l in lines):
        print("  no actor output. Did you flash a -DRUN_ACTOR_BENCH=1 build?",
              file=sys.stderr)
        return 1

    got = np.full_like(want, np.nan)
    meta: dict = {}
    for line in lines:
        m = re.match(r"EVPIL-ACTOR probe (\d+)((?:\s+[-\d.e+]+)+)", line)
        if m:
            got[int(m.group(1))] = [float(x) for x in m.group(2).split()]
            continue
        m = re.match(r"EVPIL-ACTOR checksum=([0-9a-f]+)", line)
        if m:
            meta["checksum"] = int(m.group(1), 16)
            continue
        m = re.match(r"EVPIL-ACTOR (\w+) ([-\d.]+)", line)
        if m:
            meta[m.group(1)] = float(m.group(2))
        m = re.match(r"EVPIL-ACTOR geometry in=(\d+) out=(\d+) params=(\d+)", line)
        if m:
            meta.update(in_=int(m.group(1)), out=int(m.group(2)),
                        params=int(m.group(3)))

    if np.isnan(got).any():
        print("  the board did not report every probe", file=sys.stderr)
        return 1

    err = np.abs(got - want)
    geometry_ok = meta.get("params") == cost["n_params"]
    # Geometry does not identify a policy: every seed produces an 8-64-64-3
    # network. The checksum is reported by the inference code itself, so it
    # says which weights the board is actually multiplying by.
    want_checksum = actor_checksum(actor)
    checksum_ok = meta.get("checksum") == want_checksum
    numerics_ok = bool(err.max() <= TOL)

    print(f"  geometry: {meta.get('in_')} in, {meta.get('out')} out, "
          f"{meta.get('params'):,} parameters -> "
          f"{'matches' if geometry_ok else 'MISMATCH'}")
    print(f"  weights on the board: 0x{meta.get('checksum', 0):08x}, "
          f"expected 0x{want_checksum:08x} -> "
          f"{'matches' if checksum_ok else 'MISMATCH: the board is running '
             'different weights than this actor'}")
    print(f"  worst action difference against numpy: {err.max():.2e} "
          f"(tolerance {TOL:.0e}) -> {'ok' if numerics_ok else 'FAIL'}")

    mean_ms = meta.get("latency_mean_us", float("nan")) / 1000.0
    worst_us = meta.get("latency_worst_us", float("nan"))
    fits = mean_ms <= G5_LATENCY_BUDGET_MS
    print(f"\n  measured on silicon: {mean_ms:.3f} ms mean per inference, "
          f"{worst_us:.0f} us worst single")
    print(f"  MAC-count estimate:  {cost['estimated_latency_ms']:.3f} ms")
    if cost["estimated_latency_ms"] > 0:
        ratio = mean_ms / cost["estimated_latency_ms"]
        print(f"  the estimate is {abs(1 - ratio):.0%} "
              f"{'low' if ratio > 1 else 'high'}")
    print(f"  against the {G5_LATENCY_BUDGET_MS:.0f} ms budget: "
          f"{mean_ms / G5_LATENCY_BUDGET_MS:.1%} -> "
          f"{'fits' if fits else 'DOES NOT FIT'}")

    verdict = geometry_ok and checksum_ok and numerics_ok and fits
    print(f"\nactor on-chip verification {'PASS' if verdict else 'FAIL'}")

    Path(args.out_json).write_text(json.dumps({
        "actor": args.actor,
        "cost": cost,
        "geometry_reported": meta.get("params"),
        "geometry_ok": geometry_ok,
        "checksum_board": meta.get("checksum"),
        "checksum_expected": want_checksum,
        "checksum_ok": checksum_ok,
        "max_action_error": float(err.max()),
        "tolerance": TOL,
        "numerics_ok": numerics_ok,
        "latency_mean_ms": mean_ms,
        "latency_worst_us": worst_us,
        "repeats": meta.get("repeats"),
        "estimated_latency_ms": cost["estimated_latency_ms"],
        "budget_ms": G5_LATENCY_BUDGET_MS,
        "fits_budget": bool(fits),
        "verdict": "PASS" if verdict else "FAIL",
        "probes": PROBES.tolist(),
        "host_actions": want.tolist(),
        "board_actions": got.tolist(),
    }, indent=2) + "\n")
    print(f"wrote {args.out_json}")
    return 0 if verdict else 1


if __name__ == "__main__":
    raise SystemExit(main())
