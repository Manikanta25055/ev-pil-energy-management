"""The reviewer cell in C must be the cell that was trained.

The mirror of test_actor_c_parity.py for the recurrent reviewers: the numpy
cell and firmware/main/reviewer.c, driven by the same blocks. Random weights
cover both cell kinds without needing a trained model on disk; the trained
ones, where present, are checked on recorded-looking inputs as well.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from evpil.control.supervisor import N_FEATURES
from evpil.control.tiny_rnn import TinyReviewer, write_c_header

HOST_TEST = Path("firmware/host_test")
# float32 in both, but libm's expf and tanhf against numpy's, fed back through
# the state for hundreds of steps. The actor's 2e-5 holds for the trained
# cells; a random FastGRNN cell, whose state is not kept small by training,
# reaches 3.4e-5.
TOL = 1e-4


def random_model(kind: str, hidden: int, seed: int) -> TinyReviewer:
    rng = np.random.default_rng(seed)
    g = lambda *shape: rng.normal(0.0, 0.4, shape).astype(np.float32)
    w = {"kind": kind, "w_out": g(4, hidden), "b_out": g(4),
         "mask": np.array([1.0] * 10 + [0.0, 1.0], np.float32),
         "temperature": 1.3}
    if kind == "gru":
        w.update(w_ih=g(3 * hidden, N_FEATURES), w_hh=g(3 * hidden, hidden),
                 b_ih=g(3 * hidden), b_hh=g(3 * hidden))
    else:
        w.update(w=g(hidden, N_FEATURES), u=g(hidden, hidden), b_z=g(hidden),
                 b_h=g(hidden), zeta=g(1), nu=g(1))
    return TinyReviewer(w)


def run_c(model: TinyReviewer, x: np.ndarray, tmp_path) -> np.ndarray:
    if shutil.which("cc") is None:
        pytest.skip("no C compiler available")
    write_c_header(model, tmp_path / "reviewer_weights.h")
    exe = tmp_path / "test_reviewer"
    build = subprocess.run(
        ["cc", f"-I{tmp_path}", "-std=c11", "-Wall", "-Wextra", "-Werror",
         "-O1", "-I" + str(Path("firmware/main").resolve()), "-o", str(exe),
         str(HOST_TEST / "test_reviewer.c"), "firmware/main/reviewer.c",
         "-lm"], capture_output=True, text=True)
    assert build.returncode == 0, build.stderr
    text = "\n".join(" ".join(f"{v:.9g}" for v in row) for row in x) + "\n"
    out = subprocess.run([str(exe)], input=text, capture_output=True,
                         text=True, check=True).stdout
    return np.array([[float(v) for v in line.split()]
                     for line in out.strip().splitlines()])


@pytest.mark.parametrize("kind,hidden", [("gru", 16), ("fastgrnn", 16),
                                         ("gru", 64)])
def test_the_c_cell_is_the_numpy_cell(kind, hidden, tmp_path):
    model = random_model(kind, hidden, seed=hidden)
    x = np.random.default_rng(1).normal(0.0, 1.0, (300, N_FEATURES))
    got = run_c(model, x, tmp_path)
    model.reset()
    want = np.array([model.logits(row) for row in x])
    assert got.shape == want.shape
    assert np.abs(got - want).max() < TOL


@pytest.mark.parametrize("name", ["gru16v3", "fastgrnn16v3", "gru64v3"])
def test_a_trained_reviewer_survives_the_port(name, tmp_path):
    path = Path(f"models/reviewer/{name}.npz")
    if not path.exists():
        pytest.skip("trained reviewer not present")
    model = TinyReviewer.load(path)
    x = np.random.default_rng(2).normal(0.0, 0.5, (600, N_FEATURES))
    got = run_c(model, x, tmp_path)
    model.reset()
    want = np.array([model.logits(row) for row in x])
    assert np.abs(got - want).max() < TOL
