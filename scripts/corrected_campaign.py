"""Validate corrected-plant measurements before reporting them."""

from __future__ import annotations

import json
import math
from pathlib import Path

from evpil.control.scenarios import AXES

DURATIONS = ("0.2", "0.5", "1", "2", "3", "4", "5", "10")
TRACKING_VALID_MPS = 1.0
DROP_LIMIT = 16


def validate_campaign(data: dict) -> dict:
    runs = data["runs"]
    expected = {(axis, lv.level, arm): (seed, lv)
                for arm in ("rule", "actor")
                for axis, levels in AXES.items()
                for seed, lv in enumerate(levels)}
    cells = {}
    for r in runs:
        key = (r["scenario"], r["level"], r["controller"])
        if key in cells:
            raise ValueError(f"duplicate campaign cell: {key}")
        if key not in expected:
            raise ValueError(f"unexpected campaign cells: {key}")
        seed, lv = expected[key]
        if r["seed"] != seed:
            raise ValueError(f"{key}: wrong seed")
        for field in ("cycle", "grade_offset_rad", "soc0", "noise_scale",
                      "comm_delay_s", "aggression"):
            if r[field] != getattr(lv, field):
                raise ValueError(f"{key}: wrong {field}")
        for field in ("distance_km", "equivalent_wh_per_km",
                      "tracking_rmse_mps", "duration_s"):
            if not math.isfinite(r[field]) or r[field] < 0:
                raise ValueError(f"{key}: {field} must be finite and nonnegative")
        if (r["distance_km"] <= 0 or r["steps"] <= 0
                or r["equivalent_wh_per_km"] <= 0):
            raise ValueError(f"{key}: empty run")
        if not math.isclose(r["duration_s"], r["steps"] * 0.01, abs_tol=1e-6):
            raise ValueError(f"{key}: duration does not match control steps")
        if (r["controller"] == "rule" and r["actor_steps"] != 0
                or r["controller"] == "actor" and r["actor_steps"] <= 0):
            raise ValueError(f"{key}: actor_steps indicates the wrong firmware arm")
        if r["tracking_rmse_mps"] < TRACKING_VALID_MPS and r["dropped_frames"] > DROP_LIMIT:
            raise ValueError(f"{key}: disturbed valid cell needs a re-run")
        cells[key] = r
    if set(cells) != set(expected):
        raise ValueError(f"campaign cells incomplete: {len(cells)}/36")
    gaps = []
    excluded = []
    for axis, levels in AXES.items():
        for lv in levels:
            rule, actor = (cells[(axis, lv.level, arm)] for arm in ("rule", "actor"))
            if max(rule["tracking_rmse_mps"], actor["tracking_rmse_mps"]) >= TRACKING_VALID_MPS:
                excluded.append((axis, lv.level))
                continue
            gaps.append(100 * (actor["equivalent_wh_per_km"]
                               / rule["equivalent_wh_per_km"] - 1))
    return {"runs": len(runs), "valid_settings": len(gaps),
            "excluded_settings": len(excluded), "excluded": excluded,
            "actor_less": sum(g < 0 for g in gaps),
            "actor_more": sum(g > 0 for g in gaps), "ties": sum(g == 0 for g in gaps),
            "mean_gap_pct": sum(gaps) / len(gaps) if gaps else None,
            "ctrl_late": sum(r["ctrl_late"] for r in runs),
            "steps": sum(r["steps"] for r in runs)}


def load_corrected_a4(docs: Path) -> dict | None:
    paths = [docs / f"week11-a4-{mode}-{s}s.json"
             for s in DURATIONS for mode in ("on", "off")]
    if not all(p.exists() for p in paths):
        return None
    pairs = {}
    for s in DURATIONS:
        on, off = (json.loads((docs / f"week11-a4-{mode}-{s}s.json").read_text())
                   for mode in ("on", "off"))
        for d, enabled in ((on, True), (off, False)):
            if d["fallback_enabled"] != enabled or d["blackout_s"] != float(s):
                raise ValueError(f"A4 {s}s: wrong mode or duration")
            if d["n_blackouts"] != 8 or len(d["blackouts"]) != 8:
                raise ValueError(f"A4 {s}s: expected eight complete blackouts")
            if d["cycle"] != "us06":
                raise ValueError(f"A4 {s}s: wrong cycle")
            if len({r["onset_s"] for r in d["blackouts"]}) != 8:
                raise ValueError(f"A4 {s}s: duplicate onsets")
            for row in d["blackouts"]:
                if row["diag_last"]["actor_steps"] <= row["diag_first"]["actor_steps"]:
                    raise ValueError(f"A4 {s}s: actor firmware was not active")
                if not math.isfinite(row["err_peak_mps"]):
                    raise ValueError(f"A4 {s}s: nonfinite tracking error")
            for field in ("err_peak_mps", "i_peak_recovery_a"):
                if not all(math.isfinite(d[field][stat]) for stat in ("median", "worst")):
                    raise ValueError(f"A4 {s}s: nonfinite {field}")
        if [r["onset_s"] for r in on["blackouts"]] != [r["onset_s"] for r in off["blackouts"]]:
            raise ValueError(f"A4 {s}s: mismatched onsets")
        pairs[float(s)] = (on, off)
    return pairs
