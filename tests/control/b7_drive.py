"""A drive for the B7 parity tests: healthy stretches, a wandering
acceleration channel, and four sensor faults. Shared by the two tests so
that B7 alone and B7 with the monitor are compared on the same inputs."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from evpil.control import accel_models as am

HOST_TEST = Path("firmware/host_test")
N = 4000
FAULTS = ((800, 1300, "bias", 0.5), (1700, 1900, "dropout", 0.0),
          (2400, 2600, "stuck", 0.0), (3000, 3500, "bias", -0.5))


def drive(seed: int = 0, noise_x: float = 1.0):
    """Returns v_meas, a_meas, torque as float32-exact Python floats, so the
    C side and the Python side are given the same numbers."""
    rng = np.random.default_rng(seed)
    a_true = np.where(np.arange(N) < 600, 1.2, 0.0) + 0.6 * np.sin(
        2 * np.pi * np.arange(N) * 0.01 / 23.0)
    v_true = 8.0 + np.cumsum(a_true) * 0.01
    v = v_true + rng.normal(0.0, 0.02 * noise_x, N)
    a = (a_true + rng.normal(0.0, 0.05 * noise_x, N)
         + am.wander(N, 0.01, seed=seed + 1))
    held = 0.0
    for lo, hi, kind, mag in FAULTS:
        if kind == "bias":
            v[lo:hi] += mag
        elif kind == "dropout":
            v[lo:hi] = 0.0
        else:
            held = v[lo]
            v[lo:hi] = held
    tq = 60.0 + 80.0 * a_true
    f32 = lambda x: [float(np.float32(y)) for y in x]
    return f32(v), f32(a), f32(tq)


def run_c(mode: str, v, a, tq, tmp_path) -> np.ndarray:
    if shutil.which("cc") is None:
        pytest.skip("no C compiler available")
    exe = tmp_path / "test_b7"
    build = subprocess.run(
        ["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-O1",
         "-Ifirmware/main", "-o", str(exe), str(HOST_TEST / "test_b7.c"),
         "firmware/main/control.c", "-lm"], capture_output=True, text=True)
    assert build.returncode == 0, build.stderr
    text = "".join(f"{x:.9g} {y:.9g} {z:.9g}\n" for x, y, z in zip(v, a, tq))
    out = subprocess.run([str(exe), mode], input=text, capture_output=True,
                         text=True, check=True).stdout
    return np.array([[float(x) for x in line.split()]
                     for line in out.strip().splitlines()])
