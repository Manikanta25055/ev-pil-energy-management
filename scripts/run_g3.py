"""Gate G3: close the 10 ms processor-in-the-loop loop and measure it.

Spec 8.2: the loop closes end-to-end with p99 jitter at most 1 ms and zero
dropped frames over a ten-minute run.

The host answers the MCU's STEP_REQ frames with plant state and consumes its
ACTUATION frames. It does not drive the schedule: the MCU is the clock master
(spec 4.5), because macOS is not a real-time host and timing measured here
would carry the host's own scheduling noise rather than the loop's (risk R5).
So every timing number quoted as a result comes from the MCU's own histogram,
delivered over the link as DIAG frames. The host measures only what only the
host can see: frames it never received.

    PYTHONPATH="src:." python3 scripts/run_g3.py --minutes 10
"""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

from evpil.link import SerialLink, reset_and_reexec
from evpil.protocol import (
    JITTER_BIN_EDGES_US,
    N_JITTER_BINS,
    FrameType,
    jitter_percentile,
    pack_state,
    unpack_diag,
)

# Gate thresholds, spec 8.2.
P99_LIMIT_US = 1000.0
DROPPED_LIMIT = 0


def plant_state(step: int) -> list[float]:
    """A cheap stand-in for the validated plant.

    G3 measures the loop, not the physics. Replaying a real trip here would
    add host-side work that varies per step and would show up in the timing as
    though it were jitter. A closed-form state costs the same on every step,
    which is what makes the measurement about the link.
    """
    t = step * 0.01
    return [
        15.0 + 5.0 * math.sin(t * 0.2),      # v_mps
        1.0 * math.cos(t * 0.2),             # a_mps2
        0.70 - 1e-6 * step,                  # soc_frac
        60.0 + 20.0 * math.sin(t * 0.3),     # i_batt_a
        372.0,                               # v_batt_v
        12.0,                                # t_ambient_c
        0.01 * math.sin(t * 0.05),           # grade_rad
        600.0,                               # p_aux_w
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/cu.usbmodem1101")
    ap.add_argument("--baud", type=int, default=921600)
    ap.add_argument("--minutes", type=float, default=10.0)
    ap.add_argument("--settle", type=float, default=3.0,
                    help="seconds to discard after the link comes up")
    ap.add_argument("--no-reset", action="store_true",
                    help="skip the reset; see evpil.link.usb_jtag_hard_reset "
                         "for why the default is to perform one")
    ap.add_argument("--out-json", default="docs/g3-loop-timing.json")
    ap.add_argument("--out-csv", default="docs/g3-jitter-histogram.csv")
    args = ap.parse_args()

    duration = args.minutes * 60.0
    print(f"G3: {args.minutes:.1f} minute run on {args.port}")
    print(f"    pass: p99 jitter <= {P99_LIMIT_US:.0f} us and "
          f"{DROPPED_LIMIT} dropped frames\n")

    last_diag = None
    baseline = None
    step = 0
    started = None
    replies = 0

    if not args.no_reset:
        print("  resetting the board, then restarting this process to talk to "
              "it; see evpil.link.reset_and_reexec")
        reset_and_reexec(args.port)

    with SerialLink(args.port, args.baud) as link:
        t_start = time.perf_counter()
        while True:
            now = time.perf_counter()
            if started is not None and now - started >= duration:
                break
            if started is None and now - t_start > 60.0:
                raise SystemExit(
                    "no STEP_REQ in 60 s. Is the firmware running and is "
                    "LINK_TRANSPORT set to the port you are connected to?"
                )

            item = link.recv(timeout_s=0.05)
            if item is None:
                continue
            ftype, seq, t_us, payload = item

            if ftype is FrameType.STEP_REQ:
                link.send(pack_state(seq, t_us, plant_state(step)))
                step += 1
                replies += 1
                if started is None:
                    started = time.perf_counter()

            elif ftype is FrameType.DIAG:
                stats, hist = unpack_diag(payload)
                if started is not None and \
                        time.perf_counter() - started >= args.settle:
                    if baseline is None:
                        # Everything before the settle point is discarded:
                        # enumeration and the first frames are not the steady
                        # state the gate is about.
                        baseline = (dict(stats), tuple(hist))
                        print(f"  settled after {args.settle:.0f} s, "
                              f"{stats['loop_count']} loops elapsed")
                    last_diag = (dict(stats), tuple(hist))

            if replies and replies % 6000 == 0 and last_diag is not None:
                el = time.perf_counter() - (started or t_start)
                s0, h0 = baseline
                s1, h1 = last_diag
                delta = [b - a for a, b in zip(h0, h1)]
                if sum(delta) > 0:
                    print(f"  {el / 60:5.1f} min  loops "
                          f"{s1['loop_count'] - s0['loop_count']:>7}  "
                          f"p99 {jitter_percentile(delta, 0.99):>7.0f} us  "
                          f"timeouts {s1['rx_timeouts'] - s0['rx_timeouts']:>5}")

        host_stats = dict(link.stats)

    if baseline is None or last_diag is None:
        raise SystemExit("no DIAG frames received after the settle window")

    s0, h0 = baseline
    s1, h1 = last_diag
    hist = [b - a for a, b in zip(h0, h1)]
    counters = {k: s1[k] - s0[k] for k in
                ("loop_count", "rx_timeouts", "rx_bad", "infer_deadline_misses")}
    # Running maxima on the MCU, so a difference is meaningless and these are
    # taken as-is. That means they include the startup transient before the
    # settle point: the first loop after boot has no predecessor and the link
    # is still coming up, which is where a 14 ms period and a 124 us one both
    # come from. The gate is decided on the differenced histogram, which
    # excludes that window. These are reported for context, not as the verdict.
    extremes = {k: s1[k] for k in
                ("ctrl_wcet_us", "infer_wcet_us", "rtt_max_us",
                 "period_min_us", "period_max_us")}

    total = sum(hist)
    p50 = jitter_percentile(hist, 0.50)
    p99 = jitter_percentile(hist, 0.99)
    p999 = jitter_percentile(hist, 0.999)

    dropped = counters["rx_timeouts"] + counters["rx_bad"] \
        + host_stats["frames_dropped"]

    print(f"\nmeasured over {args.minutes:.1f} minutes, "
          f"{counters['loop_count']} control loops")
    print(f"  jitter p50   {p50:>8.0f} us")
    print(f"  jitter p99   {p99:>8.0f} us   (limit {P99_LIMIT_US:.0f})")
    print(f"  jitter p99.9 {p999:>8.0f} us")
    print(f"  period       {extremes['period_min_us']} to "
          f"{extremes['period_max_us']} us since boot, nominal 10000")
    print(f"               (includes the startup transient; the gate uses the "
          f"histogram above)")
    print(f"  ctrl WCET    {extremes['ctrl_wcet_us']:>8} us")
    print(f"  round trip   {extremes['rtt_max_us']:>8} us worst")
    print(f"\n  MCU rx timeouts     {counters['rx_timeouts']}")
    print(f"  MCU bad frames      {counters['rx_bad']}")
    print(f"  host dropped frames {host_stats['frames_dropped']}")
    print(f"  host bad frames     {host_stats['frames_bad']}")

    pass_jitter = p99 <= P99_LIMIT_US
    pass_frames = dropped <= DROPPED_LIMIT
    verdict = "PASS" if (pass_jitter and pass_frames) else "FAIL"
    print(f"\nG3 {verdict}"
          f"  (jitter {'ok' if pass_jitter else 'FAIL'}, "
          f"frames {'ok' if pass_frames else 'FAIL'})")

    lines = ["bin_upper_us,count,cumulative_fraction"]
    running = 0
    for k in range(N_JITTER_BINS):
        running += hist[k]
        edge = (str(JITTER_BIN_EDGES_US[k]) if k < len(JITTER_BIN_EDGES_US)
                else "inf")
        lines.append(f"{edge},{hist[k]},{running / total if total else 0:.6f}")
    Path(args.out_csv).write_text("\n".join(lines) + "\n")

    Path(args.out_json).write_text(json.dumps({
        "minutes": args.minutes,
        "port": args.port,
        "counters": counters,
        "extremes": extremes,
        "host": host_stats,
        "histogram": hist,
        "bin_edges_us": list(JITTER_BIN_EDGES_US),
        "p50_us": p50, "p99_us": p99, "p999_us": p999,
        "dropped_total": dropped,
        "limits": {"p99_us": P99_LIMIT_US, "dropped": DROPPED_LIMIT},
        "verdict": verdict,
    }, indent=2) + "\n")
    print(f"\nwrote {args.out_json} and {args.out_csv}")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
