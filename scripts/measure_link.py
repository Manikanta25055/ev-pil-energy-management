# scripts/measure_link.py
"""G3: characterise PIL link latency and reliability over a 10-minute run.

The ESP32 is the clock master. This responder waits for STEP_REQ, replies with
a STATE frame, and records the interval between consecutive requests. That
interval is the loop period as the MCU actually realises it.
"""

from __future__ import annotations

import argparse
import statistics
import time

import numpy as np

from evpil.link import SerialLink
from evpil.protocol import FrameType, pack_state


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", required=True, help="e.g. /dev/cu.usbserial-1420")
    ap.add_argument("--baud", type=int, default=921600)
    ap.add_argument("--minutes", type=float, default=10.0)
    args = ap.parse_args()

    intervals_ms: list[float] = []
    end = time.perf_counter() + args.minutes * 60.0
    last_req: float | None = None
    n_steps = 0

    with SerialLink(args.port, args.baud) as link:
        while time.perf_counter() < end:
            got = link.recv(timeout_s=0.5)
            if got is None:
                continue
            ftype, seq, t_us, _payload = got
            if ftype is not FrameType.STEP_REQ:
                continue

            now = time.perf_counter()
            if last_req is not None:
                intervals_ms.append((now - last_req) * 1000.0)
            last_req = now
            n_steps += 1

            # Constant dummy state; Task 16 substitutes the real plant.
            link.send(pack_state(seq, int(now * 1e6),
                                 [15.0, 0.0, 0.6, 40.0, 350.0, 22.0, 0.0, 500.0]))

        stats = link.stats

    arr = np.asarray(intervals_ms)
    jitter = arr - 10.0     # deviation from the nominal 10 ms period

    print(f"steps                 {n_steps}")
    print(f"duration              {args.minutes:.1f} min")
    print(f"period mean           {arr.mean():.4f} ms")
    print(f"period median         {statistics.median(arr):.4f} ms")
    print(f"jitter p50            {np.percentile(np.abs(jitter), 50):.4f} ms")
    print(f"jitter p99            {np.percentile(np.abs(jitter), 99):.4f} ms")
    print(f"jitter max            {np.abs(jitter).max():.4f} ms")
    print(f"frames_ok             {stats['frames_ok']}")
    print(f"frames_bad            {stats['frames_bad']}")
    print(f"frames_dropped        {stats['frames_dropped']}")

    p99 = float(np.percentile(np.abs(jitter), 99))
    dropped = stats["frames_dropped"] + stats["frames_bad"]
    ok = p99 <= 1.0 and dropped == 0
    print(f"\nG3 {'PASS' if ok else 'FAIL'}  (p99 <= 1.0 ms and zero dropped)")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
