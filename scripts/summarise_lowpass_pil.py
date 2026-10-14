"""Summary of measurement-round item B1 (plan docs/2026-10-14-measurement-plan.md).

Baseline speed loop, fixed low-pass (alpha 0.1) and two-state Kalman estimator
on the target, US06 at the noise floor and at ten times it, noise seed offsets
100 and 200. The 10x loss of each arm is taken against its own floor run of the
same offset. The earlier single-seed board result (docs/week12-speed-arms-*.json)
is added for the baseline and Kalman arms. MEASURED.

    python3 scripts/summarise_lowpass_pil.py
"""
import json
from pathlib import Path

OUT = Path("docs/2026-10-14-lowpass-pil-summary.json")


def cells(path):
    runs = json.loads(Path(path).read_text())["runs"]
    return {r["level"]: r for r in runs if r["scenario"] == "sensor_noise"}


def main():
    out = {"provenance": "MEASURED on the ESP32-S3, rule manager in every arm; plan item B1",
           "arms": {}}
    earlier = {"b0": "docs/week12-speed-arms-b0.json", "kalman": "docs/week12-speed-arms-b5.json"}
    for arm in ("b0", "lowpass", "kalman"):
        rows = []
        for off in (100, 200):
            c = cells(f"docs/2026-10-14-lowpass-pil-{arm}-s{off}.json")
            rows.append({"seed_offset": off, **{
                f"{lv}_{k}": c[lv][key] for lv in ("floor", "severe")
                for k, key in (("wh_per_km", "equivalent_wh_per_km"),
                               ("rmse_mps", "tracking_rmse_mps"),
                               ("peak_current_a", "peak_current_a"),
                               ("dropped_frames", "dropped_frames"))}})
        if arm in earlier:
            c = cells(earlier[arm])
            rows.append({"seed_offset": 0, "source": earlier[arm],
                         "floor_wh_per_km": c["floor"]["equivalent_wh_per_km"],
                         "severe_wh_per_km": c["severe"]["equivalent_wh_per_km"],
                         "floor_rmse_mps": c["floor"]["tracking_rmse_mps"],
                         "severe_rmse_mps": c["severe"]["tracking_rmse_mps"]})
        for r in rows:
            r["loss_10x_wh_per_km"] = r["severe_wh_per_km"] - r["floor_wh_per_km"]
        out["arms"][arm] = rows
    OUT.write_text(json.dumps(out, indent=1) + "\n")
    for arm, rows in out["arms"].items():
        print(arm, [(r["seed_offset"], round(r["floor_wh_per_km"], 2),
                     round(r["severe_wh_per_km"], 2), round(r["loss_10x_wh_per_km"], 2),
                     round(r["floor_rmse_mps"], 3)) for r in rows])


if __name__ == "__main__":
    main()
