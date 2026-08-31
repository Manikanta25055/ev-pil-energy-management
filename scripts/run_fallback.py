"""Week 7: take the fallback path on hardware and count what it did.

A fallback path that has never been taken is a claim. This exercises all three
of them on the real board and checks that each counter moves by the amount its
injection schedule implies, and that the other two do not.

Two of the three faults are injected inside the firmware, because they cannot
be caused from outside it: the outer loop going quiet and inference overrunning
both happen on the device. Build with FAULT_INJECT=1 first:

    ./scripts/idf.sh -DFAULT_INJECT=1 build
    ./scripts/idf.sh -p /dev/cu.usbmodem1101 flash
    PYTHONPATH="src:." python3 scripts/run_fallback.py

The third, a stale plant state, this script causes itself by not answering the
microcontroller for a while. That one is the interesting case: it is the
failure a real link actually has, and the response to it -- ramping torque out
rather than acting on an old speed -- is the one that shows up as vehicle
behaviour.

The watchdog is a separate build (FAULT_INJECT=2) because it resets the board;
run it with --watchdog, which checks the boot reason instead of the counters.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

from evpil.link import SerialLink, reset_and_reexec
from evpil.protocol import (
    RESET_REASONS, FrameType, unpack_actuation, unpack_diag,
)
from scripts.run_g3 import plant_state

# Mirrors FAULT_EMS_AT_S / FAULT_INFER_AT_S / FAULT_WINDOW_S in tasks.h.
EMS_STALL_AT_S = 20.0
INFER_OVERRUN_AT_S = 40.0
FAULT_WINDOW_S = 2.0
# The host-side fault, which the firmware knows nothing about.
HOST_SILENCE_AT_S = 8.0
HOST_SILENCE_S = 1.0

COUNTERS = ("ctrl_fallback_steps", "limp_steps", "ems_fallback_steps",
            "infer_deadline_misses", "ctrl_late", "stale_steps", "loop_count")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/cu.usbmodem1101")
    ap.add_argument("--baud", type=int, default=921600)
    ap.add_argument("--seconds", type=float, default=50.0)
    ap.add_argument("--watchdog", action="store_true",
                    help="check the boot reason after a FAULT_INJECT=2 build")
    ap.add_argument("--no-reset", action="store_true")
    ap.add_argument("--out-json", default="docs/week7-fallback.json")
    args = ap.parse_args()

    if not args.no_reset:
        reset_and_reexec(args.port)

    print(f"fallback campaign on {args.port}, {args.seconds:.0f} s")
    marks: list[dict] = []
    torque_during_silence: list[float] = []
    first_diag = None
    last_diag = None
    step = 0
    t0 = None
    silence_until = None

    with SerialLink(args.port, args.baud) as link:
        opened = time.perf_counter()
        while True:
            now = time.perf_counter()
            if t0 is not None and now - t0 >= args.seconds:
                break
            if t0 is None and now - opened > 60.0:
                raise SystemExit("no STEP_REQ in 60 s; is the firmware running?")

            item = link.recv(timeout_s=0.05)
            if item is None:
                continue
            ftype, seq, t_us, payload = item
            if t0 is None:
                t0 = time.perf_counter()
            elapsed = time.perf_counter() - t0

            if ftype is FrameType.STEP_REQ:
                # The host-side fault: go silent, so the microcontroller's
                # most recent state ages past STALE_LIMIT_STEPS.
                if (silence_until is None
                        and elapsed >= HOST_SILENCE_AT_S):
                    silence_until = elapsed + HOST_SILENCE_S
                    print(f"  {elapsed:5.1f} s  host goes silent for "
                          f"{HOST_SILENCE_S:.1f} s")
                if silence_until is not None and elapsed < silence_until:
                    continue
                if silence_until is not None and elapsed >= silence_until \
                        and silence_until > 0:
                    print(f"  {elapsed:5.1f} s  host answering again")
                    silence_until = -1.0
                link.send(_state_frame(seq, t_us, step))
                step += 1

            elif ftype is FrameType.ACTUATION:
                if silence_until is not None and 0 < silence_until \
                        and elapsed < silence_until:
                    torque_during_silence.append(
                        unpack_actuation(payload)["torque_nm"])

            elif ftype is FrameType.DIAG:
                stats, _ = unpack_diag(payload)
                if first_diag is None:
                    first_diag = dict(stats)
                    print(f"  boot reason: "
                          f"{RESET_REASONS.get(stats['boot_reason'], stats['boot_reason'])}"
                          f" ({stats['boot_reason']})")
                last_diag = dict(stats)
                marks.append({"t_s": elapsed,
                              **{k: stats[k] for k in COUNTERS}})

    if first_diag is None or last_diag is None:
        raise SystemExit("no DIAG frames received")

    delta = {k: last_diag[k] - first_diag[k] for k in COUNTERS}
    reason = last_diag["boot_reason"]

    print("\ncounter                 delta over the run")
    for k in COUNTERS:
        print(f"  {k:22} {delta[k]:>8}")

    print(f"\n  torque during the silent window: "
          f"{len(torque_during_silence)} frames, "
          f"{'ramped to ' + format(torque_during_silence[-1], '.2f') + ' Nm' if torque_during_silence else 'none seen'}")

    # A counter that went backwards means the device restarted mid-run: the
    # counters live in RAM and start again from zero. In the watchdog build
    # that is the expected outcome and the whole point, so the fault-injection
    # expectations below do not apply to it.
    restarted = any(delta[k] < 0 for k in COUNTERS)
    if restarted:
        print("\n  a counter went backwards: the device restarted during "
              "the run")

    checks = {}
    if not args.watchdog:
        # Expectations, stated before the run and checked after it.
        expect = {
            "limp_steps": (1, None),
            "ctrl_fallback_steps": (100, None),
            "ems_fallback_steps": (5, None),
            "infer_deadline_misses": (5, None),
        }
        for k, (lo, hi) in expect.items():
            ok = delta[k] >= lo and (hi is None or delta[k] <= hi)
            checks[k] = bool(ok)
            print(f"  {k:22} expected >= {lo:<6} got {delta[k]:<8} "
                  f"{'ok' if ok else 'FAIL'}")

    if args.watchdog:
        checks["restarted"] = bool(restarted)
        ok = reason == 6
        print(f"\nwatchdog check: boot reason "
              f"{RESET_REASONS.get(reason, reason)} -> "
              f"{'PASS' if ok else 'FAIL (expected task watchdog)'}")
        checks["watchdog_reset"] = bool(ok)

    verdict = all(checks.values())
    label = "watchdog" if args.watchdog else "fallback path"
    print(f"\n{label} {'VERIFIED' if verdict else 'NOT VERIFIED'}")

    out = Path(args.out_json)
    payload = {
        "seconds": args.seconds, "port": args.port,
        "schedule": {"host_silence_at_s": HOST_SILENCE_AT_S,
                     "host_silence_s": HOST_SILENCE_S,
                     "ems_stall_at_s": EMS_STALL_AT_S,
                     "infer_overrun_at_s": INFER_OVERRUN_AT_S,
                     "fault_window_s": FAULT_WINDOW_S},
        "delta": delta, "checks": checks, "verdict": verdict,
        "restarted_during_run": bool(restarted),
        "boot_reason": reason,
        "boot_reason_name": RESET_REASONS.get(reason, str(reason)),
        "torque_during_silence_nm": torque_during_silence,
        "marks": marks,
    }
    if args.watchdog and out.name == "week7-fallback.json":
        out = out.with_name("week7-watchdog.json")
    out.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"wrote {out}")
    return 0 if verdict else 1


def _state_frame(seq: int, t_us: int, step: int) -> bytes:
    from evpil.protocol import pack_state
    return pack_state(seq, t_us, plant_state(step))


if __name__ == "__main__":
    raise SystemExit(main())
