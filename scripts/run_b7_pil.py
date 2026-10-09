"""Injected sensor faults on the board: B6, B7 and B7 with the rule monitor.

The cases are a subset of the registered test split
(`evpil.control.sensor_eval`): US06, the five named faults, two onsets, the
white and wander acceleration cases, at the noise floor and ten times it, and
the clean cycle under both acceleration cases. The laptop simulates the
vehicle and corrupts the two sensor channels exactly as the simulation does;
the estimator and the detector run on the chip.

One cell per process, with a board reset before each, as
scripts/run_pil_campaign.py does and for its reason: the board's PID and
estimator would otherwise carry state from one run into the next.

What the board reports about its detector is in the DIAG frame, every
500 ms: the number of alarms, the control loop the last one was raised on,
and the steps spent flagged. Detection delay is that loop against the loop
the fault started on, good to a few steps; flag state is known to 500 ms.

    PYTHONPATH="src:." python3 scripts/run_b7_pil.py --port /dev/cu.usbmodem101 \\
        --speed-est 5 --out-json docs/week13-b7-pil-b7.json

MEASURED on the board. Keep the laptop quiet while it runs.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np

from evpil.control import sensor_eval as se
from evpil.control.cycles import load_cycle
from evpil.control.scenarios import NOISE_SIGMA
from evpil.control.speed_estimators import SpeedFault
from evpil.link import SerialLink, reset_and_reexec
from evpil.plant.auxiliary import aux_power_w
from evpil.plant.plant import Plant
from evpil.protocol import (
    FrameType, STATE_FIELDS, pack_state, unpack_actuation, unpack_diag,
)
from scripts.identify_params import params_from_json
from scripts.run_pil_campaign import (
    CTRL_PERIOD_S, DROPPED_PARTS, T_AMBIENT_C, T_BATT_C,
)

ACCELS = ("white", "wander")
ONSET_INDEX = (2, 5)            # of the eight registered test onsets
DIAG_PERIOD_S = 0.5


def cases(seed_offset: int = 0) -> list[se.Case]:
    """The fault runs, then the clean cycles. `seed_offset` gives the same
    cases other draws of noise and of acceleration wander: a repeat."""
    onsets = sorted({c.onset_s for c in se.fault_cases("test")})
    keep = {onsets[i] for i in ONSET_INDEX}
    named = {f[0] for f in se.FAULTS if f[3]}
    out = [c for c in se.fault_cases("test", accels=ACCELS)
           if c.mass == 1.0 and c.onset_s in keep and c.fault in named]
    out += [c for c in se.clean_cases("test")
            if c.mass == 1.0 and c.accel in ACCELS and c.noise_x == 1.0
            and c.seed == se.SPLIT_SEED0["test"] + 500]
    if seed_offset:
        out = [replace(c, seed=c.seed + seed_offset) for c in out]
    return out


def run_case(link, case: se.Case, params) -> dict:
    full = load_cycle(case.cycle)
    dt = full.dt_s
    assert abs(dt - CTRL_PERIOD_S) < 1e-9
    if case.fault:
        end = min(int((case.onset_s + se.FAULT_S + se.TAIL_S) / dt),
                  len(full.v_ref_mps))
        start = max(0, int((case.onset_s - se.LEAD_S) / dt))
    else:
        start, end = 0, len(full.v_ref_mps)
    err, grade = se.accel_error(case, end, dt)
    err = np.zeros(end) if err is None else err
    v_ref = full.v_ref_mps[start:end]
    a_ref = np.gradient(full.v_ref_mps, dt)[start:end]
    grade, err = grade[start:end], err[start:end]
    n = end - start
    fault, a_step, b_step = None, n, n
    if case.fault:
        _, kind, mag, _ = next(f for f in se.FAULTS if f[0] == case.fault)
        onset = case.onset_s - start * dt
        fault = SpeedFault(kind, onset, mag, duration_s=se.FAULT_S)
        a_step = int(round(onset / dt))
        b_step = min(n, a_step + int(se.FAULT_S / dt))

    plant = Plant(params)
    rng = np.random.default_rng(case.seed)
    state = plant.reset(0.80, T_AMBIENT_C, T_BATT_C)
    state = replace(state, v_mps=float(v_ref[0]))
    p_aux_full = aux_power_w(params.aux, T_AMBIENT_C)
    last = {"a_mps2": 0.0, "i_batt_a": 0.0, "v_batt_v": 0.0,
            "p_aux_w": p_aux_full}
    errs = np.zeros(n)
    net_ws = aux_shed_ws = 0.0
    diags: list[tuple[int, dict]] = []      # (host step, DIAG fields)

    k = 0
    t0 = time.monotonic()
    while k < n:
        item = link.recv(timeout_s=0.5)
        if item is None:
            raise SystemExit(f"link went quiet at step {k} of {n}")
        ftype, seq, t_us, payload = item
        if ftype is FrameType.STEP_REQ:
            measured = {
                "v_mps": state.v_mps, "a_mps2": last["a_mps2"],
                "soc_frac": state.battery.soc_frac,
                "i_batt_a": last["i_batt_a"], "v_batt_v": last["v_batt_v"],
                "t_ambient_c": T_AMBIENT_C, "grade_rad": float(grade[k]),
                "p_aux_w": last["p_aux_w"],
                "t_batt_c": state.battery.t_batt_c,
            }
            noisy = dict(measured)
            for channel, sigma in NOISE_SIGMA.items():
                noisy[channel] = float(noisy[channel] + rng.normal(
                    0.0, sigma * case.noise_x))
            noisy["a_mps2"] += float(err[k])
            if fault is not None:
                noisy["v_mps"] = float(fault.apply(k * dt, noisy["v_mps"]))
            noisy["v_ref_mps"] = float(v_ref[k])
            noisy["a_ref_mps2"] = float(a_ref[k])
            link.send(pack_state(seq, t_us, [noisy[f] for f in STATE_FIELDS]))
        elif ftype is FrameType.ACTUATION:
            act = unpack_actuation(payload)
            errs[k] = abs(float(v_ref[k]) - state.v_mps)
            derate = float(act["aux_derate"])
            p_aux = p_aux_full * (1.0 - derate)
            aux_shed_ws += (p_aux_full - p_aux) * dt
            out = plant.step(
                state, torque_nm=float(act["torque_nm"]),
                regen_blend=float(act["regen_blend"]),
                p_limit_w=float(act["p_limit_w"]), grade_rad=float(grade[k]),
                t_ambient_c=T_AMBIENT_C, dt_s=dt, p_aux_w=p_aux)
            net_ws += float(out.p_batt_w) * dt
            state = out.state
            last = {"a_mps2": float(out.a_mps2),
                    "i_batt_a": float(out.i_batt_a),
                    "v_batt_v": float(out.v_batt_v),
                    "p_aux_w": float(out.p_aux_w)}
            k += 1
        elif ftype is FrameType.DIAG:
            stats, _ = unpack_diag(payload)
            diags.append((k, dict(stats)))

    if len(diags) < 2:
        raise SystemExit("fewer than two DIAG frames in the run")
    first, final = diags[0][1], diags[-1][1]
    host_dropped = int(dict(getattr(link, "stats", {})).get(
        "frames_dropped", 0))
    # The board's loop counter against the host's step counter. The board
    # loops whether or not a frame was dropped, so the offset is taken at
    # each DIAG frame and the one nearest the fault is used.
    offs = [(kk, d["loop_count"] - kk) for kk, d in diags]
    near = min(offs, key=lambda x: abs(x[0] - a_step))[1]
    alarms = []                 # (host step, test) of each new alarm seen
    seen = first["sensor_alarms"]
    for kk, d in diags[1:]:
        if d["sensor_alarms"] != seen:
            alarms.append((int(d["sensor_alarm_loop"] - near),
                           int(d["sensor_alarm_test"]),
                           int(d["sensor_alarms"] - seen)))
            seen = d["sensor_alarms"]
    # Steps flagged inside each DIAG interval.
    flagged = [(k1, d1["sensor_flag_steps"] - d0["sensor_flag_steps"])
               for (k0, d0), (k1, d1) in zip(diags[:-1], diags[1:])]
    after = [s for s, _, _ in alarms if s >= a_step - 5]
    delay = (max(0, after[0] - a_step) * dt) if (case.fault and after) else None
    in_fault = sum(f for kk, f in flagged if a_step < kk <= b_step)
    tail = [f for kk, f in flagged if kk > n - int(1.0 / dt)]
    distance_km = state.distance_m / 1000.0
    return {
        **asdict(case), "steps": n, "wall_s": time.monotonic() - t0,
        "fault_step": a_step if case.fault else None,
        "alarms_seen": alarms,
        "alarms_total": int(final["sensor_alarms"] - first["sensor_alarms"]),
        "alarms_before_onset": int(sum(c for s, _, c in alarms
                                       if s < a_step - 5)),
        "delay_s": delay,
        "flagged_steps_in_fault": int(in_fault),
        "flagged_in_last_second": int(sum(tail)),
        "flagged_steps": int(final["sensor_flag_steps"]
                             - first["sensor_flag_steps"]),
        "peak_err_mps": float(errs[a_step:].max()) if case.fault else None,
        "tracking_rmse_mps": float(np.sqrt(np.mean(errs ** 2))),
        "tracking_max_mps": float(errs.max()),
        "equivalent_wh_per_km": float((net_ws + aux_shed_ws) / 3600.0
                                      / distance_km) if distance_km > 0
                                else None,
        "speed_est_mode": int(final["speed_est_mode"]),
        "actor_steps": int(final["actor_steps"] - first["actor_steps"]),
        "ctrl_late": int(final["ctrl_late"] - first["ctrl_late"]),
        "ctrl_wcet_us": int(final["ctrl_wcet_us"]),
        "dropped_frames": int(sum(final[p] - first[p]
                                  for p in DROPPED_PARTS)) + host_dropped,
        "diag_frames": len(diags),
    }


def key_of(d) -> tuple:
    return (d["cycle"], d["accel"], d["noise_x"], d["seed"], d["fault"],
            d["onset_s"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/cu.usbmodem101")
    ap.add_argument("--baud", type=int, default=921600)
    ap.add_argument("--speed-est", type=int, default=None)
    ap.add_argument("--out-json", default=None)
    ap.add_argument("--limit", type=int, default=None,
                    help="stop after this many cells are in the file")
    ap.add_argument("--seed-offset", type=int, default=0,
                    help="add this to every case's seed: a repeat with "
                         "other noise draws. 100 and up keeps clear of the "
                         "registered test, train and validation seeds only "
                         "below 400")
    ap.add_argument("--no-reset", action="store_true")
    ap.add_argument("--probe", action="store_true",
                    help="run five seconds and print what image the board "
                         "holds; writes nothing")
    args = ap.parse_args()

    if args.probe:
        if not args.no_reset:
            reset_and_reexec(args.port, drop_flag="--no-reset",
                             add_flag="--no-reset")
        full = next(c for c in cases() if not c.fault)
        probe = replace(full, fault="stuck", onset_s=se.LEAD_S + 500.0)
        with SerialLink(args.port, args.baud) as link:
            r = run_case(link, replace(probe, onset_s=se.LEAD_S - 25.0),
                         params_from_json("data/i3_params.json"))
        image = "actor" if r["actor_steps"] > 0 else "rule"
        print(json.dumps({"image": image, "actor_steps": r["actor_steps"],
                          "speed_est_mode": r["speed_est_mode"],
                          "steps": r["steps"]}), flush=True)
        return 0

    todo = cases(args.seed_offset)
    path = Path(args.out_json)
    runs = json.loads(path.read_text())["runs"] if path.exists() else []
    done = {key_of(r) for r in runs}
    pending = [c for c in todo if key_of(asdict(c)) not in done]
    if args.limit is not None:
        pending = pending[:max(0, args.limit - len(runs))]
    if not pending:
        print(f"nothing left; {len(runs)} runs in {path}", flush=True)
        return 0
    if not args.no_reset:
        print(f"B7 PIL: mode {args.speed_est}, {len(pending)} of {len(todo)} "
              f"cells left", flush=True)
        reset_and_reexec(args.port, drop_flag="--no-reset",
                         add_flag="--no-reset")
    case = pending[0]
    params = params_from_json("data/i3_params.json")
    with SerialLink(args.port, args.baud) as link:
        r = run_case(link, case, params)
    if r["speed_est_mode"] != args.speed_est:
        raise SystemExit(f"board reports speed_est_mode {r['speed_est_mode']},"
                         f" expected {args.speed_est}: wrong image")
    if r["actor_steps"] > 0:
        raise SystemExit("board reports actor steps: this is the actor image, "
                         "not the rule-manager one")
    runs.append(r)
    path.write_text(json.dumps({
        "provenance": "MEASURED on the board (ESP32-S3), laptop simulates "
                      "the vehicle", "port": args.port,
        "speed_est_mode": args.speed_est, "config": se.config_hash(),
        "seed_offset": args.seed_offset,
        "runs": runs}, indent=1) + "\n")
    print(f"[{len(runs)}/{len(todo)}] {case.accel} {case.fault or 'clean'} "
          f"{case.noise_x:g}x onset {case.onset_s:.0f}: delay {r['delay_s']} "
          f"peak {r['peak_err_mps']} alarms {r['alarms_total']} late "
          f"{r['ctrl_late']} dropped {r['dropped_frames']}", flush=True)
    if len(pending) > 1:
        reset_and_reexec(args.port, drop_flag="--no-reset",
                         add_flag="--no-reset")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
