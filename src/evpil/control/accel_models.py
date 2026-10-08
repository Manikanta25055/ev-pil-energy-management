"""What a real acceleration channel carries besides white noise.

The fault detector B6 was built and tested against an acceleration channel
that is the vehicle's true acceleration with white noise on it. On 70 logged
BMW i3 trips that assumption does not hold (`docs/week12-speed-arms.md`,
section 10): the logged acceleration and the acceleration the speed implies
share a slow disagreement the white-noise model does not have.

This module builds that disagreement as an error to add to the simulated
channel, one value per control step, for `simulate(accel_error_mps2=...)`:

  offset   a constant bias
  wander   a slow random component (first-order, Ornstein-Uhlenbeck)
  slope    gravity along the road, which an accelerometer reads and a
           wheel-speed derivative does not
  replay   the slow disagreement of a logged trip, as it was

The wander's defaults come from the training-split trips only: over those 19
trips the five-second average of the disagreement has a median standard
deviation of 0.12 m/s^2 and falls to 1/e of itself in a median of 10.5 s.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

G = 9.81
WANDER_SD_MPS2 = 0.12       # median over the training trips
WANDER_TAU_S = 10.5
REPLAY_SMOOTH_S = 5.0


def offset(n: int, bias_mps2: float) -> np.ndarray:
    return np.full(n, float(bias_mps2))


def wander(n: int, dt_s: float, *, sd_mps2: float = WANDER_SD_MPS2,
           tau_s: float = WANDER_TAU_S, seed: int = 0) -> np.ndarray:
    """A slow random error of standard deviation `sd_mps2` that forgets
    itself over `tau_s`. Starts from a draw of its own distribution, so the
    first seconds are as disturbed as the rest."""
    rng = np.random.default_rng([seed, 2])
    phi = np.exp(-dt_s / tau_s)
    drive = rng.normal(0.0, sd_mps2 * np.sqrt(1.0 - phi * phi), n)
    out = np.empty(n)
    x = rng.normal(0.0, sd_mps2)
    for k in range(n):
        x = phi * x + drive[k]
        out[k] = x
    return out


def slope_gravity(grade_rad: np.ndarray) -> np.ndarray:
    """What an accelerometer fixed to the body reads on a slope while the
    wheel speed says nothing has changed: gravity along the road."""
    return G * np.sin(np.asarray(grade_rad, dtype=float))


def logged_disagreement(path: Path | str) -> tuple[np.ndarray, float]:
    """Logged acceleration minus the acceleration the logged speed implies,
    for one BMW i3 trip, smoothed to five seconds. Returns it with the log's
    sample time. The smoothing drops the sample-to-sample part, which is
    mostly the derivative of a quantised speed and is not the sensor."""
    import pandas as pd

    df = pd.read_csv(path, sep=";", encoding="cp1252")
    df.columns = [c.replace("]]]", "]").strip() for c in df.columns]
    need = ("Time [s]", "Velocity [km/h]", "Longitudinal Acceleration [m/s^2]")
    df = df[list(need)].apply(pd.to_numeric, errors="coerce").dropna()
    t = df[need[0]].to_numpy()
    v = df[need[1]].to_numpy() / 3.6
    a = df[need[2]].to_numpy()
    dt = float(np.median(np.diff(t)))
    diff = a - np.gradient(v, t)
    span = max(1, int(round(REPLAY_SMOOTH_S / dt)))
    return np.convolve(diff, np.ones(span) / span, mode="same"), dt


def replay(n: int, dt_s: float, path: Path | str, *,
           start_s: float = 0.0) -> np.ndarray:
    """A logged trip's slow disagreement, resampled to the control step and
    repeated if the cycle outlasts the trip."""
    slow, dt_log = logged_disagreement(path)
    t_log = np.arange(len(slow)) * dt_log
    t = (start_s + np.arange(n) * dt_s) % t_log[-1]
    return np.interp(t, t_log, slow)
