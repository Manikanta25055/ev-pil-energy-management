"""The registered sensor-reliability evaluation: cases, splits and criteria.

`docs/2026-10-07-model-advancement-research.md`, sections 7 and 13, ask that
the cases a learned sensor arm is judged on, and the bounds it must meet, be
fixed in executable form before any such arm is trained. This is that form.
Every arm, classical or learned, on the laptop or behind a delay, is run
through `run_fault_case` and `run_clean_case` and scored by `verdict`.

Splits are by cycle, by logged trip and by seed, never by window:

  train  UDDS and WLTC; replayed trips from the i3 training split
  val    HWFET; replayed trips from the i3 validation split
  test   US06; replayed trips from the i3 trips no split has ever used

The sealed i3 test trips are not read here at all.

What changed from the week-11 fault study (`scripts/run_fault_arms.py`): the
acceleration channel is no longer only true acceleration plus white noise.
The other cases are in `ACCEL_CASES`, and their sizes come from the training
trips (`evpil.control.accel_models`).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from typing import Callable

import numpy as np

from evpil.control import accel_models
from evpil.control.cycles import Cycle, load_cycle
from evpil.control.rule_ems import RuleParams, rule_action
from evpil.control.sim import simulate
from evpil.control.speed_estimators import KalmanSpeed, SpeedFault
from evpil.plant.params import VehicleParams

V_FLOOR_MPS = 0.02
A_FLOOR_MPS2 = 0.05
NOISE_X = (1.0, 10.0)
FAULT_S = 5.0
TAIL_S = 8.0
# A fault run starts this long before its onset, already at the cycle's
# speed, rather than at the start of the cycle. The acceleration error is
# still the one the whole cycle would have had at that time.
LEAD_S = 30.0
RAW_I3 = "data/raw/i3"

SPLIT_CYCLES = {"train": ("udds", "wltc3b"), "val": ("hwfet",),
                "test": ("us06",)}
# Chosen by name order from each pool before any arm was run on them.
SPLIT_TRIPS = {"train": ("TripB01", "TripB10", "TripB15", "TripB24"),
               "val": ("TripB03", "TripB08", "TripB12", "TripB29"),
               "test": ("TripA06", "TripA10", "TripA15", "TripA20")}
SPLIT_SEED0 = {"train": 1000, "val": 2000, "test": 0}
ONSETS_PER_CYCLE = {"train": 6, "val": 8, "test": 8}
CLEAN_SEEDS = {"train": 2, "val": 3, "test": 5}

FAULTS = (            # (label, kind, magnitude, named in the criteria)
    ("stuck",       "stuck",   0.0, True),
    ("dropout",     "dropout", 0.0, True),
    ("bias +0.5",   "bias",    0.5, True),
    ("bias -0.5",   "bias",   -0.5, True),
    ("bias +3.0",   "bias",    3.0, True),
    ("drift 0.5/s", "drift",   0.5, False),
)

# (label, kind, parameters). "white" is the week-11 assumption.
ACCEL_CASES = (
    ("white",       "white",  {}),
    ("offset",      "offset", {"bias_mps2": 0.17}),     # worst trip offset
    ("wander",      "wander", {}),                      # training-trip median
    ("wander hard", "wander", {"sd_mps2": 0.20, "tau_s": 15.0}),
    ("slope",       "slope",  {"amplitude_rad": 0.03, "period_s": 120.0}),
    ("replay",      "replay", {}),
)

CRITERIA = {
    "detect_within_s": 0.5,
    "false_alarms_per_hour_below": 1.0,
    "clean_energy_within_frac": 0.002,
    "clean_tracking_within_mps": 0.005,
    "tracking_rmse_below_mps": 0.1,
    "lingering_flags_at_tail": 0,
    "cleared_within_2s_frac_at_least": 0.95,
}


@dataclass(frozen=True)
class Case:
    split: str
    cycle: str
    accel: str
    noise_x: float
    mass: float
    seed: int
    fault: str = ""             # empty for a clean run
    onset_s: float = 0.0


def accel_error(case: Case, n: int, dt_s: float) -> tuple[np.ndarray | None,
                                                           np.ndarray]:
    """The acceleration-channel error of a case and the road grade it
    implies. Only the slope case has a grade."""
    grade = np.zeros(n)
    kind, kw = next((k, p) for label, k, p in ACCEL_CASES
                    if label == case.accel)
    if kind == "white":
        return None, grade
    if kind == "offset":
        sign = 1.0 if case.seed % 2 == 0 else -1.0
        return accel_models.offset(n, sign * kw["bias_mps2"]), grade
    if kind == "wander":
        return accel_models.wander(n, dt_s, seed=case.seed, **kw), grade
    if kind == "slope":
        t = np.arange(n) * dt_s
        grade = kw["amplitude_rad"] * np.sin(2 * np.pi * t / kw["period_s"])
        return accel_models.slope_gravity(grade), grade
    trips = SPLIT_TRIPS[case.split]
    trip = trips[case.seed % len(trips)]
    return accel_models.replay(n, dt_s, f"{RAW_I3}/{trip}.csv",
                               start_s=60.0 * (case.seed // len(trips))), grade


def fault_cases(split: str, *, accels: tuple[str, ...] | None = None,
                noise_x: tuple[float, ...] = NOISE_X,
                onsets_per_cycle: int | None = None) -> list[Case]:
    """Every fault, at every onset, under every acceleration case on the
    nominal car, and under white acceleration noise on a car 10% heavier.

    `onsets_per_cycle` draws more onsets than the registered number, for
    training data. The first ones are the registered ones; an evaluation
    never passes it."""
    out = []
    for cyc_name in SPLIT_CYCLES[split]:
        dur = load_cycle(cyc_name).duration_s
        rng = np.random.default_rng([SPLIT_SEED0[split], len(cyc_name)])
        m = ONSETS_PER_CYCLE[split]
        onsets = (np.linspace(16.0, 580.0, m) if split == "test" else
                  np.sort(rng.uniform(16.0, dur - FAULT_S - TAIL_S - 1.0, m)))
        if onsets_per_cycle is not None:
            if split != "train" or onsets_per_cycle > 400:
                raise ValueError("extra onsets are for training data only")
            onsets = np.concatenate([onsets, rng.uniform(
                16.0, dur - FAULT_S - TAIL_S - 1.0, onsets_per_cycle - m)])
        for label, _, _, _ in FAULTS:
            for accel, mass in ([(a[0], 1.0) for a in ACCEL_CASES]
                                + [("white", 1.1)]):
                if accels is not None and accel not in accels:
                    continue
                for mult in noise_x:
                    for k, onset in enumerate(onsets):
                        out.append(Case(split, cyc_name, accel, mult, mass,
                                        SPLIT_SEED0[split] + k, label,
                                        float(onset)))
    return out


def clean_cases(split: str) -> list[Case]:
    out = []
    for cyc_name in SPLIT_CYCLES[split]:
        for accel, mass in ([(a[0], 1.0) for a in ACCEL_CASES]
                            + [("white", 1.1)]):
            for mult in NOISE_X:
                for s in range(CLEAN_SEEDS[split]):
                    out.append(Case(split, cyc_name, accel, mult, mass,
                                    SPLIT_SEED0[split] + 500 + s))
    return out


def config_hash() -> str:
    blob = json.dumps([V_FLOOR_MPS, A_FLOOR_MPS2, NOISE_X, FAULT_S, TAIL_S, LEAD_S,
                       SPLIT_CYCLES, SPLIT_TRIPS, SPLIT_SEED0,
                       ONSETS_PER_CYCLE, CLEAN_SEEDS, FAULTS, ACCEL_CASES,
                       CRITERIA], sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


_RULES = RuleParams()


def _policy(o):
    return rule_action(_RULES, soc_frac=o.soc_frac, v_mps=o.v_mps)


def _run(nominal: VehicleParams, case: Case, est, cyc: Cycle, err, *,
         fault=None, keep_trace=False, v0_mps=0.0):
    plant = replace(nominal, mass_kg=nominal.mass_kg * case.mass)
    return simulate(plant, cyc, _policy, ff_params=nominal,
                    accel_noise_mps2=case.noise_x * A_FLOOR_MPS2,
                    speed_noise_mps=case.noise_x * V_FLOOR_MPS,
                    seed=case.seed, speed_estimator=est,
                    keep_trace=keep_trace, speed_fault=fault,
                    accel_error_mps2=err, v0_mps=v0_mps)


def simulate_fault_case(nominal: VehicleParams, case: Case, est):
    """Run a fault case with `est` in the loop. Returns the result, the step
    the fault starts and ends on, and the acceleration error that was
    applied (zeros when there was none)."""
    full = load_cycle(case.cycle)
    dt = full.dt_s
    end = min(int((case.onset_s + FAULT_S + TAIL_S) / dt), len(full.v_ref_mps))
    start = max(0, int((case.onset_s - LEAD_S) / dt))
    err, grade = accel_error(case, end, dt)
    cyc = Cycle(name=case.cycle, dt_s=dt, v_ref_mps=full.v_ref_mps[start:end],
                grade_rad=grade[start:end])
    n = end - start
    onset = case.onset_s - start * dt
    _, kind, mag, _ = next(f for f in FAULTS if f[0] == case.fault)
    err = None if err is None else err[start:]
    r = _run(nominal, case, est, cyc, err, keep_trace=True,
             v0_mps=float(cyc.v_ref_mps[0]),
             fault=SpeedFault(kind, onset, mag, duration_s=FAULT_S))
    a = int(round(onset / dt))
    b = min(n, a + int(FAULT_S / dt))
    return r, a, b, (np.zeros(n) if err is None else err)


def simulate_clean_case(nominal: VehicleParams, case: Case, est, *,
                        max_s: float | None = None):
    """Run a clean case with `est` in the loop: the result and the
    acceleration error applied."""
    full = load_cycle(case.cycle)
    dt = full.dt_s
    n = len(full.v_ref_mps)
    if max_s is not None:
        n = min(n, int(max_s / dt))
    err, grade = accel_error(case, n, dt)
    cyc = Cycle(name=case.cycle, dt_s=dt, v_ref_mps=full.v_ref_mps[:n],
                grade_rad=grade)
    r = _run(nominal, case, est, cyc, err)
    return r, cyc, err


def run_fault_case(nominal: VehicleParams, case: Case,
                   make_estimator: Callable[[], object]) -> dict:
    """One fault, five seconds long, then eight seconds of healthy sensor."""
    est = make_estimator()
    r, a, b, _ = simulate_fault_case(nominal, case, est)
    dt = r.trace.t_s[1] - r.trace.t_s[0]
    named = next(f for f in FAULTS if f[0] == case.fault)[3]
    flags = np.asarray(est.flag_history, dtype=bool)
    after = [s for s in est.alarm_steps if s >= a]
    delay = (after[0] - a) * dt if after else None
    caught = delay is not None and delay <= CRITERIA["detect_within_s"]
    # A clear while the fault is still there: the flag was up and came down
    # before the sensor was healthy again.
    false_clear = bool(caught and not flags[after[0]:b].all())
    down = np.flatnonzero(~flags[b:])
    clear_s = float(down[0] * dt) if len(down) else None
    err_abs = np.abs(r.trace.v_ref_mps - r.trace.v_mps)
    return {**asdict(case), "named": named,
            "false_alarms_before": sum(s < a for s in est.alarm_steps),
            "delay_s": delay, "false_clear": false_clear,
            "flagged_share_in_fault": float(flags[a:b].mean()),
            "clear_after_restore_s": clear_s,
            "lingering": bool(flags[-1]),
            "peak_err_mps": float(err_abs[a:].max()),
            "v_ref_at_onset_mps": float(r.trace.v_ref_mps[a]),
            "supervisor": dict(getattr(est, "applied", {}))}


def run_clean_case(nominal: VehicleParams, case: Case,
                   make_estimator: Callable[[], object], *,
                   q_mps: float, q_d_mps2: float) -> dict:
    """A whole cycle with a healthy sensor, beside the filter B5 on the same
    noise. B5 does not read the acceleration channel."""
    est = make_estimator()
    r, cyc, err = simulate_clean_case(nominal, case, est)
    n, dt = len(cyc.v_ref_mps), cyc.dt_s
    base = _run(nominal, case, KalmanSpeed(
        nominal, q_mps=q_mps, r_mps=V_FLOOR_MPS, adaptive=True,
        q_d_mps2=q_d_mps2), cyc, err)
    return {**asdict(case), "hours": n * dt / 3600.0,
            "false_alarms": len(est.alarm_steps),
            "alarm_tests": list(getattr(est, "alarm_tests", [])),
            "flagged_share": float(np.mean(est.flag_history)),
            "equivalent_wh_per_km": r.equivalent_wh_per_km,
            "tracking_rmse_mps": r.tracking_rmse_mps,
            "tracking_max_mps": r.tracking_max_mps,
            "b5_equivalent_wh_per_km": base.equivalent_wh_per_km,
            "b5_tracking_rmse_mps": base.tracking_rmse_mps,
            "supervisor": dict(getattr(est, "applied", {}))}


def verdict(fault_rows: list[dict], clean_rows: list[dict]) -> dict:
    """The registered criteria, overall and per acceleration case. Noise
    floor and ten times it are pooled for faults; false alarms are counted
    at the floor, as the design's criterion is worded, and at 10x beside."""
    c = CRITERIA
    out: dict = {"config": config_hash(), "by_accel": {}}
    groups = sorted({(r["accel"], r["mass"]) for r in fault_rows + clean_rows})
    for accel, mass in groups:
        f = [r for r in fault_rows if (r["accel"], r["mass"]) == (accel, mass)
             and r["named"]]
        cl = [r for r in clean_rows if (r["accel"], r["mass"]) == (accel, mass)]
        fl = [r for r in cl if r["noise_x"] == 1.0]
        hours = sum(r["hours"] for r in fl)
        g: dict = {"named_faults": len(f)}
        if f:
            ok = [r["delay_s"] is not None
                  and r["delay_s"] <= c["detect_within_s"] for r in f]
            cleared = [r["clear_after_restore_s"] for r in f]
            g.update({
                "detected_in_time": int(sum(ok)),
                "missed_or_late": int(len(f) - sum(ok)),
                "worst_delay_s": max((r["delay_s"] for r in f
                                      if r["delay_s"] is not None),
                                     default=None),
                "false_clears": int(sum(r["false_clear"] for r in f)),
                "lingering_flags": int(sum(r["lingering"] for r in f)),
                "cleared_within_2s_frac": float(np.mean(
                    [x is not None and x <= 2.0 for x in cleared])),
                "false_alarms_before_onset": int(sum(
                    r["false_alarms_before"] for r in f)),
                "worst_peak_err_mps": float(max(r["peak_err_mps"] for r in f)),
                "median_peak_err_mps": float(np.median(
                    [r["peak_err_mps"] for r in f])),
            })
        if cl:
            g.update({
                "clean_hours_floor": hours,
                "false_alarms_floor": int(sum(r["false_alarms"] for r in fl)),
                "false_alarms_per_hour_floor": (
                    sum(r["false_alarms"] for r in fl) / hours if hours else None),
                "false_alarms_10x": int(sum(r["false_alarms"] for r in cl
                                            if r["noise_x"] == 10.0)),
                "flagged_share_clean": float(np.mean(
                    [r["flagged_share"] for r in cl])),
                "worst_energy_gap_frac": float(max(
                    abs(r["equivalent_wh_per_km"] / r["b5_equivalent_wh_per_km"]
                        - 1.0) for r in fl)) if fl else None,
                "worst_tracking_gap_mps": float(max(
                    r["tracking_rmse_mps"] - r["b5_tracking_rmse_mps"]
                    for r in fl)) if fl else None,
                "worst_clean_rmse_mps": float(max(
                    r["tracking_rmse_mps"] for r in cl)),
            })
            if f:
                g["passes"] = bool(
                    g["missed_or_late"] == 0
                    and g["false_alarms_per_hour_floor"]
                    < c["false_alarms_per_hour_below"]
                    and g["worst_energy_gap_frac"]
                    <= c["clean_energy_within_frac"]
                    and g["worst_tracking_gap_mps"]
                    <= c["clean_tracking_within_mps"]
                    and g["worst_clean_rmse_mps"] < c["tracking_rmse_below_mps"]
                    and g["lingering_flags"] <= c["lingering_flags_at_tail"]
                    and g["cleared_within_2s_frac"]
                    >= c["cleared_within_2s_frac_at_least"])
        out["by_accel"][f"{accel}, mass x{mass:g}"] = g
    passes = [g.get("passes") for g in out["by_accel"].values()
              if "passes" in g]
    out["cases_passed"] = int(sum(bool(p) for p in passes))
    out["cases_judged"] = len(passes)
    return out
