"""What a missed deadline costs when the handling is switched off, predicted.

Ablation A4 turns the deadline-miss handling off and asks what that costs in
control quality (claim C5). The measurement needs the board. This predicts the
answer first, on the host, so that the hardware run is checked against a number
that was written down before it.

That order is this project's convention and it earned its place: the DP optimum
predicted ablation A3 null, with a reason, before SAC was ever trained, and the
five-seed campaign then agreed. A prediction made afterwards would be worth
nothing.

What is modelled is the firmware's control task, not the host simulator's. The
loop below mirrors `firmware/main/tasks.c` step for step, including the detail
that matters most here: when the host stops answering, the control task keeps
the *whole* state frame it last received. The speed measurement goes stale, and
so do the reference, the reference acceleration and the grade -- so the
feedforward is stale too, not only the feedback. Modelling a stale `v_meas`
alone would understate the cost.

Two modes, differing exactly as the firmware's `#if FALLBACK_ENABLED` does:

  handling on   after STALE_LIMIT_STEPS consecutive silent steps, torque ramps
                out at LIMP_RAMP_NM per step and the integrator is frozen
  handling off  the PID keeps running on the frozen state frame, integrating
                against an error it cannot refresh

The blackout onset is swept across each cycle rather than placed once, because
a single onset can be chosen to flatter either mode: a blackout during a
constant-speed cruise costs almost nothing and one during hard acceleration
costs a great deal. What is reported is the distribution over onsets.

    PYTHONPATH="src:." python3 scripts/predict_a4.py
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path

import numpy as np

from evpil.control.cycles import load_cycle
from evpil.control.pid import (
    PidState, feedforward_torque_nm, pid_step,
)
from evpil.control.rule_ems import EmsAction
from evpil.control.sim import DEFAULT_GAINS
from evpil.plant.motor import clamp_torque
from evpil.plant.params import VehicleParams
from evpil.plant.plant import Plant
from scripts.identify_params import params_from_json

# Mirrored from firmware/main/tasks.h. Duplicated constants are how two
# implementations drift, so the parity test reads these back out of the header.
CTRL_PERIOD_S = 0.010
STALE_LIMIT_STEPS = 5
LIMP_RAMP_NM = 10.0

# The host-side fault the hardware campaign injects is 1.0 s of silence at
# 100 Hz. That single duration is not enough to answer A4, which is why it is
# swept: the limp path trades tracking for safety, so how long the link stays
# down decides which way the trade goes.
BLACKOUT_S = 1.0
DURATIONS_S = (0.2, 0.5, 1.0, 2.0, 5.0, 10.0)
RECOVERY_S = 2.0

# Each blackout is simulated from a lead-in before its onset rather than from
# the start of the cycle. Running 1800 s of WLTC to study three seconds of it
# costs about seventy times what the question needs, and the lead-in reaches
# the same place: the plant starts on the reference speed and the PID settles
# long before the blackout. 15 s is far more than this loop needs to settle --
# its derivative filter is 0.05 s and its integrator clamp is reached in well
# under a second -- and the settling is checked rather than assumed, by
# requiring the pre-blackout tracking error to be small.
LEAD_IN_S = 15.0


def run_blackout(
    params: VehicleParams,
    cycle,
    *,
    onset_s: float,
    blackout_s: float,
    handling: bool,
    action: EmsAction,
    soc0: float = 0.80,
    t_ambient_c: float = 12.0,
) -> dict:
    """One cycle with a single host blackout, mirroring the firmware loop."""
    gains = DEFAULT_GAINS
    plant = Plant(params)
    pid = PidState()

    dt = cycle.dt_s
    v_ref_all = cycle.v_ref_mps
    a_ref_all = np.gradient(v_ref_all, dt)
    n = len(v_ref_all)

    k0 = int(round(onset_s / dt))
    k1 = k0 + int(round(blackout_s / dt))
    k2 = k1 + int(round(RECOVERY_S / dt))
    if k2 >= n:
        return {}
    k_start = max(0, k0 - int(round(LEAD_IN_S / dt)))

    state = plant.reset(soc0, t_ambient_c, 20.0)
    # Start on the reference rather than from rest, so the lead-in settles the
    # loop instead of spending itself accelerating from zero.
    state = replace(state, v_mps=float(v_ref_all[k_start]))

    torque_cmd = 0.0
    stale_run = 0
    err_pre = 0.0
    # The last state frame the control task received.
    held = {"v": float(v_ref_all[k_start]), "v_ref": float(v_ref_all[k_start]),
            "a_ref": float(a_ref_all[k_start]),
            "grade": float(cycle.grade_rad[k_start])}

    err_window = []       # tracking error inside the blackout
    err_recovery = []     # and for RECOVERY_S after it
    torque_window = []
    torque_recovery = []
    integral_at_end = 0.0
    peak_i_a = 0.0
    err_sq = 0.0

    for k in range(k_start, k2 + 1):
        v_true = state.v_mps
        silent = k0 <= k < k1

        if silent:
            stale_run += 1
        else:
            stale_run = 0
            held = {"v": v_true, "v_ref": float(v_ref_all[k]),
                    "a_ref": float(a_ref_all[k]),
                    "grade": float(cycle.grade_rad[k])}

        if handling and stale_run > STALE_LIMIT_STEPS:
            # Limp: ramp torque out, freeze the integrator.
            if torque_cmd > LIMP_RAMP_NM:
                torque_cmd -= LIMP_RAMP_NM
            elif torque_cmd < -LIMP_RAMP_NM:
                torque_cmd += LIMP_RAMP_NM
            else:
                torque_cmd = 0.0
        else:
            ff = feedforward_torque_nm(
                params, v_ref_mps=held["v_ref"], a_ref_mps2=held["a_ref"],
                grade_rad=held["grade"],
            )
            omega = (held["v"] / params.wheel_radius_m) * params.gear_ratio
            limit = abs(clamp_torque(params.motor, params.motor.torque_max_nm,
                                     omega)) or 1e-6
            out = pid_step(gains, pid, v_ref_mps=held["v_ref"],
                           v_meas_mps=held["v"], torque_ff_nm=ff,
                           torque_limit_nm=limit, dt_s=dt)
            pid = out.state
            torque_cmd = out.torque_nm

        step = plant.step(
            state, torque_nm=torque_cmd, regen_blend=action.regen_blend,
            p_limit_w=action.p_limit_w, grade_rad=float(cycle.grade_rad[k]),
            t_ambient_c=t_ambient_c, dt_s=dt,
        )
        state = step.state

        # Error against the true reference, which is what tracking means
        # regardless of what the controller could see at the time.
        e = float(v_ref_all[k]) - v_true
        err_sq += e * e
        if k < k0:
            err_pre = max(err_pre, abs(e))
        peak_i_a = max(peak_i_a, abs(float(step.i_batt_a)))

        if k0 <= k < k1:
            err_window.append(abs(e))
            torque_window.append(torque_cmd)
        elif k1 <= k < k2:
            err_recovery.append(abs(e))
            torque_recovery.append(torque_cmd)
        if k == k1 - 1:
            integral_at_end = pid.integral_nm

    return {
        "onset_s": onset_s,
        "blackout_s": blackout_s,
        "handling": handling,
        "v_ref_at_onset_mps": float(v_ref_all[k0]),
        "err_peak_window_mps": max(err_window) if err_window else 0.0,
        "err_peak_recovery_mps": max(err_recovery) if err_recovery else 0.0,
        "err_peak_mps": max(err_window + err_recovery),
        "rmse_window_mps": float(np.sqrt(err_sq / (k2 + 1 - k_start))),
        "err_peak_before_blackout_mps": err_pre,
        "integral_at_window_end_nm": float(integral_at_end),
        "torque_at_window_end_nm": float(torque_window[-1])
        if torque_window else 0.0,
        "torque_peak_recovery_nm": float(max(abs(t) for t in torque_recovery))
        if torque_recovery else 0.0,
        "peak_batt_current_a": peak_i_a,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--params", default="data/i3_params.json")
    ap.add_argument("--cycles", nargs="+",
                    default=["us06", "udds", "hwfet", "wltc3b"])
    ap.add_argument("--onsets", type=int, default=20,
                    help="blackout onsets swept across each cycle")
    ap.add_argument("--out-json", default="docs/week9-a4-prediction.json")
    args = ap.parse_args()

    params = params_from_json(args.params)
    # The energy action is held fixed. A4 is about the tracking loop, and
    # letting the outer action vary would mix a second effect into it.
    action = EmsAction(regen_blend=1.0, p_limit_w=60000.0, aux_derate=0.0)

    rows: list[dict] = []
    for name in args.cycles:
        try:
            cycle = load_cycle(name, dt_s=CTRL_PERIOD_S)
        except (FileNotFoundError, KeyError, ValueError) as exc:
            print(f"  {name}: not loaded ({exc}), skipped")
            continue
        span = len(cycle.v_ref_mps) * cycle.dt_s
        print(f"\n{name}: {span:.0f} s")
        for blackout_s in DURATIONS_S:
            usable = span - (blackout_s + RECOVERY_S) - 1.0
            if usable <= 0:
                continue
            onsets = np.linspace(usable * 0.05, usable * 0.95, args.onsets)
            for onset in onsets:
                for handling in (True, False):
                    r = run_blackout(params, cycle, onset_s=float(onset),
                                     blackout_s=blackout_s,
                                     handling=handling, action=action)
                    if r:
                        r["cycle"] = name
                        rows.append(r)

    if not rows:
        print("no runs completed; are the cycle files built?")
        return 1

    def med(rs, key):
        return float(np.median([r[key] for r in rs])) if rs else float("nan")

    def wrst(rs, key):
        return float(np.max([r[key] for r in rs])) if rs else float("nan")

    print(f"\n{len(rows) // 2} paired blackouts across "
          f"{len(set(r['cycle'] for r in rows))} cycles.\n")
    print("Peak |speed error| against the true reference, m/s. 'on' is the "
          "shipped\nfirmware; 'off' is ablation A4.\n")
    print(f"  {'blackout':>9}  {'on median':>10} {'off median':>11} "
          f"{'on worst':>9} {'off worst':>10}   verdict")

    by_duration = {}
    for d in DURATIONS_S:
        on = [r for r in rows if r["handling"] and r["blackout_s"] == d]
        off = [r for r in rows if not r["handling"] and r["blackout_s"] == d]
        if not on or not off:
            continue
        on_m, off_m = med(on, "err_peak_mps"), med(off, "err_peak_mps")
        on_w, off_w = wrst(on, "err_peak_mps"), wrst(off, "err_peak_mps")
        verdict = ("median costs, tail saves" if off_m < on_m < on_w
                   and off_w > on_w else
                   "handling costs tracking" if off_m < on_m else
                   "handling saves tracking")
        print(f"  {d:>8.1f}s  {on_m:>10.3f} {off_m:>11.3f} "
              f"{on_w:>9.3f} {off_w:>10.3f}   {verdict}")
        by_duration[str(d)] = {
            "n_pairs": len(on),
            "on_median_peak_err_mps": on_m, "off_median_peak_err_mps": off_m,
            "on_worst_peak_err_mps": on_w, "off_worst_peak_err_mps": off_w,
            "on_worst_torque_recovery_nm": wrst(on, "torque_peak_recovery_nm"),
            "off_worst_torque_recovery_nm": wrst(off,
                                                 "torque_peak_recovery_nm"),
            "on_worst_peak_current_a": wrst(on, "peak_batt_current_a"),
            "off_worst_peak_current_a": wrst(off, "peak_batt_current_a"),
        }

    # The lead-in is only long enough if the loop is actually settled when the
    # blackout starts. If it is not, every number above is measuring the
    # lead-in rather than the ablation, so this is checked, not assumed.
    pre = wrst(rows, "err_peak_before_blackout_mps")
    print(f"\n  worst tracking error before any blackout: {pre:.4f} m/s "
          f"({'settled' if pre < 0.10 else 'NOT SETTLED -- lengthen LEAD_IN_S'})")

    def first_crossing(med_or_worst: str) -> float | None:
        for d in DURATIONS_S:
            e = by_duration.get(str(d))
            if not e:
                continue
            if e[f"off_{med_or_worst}_peak_err_mps"] > \
                    e[f"on_{med_or_worst}_peak_err_mps"]:
                return d
        return None

    crossover = first_crossing("median")
    crossover_worst = first_crossing("worst")
    print(f"\n  median case: "
          + (f"the handling starts paying at a {crossover:.1f} s outage"
             if crossover else
             "the handling never pays. Over every duration tried, holding "
             "the last\n               command tracked the reference better "
             "than limping did."))
    print(f"  worst case:  "
          + (f"the handling starts paying at a {crossover_worst:.1f} s outage"
             if crossover_worst else
             "the handling never pays, in the tail either."))
    print("\n  Read together, that is what a safety mechanism looks like: it\n"
          "  spends tracking in the ordinary case to bound the bad one. The\n"
          "  median says limping is a cost; the worst case is where it earns\n"
          "  the cost back, if it earns it back at all.")

    out = Path(args.out_json)
    out.write_text(json.dumps({
        "constants": {"ctrl_period_s": CTRL_PERIOD_S,
                      "stale_limit_steps": STALE_LIMIT_STEPS,
                      "limp_ramp_nm": LIMP_RAMP_NM,
                      "recovery_s": RECOVERY_S},
        "durations_s": list(DURATIONS_S),
        "n_paired_blackouts": len(rows) // 2,
        "crossover_median_s": crossover,
        "crossover_worst_s": crossover_worst,
        "worst_pre_blackout_err_mps": pre,
        "lead_in_s": LEAD_IN_S,
        "by_duration": by_duration,
        "runs": rows,
    }, indent=2) + "\n")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
