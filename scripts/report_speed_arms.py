"""The speed-loop arms on the board: validate the three files and say what
they show.

Three images, all with the rule manager for energy, differing only in what
turns the measured speed into the speed the loop controls on:

  b0  the loop as shipped                         SPEED_KALMAN=0
  b5  the two-state Kalman estimate               SPEED_KALMAN=3
  b6  that, with the sensor-fault detector on top SPEED_KALMAN=4

Six cells each: urban, highway and US06 at the noise floor, then US06 at the
floor, 3x and 10x sensor noise. The criteria are the ones the design fixed
before anything was built (docs/superpowers/specs/2026-10-06-decision-model-design.md,
section 7.3), applied to what the board can measure: clean energy and clean
tracking against the shipped loop, and how much of the 10x noise penalty is
recovered. The fault criteria cannot be tested here, because the campaign
injects no faults; what it does measure is false alarms on a healthy sensor.

Nothing is run. This reads saved measurements.

    PYTHONPATH="src:." python3 scripts/report_speed_arms.py
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

ARMS = {"b0": 0, "b5": 3, "b6": 4}
CELLS = (("driving_condition", "urban"), ("driving_condition", "highway"),
         ("driving_condition", "aggressive_mixed"),
         ("sensor_noise", "floor"), ("sensor_noise", "elevated"),
         ("sensor_noise", "severe"))
CLEAN = CELLS[:3]
DROP_LIMIT = 16
FIELDS = ("equivalent_wh_per_km", "tracking_rmse_mps", "tracking_max_mps",
          "peak_current_a", "regen_wh", "ctrl_wcet_us", "sensor_alarms",
          "sensor_flag_steps", "dropped_frames", "ctrl_late", "steps",
          "duration_s", "distance_km")


def validate_arm(arm: str, data: dict) -> dict:
    """Every cell present once, taken on the image it claims, undisturbed."""
    cells = {}
    for r in data["runs"]:
        key = (r["scenario"], r["level"])
        if key in cells:
            raise ValueError(f"{arm}: duplicate cell {key}")
        if key not in CELLS:
            raise ValueError(f"{arm}: unexpected cell {key}")
        if r["controller"] != "rule" or r["actor_steps"] != 0:
            raise ValueError(f"{arm} {key}: not the rule manager's image")
        if r["speed_est_mode"] != ARMS[arm]:
            raise ValueError(
                f"{arm} {key}: image reports estimator {r['speed_est_mode']}, "
                f"arm needs {ARMS[arm]}")
        for f in ("equivalent_wh_per_km", "tracking_rmse_mps", "distance_km"):
            if not math.isfinite(r[f]) or r[f] <= 0:
                raise ValueError(f"{arm} {key}: {f} is not a positive number")
        if r["tracking_rmse_mps"] >= 1.0:
            raise ValueError(f"{arm} {key}: the car did not follow the cycle")
        if r["dropped_frames"] > DROP_LIMIT:
            raise ValueError(f"{arm} {key}: disturbed cell needs a re-run")
        if arm != "b6" and (r["sensor_alarms"] or r["sensor_flag_steps"]):
            raise ValueError(f"{arm} {key}: fault counters moved with no detector")
        cells[key] = r
    if set(cells) != set(CELLS):
        raise ValueError(f"{arm}: {len(cells)}/{len(CELLS)} cells")
    return cells


def summarise(arms: dict[str, dict]) -> dict:
    e = lambda arm, key: arms[arm][key]["equivalent_wh_per_km"]
    t = lambda arm, key: arms[arm][key]["tracking_rmse_mps"]

    rows = [{"scenario": k[0], "level": k[1],
             **{f"{arm}_{f}": arms[arm][k][f] for arm in ARMS for f in FIELDS}}
            for k in CELLS]

    # The same setting twice with different noise seeds: US06 at the floor
    # sits on both axes. It is the only measure here of how far a number
    # moves when nothing has changed.
    twin = (("driving_condition", "aggressive_mixed"), ("sensor_noise", "floor"))
    spread = {arm: abs(100.0 * (e(arm, twin[0]) / e(arm, twin[1]) - 1.0))
              for arm in ARMS}

    floor, severe = ("sensor_noise", "floor"), ("sensor_noise", "severe")
    penalty = e("b0", severe) - e("b0", floor)
    verdicts = {}
    for arm in ("b5", "b6"):
        clean_e = [100.0 * (e(arm, k) / e("b0", k) - 1.0) for k in CLEAN]
        clean_t = [t(arm, k) - t("b0", k) for k in CLEAN]
        recovered = (e("b0", severe) - e(arm, severe)) / penalty
        own = e(arm, severe) - e(arm, floor)
        steps = sum(arms[arm][k]["steps"] for k in CELLS)
        v = {
            "clean energy vs b0, percent, per cycle": clean_e,
            "clean energy within 0.2% of b0": all(abs(x) <= 0.2 for x in clean_e),
            "clean tracking RMSE minus b0, m/s, per cycle": clean_t,
            "clean tracking within 0.005 m/s of b0":
                all(x <= 0.005 for x in clean_t),
            "b0 penalty at 10x noise, Wh/km": penalty,
            "own penalty at 10x noise, Wh/km": own,
            "fraction of b0's 10x penalty recovered": recovered,
            "recovers at least half of the 10x penalty": bool(recovered >= 0.5),
            "tracking under 0.1 m/s in every cell":
                all(t(arm, k) < 0.1 for k in CELLS),
            "late control steps": sum(arms[arm][k]["ctrl_late"] for k in CELLS),
            "worst control computation, us":
                max(arms[arm][k]["ctrl_wcet_us"] for k in CELLS),
            "hours on the board": steps * 0.01 / 3600.0,
        }
        if arm == "b6":
            v["false alarms on a healthy sensor"] = sum(
                arms[arm][k]["sensor_alarms"] for k in CELLS)
            v["control steps spent flagged"] = sum(
                arms[arm][k]["sensor_flag_steps"] for k in CELLS)
        v["meets every criterion the board can test"] = bool(
            v["clean energy within 0.2% of b0"]
            and v["clean tracking within 0.005 m/s of b0"]
            and v["recovers at least half of the 10x penalty"]
            and v["tracking under 0.1 m/s in every cell"]
            and v["late control steps"] == 0
            and v.get("false alarms on a healthy sensor", 0) == 0)
        verdicts[arm] = v

    return {
        "provenance": "MEASURED on the board, one run per cell",
        "arms": {a: f"SPEED_KALMAN={m}" for a, m in ARMS.items()},
        "b0 worst control computation, us":
            max(arms["b0"][k]["ctrl_wcet_us"] for k in CELLS),
        "twin_cell_spread_percent": spread,
        "rows": rows, "verdicts": verdicts,
        "not_tested_on_the_board": [
            "25x noise and a noise level that changes mid-cycle",
            "injected sensor faults (stuck, dropout, offset)",
            "a vehicle heavier than the model",
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", default="docs")
    ap.add_argument("--out-json", default="docs/week12-speed-arms.json")
    args = ap.parse_args()
    docs = Path(args.docs)
    arms = {arm: validate_arm(arm, json.loads(
        (docs / f"week12-speed-arms-{arm}.json").read_text())) for arm in ARMS}
    out = summarise(arms)
    Path(args.out_json).write_text(json.dumps(out, indent=1) + "\n")

    print(f"{'cell':36s}" + "".join(f"{a:>26s}" for a in ARMS))
    for r in out["rows"]:
        print(f"{r['scenario'] + '/' + r['level']:36s}" + "".join(
            f"{r[a + '_equivalent_wh_per_km']:10.2f} /{r[a + '_tracking_rmse_mps']:7.4f}"
            f" /{r[a + '_peak_current_a']:4.0f}A" for a in ARMS))
    print("  (energy Wh/km / tracking RMSE m/s / peak current)")
    print("twin-cell spread, %:", {a: round(s, 3) for a, s in
                                   out["twin_cell_spread_percent"].items()})
    for arm, v in out["verdicts"].items():
        print(arm)
        for k, x in v.items():
            print(f"   {k}: {x}")
    print(f"wrote {args.out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
