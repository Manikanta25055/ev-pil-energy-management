"""Ablation A4 with the loop closed: the plant answers the torque the board commands.

`scripts/run_fallback.py` proves the fallback path is taken, and it does that
well. It cannot say what the path costs in control quality, because the state
it feeds the board is `run_g3.plant_state`, a closed-form function of the step
index. The torque the device commands never reaches the plant that answers it,
so no tracking error can accumulate and there is nothing for the recovery
window to show. `docs/week9-a4.md` section 4 records that in detail.

That closed form was the right choice for G3. Replaying a trip adds host-side
work that varies per step, and G3 was measuring the link's timing, where such
work appears as jitter the loop did not cause. A4 measures control quality
instead, and for that the loop has to be closed.

So this script does what `predict_a4.py` simulates, except that the controller
is the real firmware on the real board:

  * the reference is a drive cycle, not a sine
  * the plant is the validated one from `docs/g2-plant-validation.md`, stepped
    with the torque, regen blend, power limit and auxiliary derate the board
    just sent
  * the tracking error is measured against the true reference, which is what
    tracking means regardless of what the controller could see at the time

The blackout is host-side and needs no special firmware: the host stops
answering, which is the failure a real link has. Note what does *not* stop.
The board keeps running its control task and keeps sending actuation at
100 Hz, so the plant keeps being stepped and the drive cycle keeps running on.
A vehicle does not pause because its link went down, and neither does this.

Run it against both builds, from a 15 s lead-in so the loop is settled:

    ./scripts/idf.sh -DFAULT_INJECT=0 -DFALLBACK_ENABLED=1 build
    ./scripts/idf.sh -p /dev/cu.usbmodem1101 flash
    PYTHONPATH="src:." python3 scripts/run_a4_closedloop.py \
        --out-json docs/week9-a4-closed-on.json

    ./scripts/idf.sh -DFAULT_INJECT=0 -DFALLBACK_ENABLED=0 build
    ./scripts/idf.sh -p /dev/cu.usbmodem1101 flash
    PYTHONPATH="src:." python3 scripts/run_a4_closedloop.py --fallback-off \
        --out-json docs/week9-a4-closed-off.json

The metric reported is the one the prediction is staked on: peak absolute
speed error over the outage and the RECOVERY_S after it, in m/s.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path

import numpy as np

from evpil.control.cycles import load_cycle
from evpil.link import SerialLink, reset_and_reexec
from evpil.protocol import (
    RESET_REASONS, FrameType, pack_state, unpack_actuation, unpack_diag,
)
from evpil.plant.plant import Plant
from scripts.identify_params import params_from_json
from scripts.run_fallback import COUNTERS, expectations

# Mirrored from firmware/main/tasks.h, the same three constants predict_a4.py
# mirrors. The parity test reads them back out of the header.
CTRL_PERIOD_S = 0.010

# Matched to scripts/predict_a4.py so the measurement lands on the same axes
# as the prediction it is scored against.
LEAD_IN_S = 15.0
RECOVERY_S = 2.0
BLACKOUT_S = 1.0

# Ambient and starting charge, held fixed. A4 is about the tracking loop.
SOC0 = 0.80
T_AMBIENT_C = 12.0
T_BATT_C = 20.0

# Which counters this campaign is entitled to score.
#
# Build it with FAULT_INJECT=0. The firmware's own injection schedule fires at
# 20 s and 40 s after boot, and a lead-in plus a blackout plus a recovery is
# shorter than that, so a fault-injecting build would land its outer-loop stall
# somewhere inside the measurement window and put a second effect into the
# tracking error. The host silence is a real fault and is the only one wanted
# here.
#
# That choice decides the scored set. `ems_fallback_steps` and
# `infer_deadline_misses` are injected and cannot move. Neither can
# `ctrl_fallback_steps`, which counts the rule manager taking over from a
# silent *outer loop*, i.e. the injected EMS stall, not the host blackout.
# What remains is exactly the pair this campaign drives: `limp_steps`, which
# the ablation compiles out, and `stale_steps`, which it does not, plus
# `ctrl_late`, which must stay at zero in any build.
SCORED = ("limp_steps", "stale_steps", "ctrl_late")


def run_blackout(link, *, cycle_arrays, plant, k_onset, lead_in_k, black_k,
                 recovery_k) -> dict:
    """One blackout: lead in, go silent, watch the recovery.

    The board is not reset between blackouts, so its PID carries state across
    them. The lead-in is what absorbs that, and `err_peak_before_blackout_mps`
    is the check that it did rather than the assumption that it would.
    """
    v_ref_all, a_ref_all, grade_all = cycle_arrays
    k_start = k_onset - lead_in_k
    k_end_black = k_onset + black_k
    k_stop = k_end_black + recovery_k

    state = plant.reset(SOC0, T_AMBIENT_C, T_BATT_C)
    # Start on the reference rather than from rest, so the lead-in settles the
    # loop instead of spending itself accelerating from zero. Same as
    # predict_a4.py, for the same reason.
    state = replace(state, v_mps=float(v_ref_all[k_start]))

    k = k_start
    # The fields of the state frame that are plant outputs rather than plant
    # states. Before the first step there is no output to report.
    last = {"a_mps2": 0.0, "i_batt_a": 0.0, "v_batt_v": 0.0, "p_aux_w": 0.0}
    err_lead_in = 0.0
    err_window: list[float] = []
    err_recovery: list[float] = []
    i_lead_in = 0.0
    i_window = 0.0
    i_recovery = 0.0
    t_window: list[float] = []
    t_recovery: list[float] = []
    silent_frames = 0
    diag_first = None
    diag_last = None

    while k <= k_stop:
        item = link.recv(timeout_s=0.5)
        if item is None:
            raise SystemExit(
                f"link went quiet at k={k}, "
                f"{(k - k_start) * CTRL_PERIOD_S:.2f} s into the blackout at "
                f"{k_onset * CTRL_PERIOD_S:.1f} s; is the firmware running?")
        ftype, seq, t_us, payload = item

        if ftype is FrameType.STEP_REQ:
            if k_onset <= k < k_end_black:
                # The host-side fault: do not answer, so the board's most
                # recent state ages past STALE_LIMIT_STEPS.
                silent_frames += 1
                continue
            link.send(pack_state(seq, t_us, [
                state.v_mps, last["a_mps2"], state.battery.soc_frac,
                last["i_batt_a"], last["v_batt_v"], T_AMBIENT_C,
                float(grade_all[k]), last["p_aux_w"],
                float(v_ref_all[k]), float(a_ref_all[k]),
            ]))

        elif ftype is FrameType.ACTUATION:
            act = unpack_actuation(payload)
            # Error against the true reference, taken on the speed that
            # produced this command, before the plant advances past it.
            v_true = state.v_mps
            e = abs(float(v_ref_all[k]) - v_true)

            out = plant.step(
                state,
                torque_nm=float(act["torque_nm"]),
                regen_blend=float(act["regen_blend"]),
                p_limit_w=float(act["p_limit_w"]),
                grade_rad=float(grade_all[k]),
                t_ambient_c=T_AMBIENT_C,
                dt_s=CTRL_PERIOD_S,
            )
            i_abs = abs(float(out.i_batt_a))
            tq = float(act["torque_nm"])

            # Phase-scoped, deliberately. A peak taken over the whole span is
            # dominated by whatever the drive cycle was already doing during
            # the lead-in, which is identical in both modes and therefore
            # cannot separate them. scripts/predict_a4.py takes its peak
            # current that way, which is why its section 3 reports the two
            # modes as indistinguishable on current.
            if k < k_onset:
                err_lead_in = max(err_lead_in, e)
                i_lead_in = max(i_lead_in, i_abs)
            elif k < k_end_black:
                err_window.append(e)
                i_window = max(i_window, i_abs)
                t_window.append(tq)
            else:
                err_recovery.append(e)
                i_recovery = max(i_recovery, i_abs)
                t_recovery.append(tq)

            state = out.state
            last = {"a_mps2": float(out.a_mps2),
                    "i_batt_a": float(out.i_batt_a),
                    "v_batt_v": float(out.v_batt_v),
                    "p_aux_w": float(out.p_aux_w)}
            k += 1

        elif ftype is FrameType.DIAG:
            stats, _ = unpack_diag(payload)
            if diag_first is None:
                diag_first = dict(stats)
            diag_last = dict(stats)

    peak_window = max(err_window) if err_window else 0.0
    peak_recovery = max(err_recovery) if err_recovery else 0.0
    return {
        "onset_s": k_onset * CTRL_PERIOD_S,
        "v_ref_at_onset_mps": float(v_ref_all[k_onset]),
        "err_peak_before_blackout_mps": err_lead_in,
        "err_peak_window_mps": peak_window,
        "err_peak_recovery_mps": peak_recovery,
        "err_peak_mps": max(peak_window, peak_recovery),
        "i_peak_lead_in_a": i_lead_in,
        "i_peak_window_a": i_window,
        "i_peak_recovery_a": i_recovery,
        "torque_at_window_end_nm": t_window[-1] if t_window else 0.0,
        "torque_peak_recovery_nm": max((abs(t) for t in t_recovery), default=0.0),
        "silent_step_reqs": silent_frames,
        "diag_first": diag_first,
        "diag_last": diag_last,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/cu.usbmodem1101")
    ap.add_argument("--baud", type=int, default=921600)
    ap.add_argument("--params", default="data/i3_params.json")
    ap.add_argument("--cycle", default="us06")
    ap.add_argument("--onsets", type=int, default=8,
                    help="blackout onsets swept across the cycle")
    ap.add_argument("--onset-s", type=float, default=None,
                    help="a single onset, instead of a sweep")
    ap.add_argument("--blackout-s", type=float, default=BLACKOUT_S)
    ap.add_argument("--lead-in-s", type=float, default=LEAD_IN_S)
    ap.add_argument("--recovery-s", type=float, default=RECOVERY_S)
    ap.add_argument("--no-reset", action="store_true")
    ap.add_argument("--fallback-off", action="store_true",
                    help="score a -DFALLBACK_ENABLED=0 build (ablation A4)")
    ap.add_argument("--out-json", default="docs/week9-a4-closed.json")
    args = ap.parse_args()

    if not args.no_reset:
        reset_and_reexec(args.port)

    cycle = load_cycle(args.cycle, dt_s=CTRL_PERIOD_S)
    v_ref_all = np.asarray(cycle.v_ref_mps, dtype=float)
    a_ref_all = np.gradient(v_ref_all, cycle.dt_s)
    grade_all = np.asarray(cycle.grade_rad, dtype=float)
    span_s = len(v_ref_all) * CTRL_PERIOD_S

    lead_in_k = int(round(args.lead_in_s / CTRL_PERIOD_S))
    black_k = int(round(args.blackout_s / CTRL_PERIOD_S))
    recovery_k = int(round(args.recovery_s / CTRL_PERIOD_S))

    # The onset is swept rather than placed once. A single onset can be chosen
    # to flatter either mode: an outage during a cruise costs almost nothing,
    # one during hard acceleration costs a great deal. predict_a4.py sweeps 20
    # onsets per cycle for the same reason, and a hardware run reported at one
    # onset could not be compared with it.
    lo = args.lead_in_s + 1.0
    hi = span_s - (args.blackout_s + args.recovery_s) - 1.0
    if args.onset_s is not None:
        onsets = [args.onset_s]
    else:
        if hi <= lo:
            raise SystemExit(f"{args.cycle} is too short for these windows")
        onsets = [float(x) for x in np.linspace(lo, hi, args.onsets)]

    params = params_from_json(args.params)
    plant = Plant(params)
    arrays = (v_ref_all, a_ref_all, grade_all)

    mode = "handling off (A4)" if args.fallback_off else "handling on"
    print(f"closed-loop A4 on {args.port}, {mode}")
    print(f"  cycle {args.cycle} ({span_s:.0f} s), blackout "
          f"{args.blackout_s:.1f} s, lead-in {args.lead_in_s:.0f} s, "
          f"{len(onsets)} onset(s)")

    rows: list[dict] = []
    with SerialLink(args.port, args.baud) as link:
        for i, onset in enumerate(onsets, 1):
            k_onset = int(round(onset / CTRL_PERIOD_S))
            if k_onset - lead_in_k < 0 or \
                    k_onset + black_k + recovery_k >= len(v_ref_all):
                print(f"  onset {onset:.1f} s does not fit, skipped")
                continue
            r = run_blackout(link, cycle_arrays=arrays, plant=plant,
                             k_onset=k_onset, lead_in_k=lead_in_k,
                             black_k=black_k, recovery_k=recovery_k)
            rows.append(r)
            print(f"  [{i}/{len(onsets)}] onset {onset:6.1f} s  "
                  f"v_ref {r['v_ref_at_onset_mps']:5.2f}  "
                  f"settled {r['err_peak_before_blackout_mps']:.3f}  "
                  f"peak err {r['err_peak_mps']:6.3f} m/s  "
                  f"I_rec {r['i_peak_recovery_a']:6.1f} A")

    if not rows:
        raise SystemExit("no blackout completed")

    def summarise(key: str) -> dict:
        vals = sorted(r[key] for r in rows)
        return {"median": float(np.median(vals)), "worst": float(vals[-1]),
                "best": float(vals[0])}

    peak = summarise("err_peak_mps")
    i_rec = summarise("i_peak_recovery_a")
    settled = max(r["err_peak_before_blackout_mps"] for r in rows)

    print(f"\n  over {len(rows)} blackouts")
    print(f"  lead-in settled to        {settled:.3f} m/s worst")
    print(f"  peak error   median       {peak['median']:.3f} m/s")
    print(f"  peak error   worst        {peak['worst']:.3f} m/s")
    print(f"  recovery current median   {i_rec['median']:.1f} A")
    print(f"  recovery current worst    {i_rec['worst']:.1f} A")

    # Counters, across the whole session rather than per blackout: the
    # firmware's counters are cumulative and are not reset between them.
    delta: dict = {}
    checks: dict = {}
    first = rows[0]["diag_first"]
    final = rows[-1]["diag_last"]
    if first and final:
        delta = {c: final[c] - first[c] for c in COUNTERS}
        print("\ncounter                 delta over the session")
        for c in COUNTERS:
            print(f"  {c:22} {delta[c]:>8}")
        for c, (lo_b, hi_b) in expectations(args.fallback_off).items():
            if c not in SCORED:
                continue
            ok = delta[c] >= lo_b and (hi_b is None or delta[c] <= hi_b)
            checks[c] = bool(ok)
            bound = f"== {lo_b}" if hi_b == lo_b else f">= {lo_b}"
            print(f"  {c:22} expected {bound:<8} got {delta[c]:<8} "
                  f"{'ok' if ok else 'FAIL'}")

    out_path = Path(args.out_json)
    out_path.write_text(json.dumps({
        "mode": mode,
        "fallback_enabled": not args.fallback_off,
        "ablation": "A4" if args.fallback_off else None,
        "port": args.port,
        "cycle": args.cycle,
        "cycle_span_s": span_s,
        "blackout_s": args.blackout_s,
        "lead_in_s": args.lead_in_s,
        "recovery_s": args.recovery_s,
        "ctrl_period_s": CTRL_PERIOD_S,
        "n_blackouts": len(rows),
        "worst_pre_blackout_err_mps": settled,
        "err_peak_mps": peak,
        "i_peak_recovery_a": i_rec,
        "delta": delta,
        "checks": checks,
        "verdict": all(checks.values()) if checks else None,
        "blackouts": rows,
    }, indent=2) + "\n")
    print(f"\nwrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
