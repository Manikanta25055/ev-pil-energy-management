"""The firmware's block features must be the features the model was trained on.

Same discipline as test_c_parity.py, and the failure it guards against is
quieter: a controller that differs gives a different torque, which shows. A
feature that differs gives the model an input it has never seen, and the model
answers anyway.

The C side prints its inputs with its outputs, and the samples fed to the
Python copy are read back from that dump.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from evpil.control.block_features import (
    BLOCK_STEPS, FEATURE_NAMES, FEATURE_SCALE, WINDOW_BLOCKS, BlockFeatures,
    FeatureWindow,
)

HOST_TEST = Path("firmware/host_test")

# Both sides work in float32 and do the same operations in the same order, so
# this is much tighter than the controller's tolerance. What is left is the
# compiler's freedom to contract a multiply-add.
ABS = 2e-6


@pytest.fixture(scope="module")
def dump():
    if shutil.which("cc") is None:
        pytest.skip("no C compiler available")
    subprocess.run(["make", "test_features"], cwd=HOST_TEST, check=True,
                   capture_output=True)
    out = subprocess.run([str(HOST_TEST / "test_features")], check=True,
                         capture_output=True, text=True).stdout
    rows: dict[str, list[list[float]]] = {"in": [], "blk": [], "part": [],
                                          "win": []}
    for line in out.splitlines():
        tag, *rest = line.split()
        rows[tag].append([float(x) for x in rest[1:]])
    return rows


@pytest.fixture(scope="module")
def python_side(dump):
    acc, win = BlockFeatures(), FeatureWindow()
    blocks, partial = [], None
    for v, a, tq, i, v_ref, a_ref in dump["in"]:
        row = acc.push(v_meas_mps=v, a_meas_mps2=a, torque_nm=tq, i_batt_a=i,
                       v_ref_mps=v_ref, a_ref_mps2=a_ref)
        if row is not None:
            blocks.append(row)
            win.push(row)
            if len(blocks) == 3:
                partial = win.as_array()
    return np.array(blocks), partial, win.as_array()


def test_the_dump_exercises_what_it_claims_to(dump):
    blocks = np.array(dump["blk"]) * FEATURE_SCALE
    idx = {n: k for k, n in enumerate(FEATURE_NAMES)}
    assert len(dump["in"]) == 370
    assert len(blocks) > WINDOW_BLOCKS, "the window never wraps"
    assert blocks[:, idx["tq_flips"]].max() > 0, "the torque never flips"
    assert blocks[:, idx["dv_std"]].min() > 0, "the speed never jitters"
    assert blocks[:, idx["i_mean"]].min() > 250, "no large offset on current"


def test_every_block_matches(dump, python_side):
    blocks, _, _ = python_side
    got = np.array(dump["blk"])
    assert got.shape == blocks.shape == (len(dump["in"]) // BLOCK_STEPS,
                                         len(FEATURE_NAMES))
    worst = np.abs(got - blocks).max(axis=0)
    for name, err in zip(FEATURE_NAMES, worst):
        assert err <= ABS, f"{name} differs by {err:.3g}"


def test_the_partly_filled_window_matches(dump, python_side):
    _, partial, _ = python_side
    got = np.array(dump["part"])
    assert np.all(got[:-3] == 0.0)
    assert np.abs(got - partial).max() <= ABS


def test_the_wrapped_window_matches_and_is_oldest_first(dump, python_side):
    blocks, _, window = python_side
    got = np.array(dump["win"])
    assert np.abs(got - window).max() <= ABS
    assert np.abs(got - blocks[-WINDOW_BLOCKS:]).max() <= ABS


def test_the_c_constants_are_the_python_constants():
    """The scale is written out twice. The dump would catch a wrong value;
    this says which one, and catches a changed block or window size."""
    c = Path("firmware/main/features.c").read_text()
    h = Path("firmware/main/features.h").read_text()
    body = re.search(r"k_scale\[FEAT_N\]\s*=\s*\{([^}]*)\}", c).group(1)
    scale = [float(x.strip().rstrip("f")) for x in body.split(",") if x.strip()]
    assert scale == pytest.approx(FEATURE_SCALE.tolist())
    for name, want in (("FEAT_BLOCK_STEPS", BLOCK_STEPS),
                       ("FEAT_N", len(FEATURE_NAMES)),
                       ("FEAT_WINDOW", WINDOW_BLOCKS)):
        got = int(re.search(rf"#define {name}\s+(\d+)", h).group(1))
        assert got == want, f"{name}: firmware has {got}, Python has {want}"
