"""Standard driving cycles: load, resample, and attach a grade profile.

The published traces are one sample per second. The control loop runs at
100 Hz (spec 4.4), so a cycle has to be resampled by a factor of a hundred
before it can be a reference. How that resampling is done is not cosmetic:
holding each sample for a second and stepping between them turns every
one-second speed change into an instantaneous one, which asks the tracker for
an unbounded acceleration and shows up as a tracking error the controller
never caused.

Linear interpolation between published samples is what the regulations
themselves assume -- GTR 15 defines the trace as the polyline through the
tabulated points -- so that is what is used here.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

CYCLE_DIR = Path("data/raw/cycles")

# Spec 5.2, retained from the professor's original plan: the controller is
# trained on WLTP and UDDS, tuned on HWFET, and reported on US06. US06 is the
# aggressive cycle, which is the honest place to report a controller that
# claims to save energy without giving up tracking.
CONTROL_SPLIT: dict[str, tuple[str, ...]] = {
    "train": ("wltc3b", "udds"),
    "val": ("hwfet",),
    "test": ("us06",),
}


@dataclass(frozen=True)
class Cycle:
    name: str
    dt_s: float
    v_ref_mps: np.ndarray
    grade_rad: np.ndarray

    @property
    def duration_s(self) -> float:
        return float(len(self.v_ref_mps) * self.dt_s)

    @property
    def distance_m(self) -> float:
        return float(np.sum(self.v_ref_mps) * self.dt_s)


def available() -> tuple[str, ...]:
    manifest = CYCLE_DIR / "manifest.json"
    if not manifest.exists():
        return ()
    return tuple(json.loads(manifest.read_text()).keys())


def load_raw(name: str, cycle_dir: Path | str = CYCLE_DIR) -> tuple[np.ndarray, np.ndarray]:
    """The published trace, unmodified: (t_s, v_mps) at its own sample rate."""
    path = Path(cycle_dir) / f"{name}.npz"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Run scripts/build_cycles.py to fetch the "
            f"published traces."
        )
    with np.load(path) as z:
        return z["t_s"], z["v_mps"]


def grade_profile(
    n: int,
    dt_s: float,
    kind: str = "flat",
    amplitude_rad: float = 0.0,
    period_s: float = 600.0,
) -> np.ndarray:
    """Road grade along the cycle, in radians, positive uphill.

    Three shapes, all deterministic so that a scenario is reproducible from
    its name alone:

      flat   zero everywhere; the reference condition
      sine   a smooth climb-and-descend of the given amplitude, which returns
             to the starting elevation and so does not bias trip energy
      ramp   a sustained climb over the first half and descent over the
             second, the harder case for a battery power limit

    Amplitude is an angle, not a percent grade. 0.05 rad is about 5% grade.
    """
    t = np.arange(n, dtype=float) * dt_s
    if kind == "flat":
        return np.zeros(n)
    if kind == "sine":
        return amplitude_rad * np.sin(2.0 * np.pi * t / period_s)
    if kind == "ramp":
        half = t <= (t[-1] / 2.0 if n > 1 else 1.0)
        return np.where(half, amplitude_rad, -amplitude_rad)
    raise ValueError(f"unknown grade profile {kind!r}")


def load_cycle(
    name: str,
    dt_s: float = 0.01,
    *,
    grade: str = "flat",
    grade_amplitude_rad: float = 0.0,
    grade_period_s: float = 600.0,
    cycle_dir: Path | str = CYCLE_DIR,
) -> Cycle:
    """Load a published cycle resampled onto the control period."""
    t_s, v_raw = load_raw(name, cycle_dir)

    n = int(round(t_s[-1] / dt_s)) + 1
    t_new = np.arange(n, dtype=float) * dt_s
    v_ref = np.interp(t_new, t_s, v_raw)
    v_ref[v_ref < 0.0] = 0.0

    return Cycle(
        name=name, dt_s=dt_s, v_ref_mps=v_ref,
        grade_rad=grade_profile(n, dt_s, grade, grade_amplitude_rad,
                                grade_period_s),
    )
