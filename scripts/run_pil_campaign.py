"""The week-10 PIL campaign: six scenario axes x two controllers x three seeds.

The last piece of hardware work the plan lists. `docs/hardware-pending.md`
item 3 calls it "work rather than a blocker", and this is that work.

What it is, and what it is not. Ablation A4 asks what a *fault* costs; this
asks what ordinary variation costs. The board runs the real control stack at
100 Hz, the host runs the validated plant of `docs/g2-plant-validation.md`
stepped by the torque the board just commanded, and the reference is a drive
cycle. Six axes from spec 6.5 are swept across three levels each, both
controllers, one seed per level.

**The controller is a compile-time choice, not a runtime one.** `ems_task`
selects the SAC actor or the rule manager on `HAVE_SAC_ACTOR`, which
`scripts/arduino_build.sh` sets from the presence of
`firmware/main/sac_actor_weights.h`. There is no command frame for it: the
protocol carries STATE, ACTUATION, STEP_REQ and DIAG and nothing else. So a
campaign that interleaved the arms would need a reflash per run. This script
therefore runs one arm per invocation, selected by `--controller`, and the
caller is responsible for having flashed the matching image. The recorded
`actor_steps` delta is the check that the caller did: the actor image answers
outer steps with the policy, the rule image cannot and reports zero.

Usage, per arm:

    ./scripts/arduino_build.sh --flash -DFAULT_INJECT=0 -DFALLBACK_ENABLED=1
    PYTHONPATH="src:." python3 scripts/run_pil_campaign.py \
        --port /dev/cu.usbmodem101 --controller actor \
        --out-json docs/week10-pil-actor.json

Energy is reported on two scales and the comparable one is
`equivalent_wh_per_km`, which charges shed cabin heat back at what it saved.
Raw Wh/km rewards a controller for turning the heating off, which is not
energy management. `evpil.control.sim.Result.equivalent_wh` sets that
convention for the offline arms and this mirrors it, so the on-device numbers
land on the same scale as week 7's and week 8's.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import replace
from pathlib import Path

import numpy as np

from evpil.control.cycles import load_cycle
from evpil.control.scenarios import (
    AXES, NOISE_SIGMA, ScenarioLevel, scenario_runs,
)
from evpil.link import SerialLink, reset_and_reexec
from evpil.plant.auxiliary import aux_power_w
from evpil.plant.plant import Plant
from evpil.protocol import (
    STATE_FIELDS, FrameType, pack_state, unpack_actuation, unpack_diag,
)
from scripts.identify_params import params_from_json

# Mirrored from firmware/main/tasks.h, as every other campaign script mirrors
# it. The parity test reads the constant back out of the header.
CTRL_PERIOD_S = 0.010

# Held fixed across the campaign so that the scenario axes are the only thing
# moving. Ambient is the same 12 C ablation A4 used, which is cold enough for
# the auxiliary load to be a real term rather than a rounding error -- without
# that the auxiliary-derate dimension of the action would have nothing to act
# on and the comparable energy scale would collapse onto the raw one.
T_AMBIENT_C = 12.0
T_BATT_C = 20.0

# The counters a run is entitled to read. `dropped_frames` is composed exactly
# as scripts/run_g3.py composes it, so a campaign row can be compared with the
# G3 result rather than being a second, quietly different definition.
DROPPED_PARTS = ("rx_timeouts", "rx_bad", "stale_steps")


def scaled_cycle(
    name: str, *, aggression: float, grade_offset_rad: float, dt_s: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The reference for one scenario: (v_ref, a_ref, grade).

    Driver aggression is a time-scaling. The same speeds arrive in the same
    order, sooner, so accelerations scale with the factor and the cycle
    finishes earlier. Scaling the speeds instead would be a different cycle
    rather than a different driver, and the tracking error would then be
    measured against a trajectory no regulation defines.
    """
    cycle = load_cycle(name, dt_s=dt_s)
    v = np.asarray(cycle.v_ref_mps, dtype=float)
    g = np.asarray(cycle.grade_rad, dtype=float) + grade_offset_rad

    if aggression != 1.0:
        n_new = int(len(v) / aggression)
        src = np.arange(len(v), dtype=float)
        idx = np.arange(n_new, dtype=float) * aggression
        v = np.interp(idx, src, v)
        g = np.interp(idx, src, g)

    a = np.gradient(v, dt_s)
    return v, a, g


def apply_noise(values: dict, *, scale: float, rng: np.random.Generator) -> dict:
    """Corrupt the measured channels; leave the reference alone.

    `v_ref_mps` and `a_ref_mps2` are what the controller is tracking, not a
    measurement of the vehicle. Adding noise to them would move the target,
    which is a different experiment: the tracking error would then include
    error the controller did not make.
    """
    out = dict(values)
    for channel, sigma in NOISE_SIGMA.items():
        if channel in out:
            out[channel] = float(out[channel] + rng.normal(0.0, sigma * scale))
    return out


def run_one(
    link,
    *,
    scenario: ScenarioLevel,
    controller: str,
    seed: int,
    port: str,
    max_steps: int | None = None,
    sleep=time.sleep,
    params=None,
    progress: bool = False,
) -> dict:
    """One cell of the campaign, from the first STEP_REQ to the last step."""
    if params is None:
        params = params_from_json("data/i3_params.json")
    plant = Plant(params)
    rng = np.random.default_rng(seed)

    v_ref, a_ref, grade = scaled_cycle(
        scenario.cycle, aggression=scenario.aggression,
        grade_offset_rad=scenario.grade_offset_rad, dt_s=CTRL_PERIOD_S)
    n = len(v_ref) if max_steps is None else min(max_steps, len(v_ref))

    state = plant.reset(scenario.soc0, T_AMBIENT_C, T_BATT_C)
    # Start on the reference rather than from rest, as every other closed-loop
    # campaign here does, so the opening seconds measure tracking rather than
    # a standing start the cycle did not ask for.
    state = replace(state, v_mps=float(v_ref[0]))

    p_aux_full = aux_power_w(params.aux, T_AMBIENT_C)
    last = {"a_mps2": 0.0, "i_batt_a": 0.0, "v_batt_v": 0.0,
            "p_aux_w": p_aux_full}

    err_sq = 0.0
    err_max = 0.0
    peak_i = 0.0
    regen_ws = 0.0
    net_ws = 0.0
    aux_shed_ws = 0.0
    derate_sum = 0.0
    blend_sum = 0.0
    diag_first: dict | None = None
    diag_last: dict | None = None

    k = 0
    t0 = time.monotonic()
    while k < n:
        item = link.recv(timeout_s=0.5)
        if item is None:
            raise SystemExit(
                f"link went quiet at step {k} of {n} in "
                f"{scenario.axis}/{scenario.level}; is the firmware running?")
        ftype, seq, t_us, payload = item

        if ftype is FrameType.STEP_REQ:
            measured = {
                "v_mps": state.v_mps,
                "a_mps2": last["a_mps2"],
                "soc_frac": state.battery.soc_frac,
                "i_batt_a": last["i_batt_a"],
                "v_batt_v": last["v_batt_v"],
                "t_ambient_c": T_AMBIENT_C,
                "grade_rad": float(grade[k]),
                "p_aux_w": last["p_aux_w"],
                "t_batt_c": state.battery.t_batt_c,
            }
            noisy = apply_noise(measured, scale=scenario.noise_scale, rng=rng)
            noisy["v_ref_mps"] = float(v_ref[k])
            noisy["a_ref_mps2"] = float(a_ref[k])
            if scenario.comm_delay_s > 0.0:
                sleep(scenario.comm_delay_s)
            link.send(pack_state(seq, t_us,
                                 [noisy[f] for f in STATE_FIELDS]))

        elif ftype is FrameType.ACTUATION:
            act = unpack_actuation(payload)
            v_true = state.v_mps
            e = float(v_ref[k]) - v_true

            derate = float(act["aux_derate"])
            p_aux = p_aux_full * (1.0 - derate)
            aux_shed_ws += (p_aux_full - p_aux) * CTRL_PERIOD_S
            derate_sum += derate
            blend_sum += float(act["regen_blend"])

            out = plant.step(
                state,
                torque_nm=float(act["torque_nm"]),
                regen_blend=float(act["regen_blend"]),
                p_limit_w=float(act["p_limit_w"]),
                grade_rad=float(grade[k]),
                t_ambient_c=T_AMBIENT_C,
                dt_s=CTRL_PERIOD_S,
                p_aux_w=p_aux,
            )

            err_sq += e * e
            err_max = max(err_max, abs(e))
            peak_i = max(peak_i, abs(float(out.i_batt_a)))
            regen_ws += max(0.0, -float(out.p_regen_w)) * CTRL_PERIOD_S
            net_ws += float(out.p_batt_w) * CTRL_PERIOD_S

            state = out.state
            last = {"a_mps2": float(out.a_mps2),
                    "i_batt_a": float(out.i_batt_a),
                    "v_batt_v": float(out.v_batt_v),
                    "p_aux_w": float(out.p_aux_w)}
            k += 1
            if progress and k % 6000 == 0:
                print(f"    {k / n * 100:5.1f}%  "
                      f"{time.monotonic() - t0:6.0f} s elapsed", flush=True)

        elif ftype is FrameType.DIAG:
            stats, _ = unpack_diag(payload)
            if diag_first is None:
                diag_first = dict(stats)
            diag_last = dict(stats)

    # `SerialLink.stats` is a property, not a method. Reading it here rather
    # than in main() puts it on the path the fake-link tests exercise; when it
    # lived in main() a mistyped call went unnoticed until it threw at the end
    # of a twenty-three minute run and discarded it.
    host_dropped = int(dict(getattr(link, "stats", {})).get(
        "frames_dropped", 0))

    distance_km = state.distance_m / 1000.0
    energy_wh = net_ws / 3600.0
    aux_shed_wh = aux_shed_ws / 3600.0
    equivalent_wh = energy_wh + aux_shed_wh

    delta = {}
    if diag_first and diag_last:
        for key in diag_last:
            # Levels, not counts. Differencing a running minimum or a mean
            # across the run produces a number with no meaning, and for a
            # minimum it is usually negative, which is how this was caught.
            if key in ("boot_reason", "ctrl_wcet_us", "infer_wcet_us",
                       "rtt_max_us", "period_min_us", "period_max_us",
                       "actor_wcet_us", "stale_worst",
                       "p_limit_min_w", "p_limit_mean_w", "p_limit_max_w"):
                delta[key] = int(diag_last[key])
            else:
                delta[key] = int(diag_last[key]) - int(diag_first[key])

    return {
        "scenario": scenario.axis,
        "level": scenario.level,
        "controller": controller,
        "seed": seed,
        "port": port,
        "cycle": scenario.cycle,
        "grade_offset_rad": scenario.grade_offset_rad,
        "soc0": scenario.soc0,
        "noise_scale": scenario.noise_scale,
        "comm_delay_s": scenario.comm_delay_s,
        "aggression": scenario.aggression,
        "steps": k,
        "duration_s": k * CTRL_PERIOD_S,
        "wall_s": time.monotonic() - t0,
        "tracking_rmse_mps": float(np.sqrt(err_sq / k)) if k else float("nan"),
        "tracking_max_mps": float(err_max),
        "distance_km": float(distance_km),
        "energy_wh": float(energy_wh),
        "aux_shed_wh": float(aux_shed_wh),
        "equivalent_wh": float(equivalent_wh),
        "wh_per_km": float(energy_wh / distance_km) if distance_km > 0
                     else float("nan"),
        "equivalent_wh_per_km": float(equivalent_wh / distance_km)
                                if distance_km > 0 else float("nan"),
        "regen_wh": float(regen_ws / 3600.0),
        "peak_current_a": float(peak_i),
        "soc_start": float(scenario.soc0),
        "soc_end": float(state.battery.soc_frac),
        "mean_aux_derate": float(derate_sum / k) if k else float("nan"),
        "mean_regen_blend": float(blend_sum / k) if k else float("nan"),
        "ctrl_late": int(delta.get("ctrl_late", -1)),
        "stale_steps": int(delta.get("stale_steps", -1)),
        "actor_steps": int(delta.get("actor_steps", -1)),
        "actor_wcet_us": int(delta.get("actor_wcet_us", -1)),
        "ems_fallback_steps": int(delta.get("ems_fallback_steps", -1)),
        "loop_count": int(delta.get("loop_count", -1)),
        "host_frames_dropped": host_dropped,
        "dropped_frames": int(sum(delta.get(p, 0)
                                  for p in DROPPED_PARTS)) + host_dropped,
        "diag_delta": delta,
    }


def check_arm(result: dict) -> None:
    """Refuse to file a run under a controller the board was not running.

    The arm is a compile-time choice with no runtime signature in the frame
    protocol, so the only thing standing between "flashed the wrong image" and
    a campaign table that silently compares an arm with itself is this check.
    `actor_steps` counts outer steps the policy answered: the actor image
    cannot report zero over a whole cycle, and the rule image cannot report
    anything else, because the counter is only incremented inside the
    `HAVE_SAC_ACTOR` branch.

    This is the class of mistake the CMake cache produced once already, where
    a baseline build silently came out as the ablation. Cheap to check, and
    the alternative is three hours of runs that mean nothing.
    """
    steps = result["actor_steps"]
    controller = result["controller"]
    if controller == "actor" and steps <= 0:
        raise SystemExit(
            f"--controller actor but the board reported actor_steps={steps} "
            f"over {result['steps']} control steps. The flashed image has no "
            f"policy in it: check that firmware/main/sac_actor_weights.h was "
            f"present when scripts/arduino_build.sh ran.")
    if controller == "rule" and steps > 0:
        raise SystemExit(
            f"--controller rule but the board reported actor_steps={steps}. "
            f"The flashed image is the actor build; these runs would be the "
            f"learned policy filed under the rule manager.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/cu.usbmodem1101")
    ap.add_argument("--baud", type=int, default=921600)
    ap.add_argument("--params", default="data/i3_params.json")
    ap.add_argument("--controller", required=True, choices=("rule", "actor"))
    ap.add_argument("--axis", action="append", default=None,
                    help="restrict to one axis; repeatable")
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--no-reset", action="store_true",
                    help="set by the re-exec; the board was just reset")
    ap.add_argument("--max-steps", type=int, default=None,
                    help="truncate each run; for smoke-testing this script "
                         "against the board without spending a whole cycle. "
                         "Results from a truncated run are not a campaign and "
                         "may not be written to the campaign file.")
    args = ap.parse_args()

    if args.max_steps is not None and "week10-pil-campaign" in args.out_json:
        raise SystemExit(
            "--max-steps produces truncated runs; refusing to write them to "
            "the campaign file. Point --out-json somewhere else.")

    if args.axis:
        unknown = set(args.axis) - set(AXES)
        if unknown:
            raise SystemExit(f"unknown axis: {sorted(unknown)}")

    runs = [r for r in scenario_runs(controllers=(args.controller,))
            if not args.axis or r.axis in args.axis]
    params = params_from_json(args.params)

    out_path = Path(args.out_json)
    results: list[dict] = []
    if out_path.exists():
        results = json.loads(out_path.read_text())["runs"]

    def key_of(d) -> tuple:
        return (d["scenario"], d["level"], d["controller"], d["seed"])

    done = {key_of(r) for r in results}
    pending = [r for r in runs
               if (r.axis, r.level, r.controller, r.seed) not in done]

    if not pending:
        print(f"nothing left to run; {len(results)} runs already in {out_path}")
        return 0

    # One board reset per run, and the reset is why this runs a single cell per
    # process. `reset_and_reexec` resets the chip and then replaces the process
    # image, because resetting and reopening the port from the same process
    # reads zero bytes on this machine -- link.py documents the measurement.
    # So the campaign advances one cell per exec, resuming from the file it
    # already wrote. Without a reset between cells the board's PID would carry
    # integral state across a cycle boundary and a run would depend on the one
    # before it, and on the order the axes happen to be listed in.
    if not args.no_reset:
        print(f"PIL campaign: {args.controller} arm, "
              f"{len(pending)} of {len(runs)} runs left, port {args.port}",
              flush=True)
        reset_and_reexec(args.port, drop_flag="--no-reset",
                         add_flag="--no-reset")

    run = pending[0]
    i = len(runs) - len(pending) + 1
    print(f"\n[{i}/{len(runs)}] {run.axis}/{run.level} seed {run.seed}",
          flush=True)

    with SerialLink(args.port, args.baud) as link:
        result = run_one(link, scenario=run.scenario,
                         controller=run.controller, seed=run.seed,
                         port=args.port, params=params, progress=True,
                         max_steps=args.max_steps)

    check_arm(result)
    results = [r for r in results if key_of(r) != key_of(result)]
    results.append(result)

    # flush=True is load-bearing: os.execv below replaces the process image
    # without flushing Python's stdout buffer, and stdout is block-buffered
    # when redirected to a file, so an unflushed summary line is simply lost.
    # The whole actor arm ran once with a log of progress percentages and no
    # results in it.
    print(f"    rmse {result['tracking_rmse_mps']:.4f} m/s   "
          f"equiv {result['equivalent_wh_per_km']:.2f} Wh/km   "
          f"ctrl_late {result['ctrl_late']}   "
          f"dropped {result['dropped_frames']}   "
          f"actor_steps {result['actor_steps']}", flush=True)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(
        {"port": args.port, "runs": results}, indent=1) + "\n")

    if len(pending) > 1:
        # Reset for the next cell, which restarts this script; it will reload
        # the file just written and skip everything in it.
        reset_and_reexec(args.port, drop_flag="--no-reset",
                         add_flag="--no-reset")

    print(f"\nwrote {out_path}  ({len(results)} runs)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
