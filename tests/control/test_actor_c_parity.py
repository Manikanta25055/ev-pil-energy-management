"""The actor that runs on the board must be the actor that was trained.

The chain has four links -- PyTorch, numpy arrays, a generated C header,
inference in C -- and a transposed matrix anywhere along it produces a
controller that runs, returns plausible actions, and is not the one that was
trained. This checks the last two links without needing hardware; the board
itself is checked by scripts/verify_actor.py, which is the same comparison
against silicon.

Random probes rather than a fixed set: the on-device benchmark carries corners
and centre, and this covers the interior those would miss.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from evpil.control.actor import Actor, actor_checksum, write_c_header
from tests.control.test_actor import two_hidden

HOST_TEST = Path("firmware/host_test")
# float32 in C against float64 in numpy, accumulated over 64-wide dot
# products, then squashed by tanh, which contracts rather than amplifies.
TOL = 2e-5

# Any value: this harness checks the forward pass, not the decode. It has to
# be supplied because a header without decode bounds will not compile.
P_LIMIT_HI_W = 125000.0


@pytest.fixture(scope="module")
def harness(tmp_path_factory):
    if shutil.which("cc") is None:
        pytest.skip("no C compiler available")
    if not (HOST_TEST / "test_actor.c").exists():
        pytest.skip("firmware host test not present")

    actor = two_hidden(64)
    inc = tmp_path_factory.mktemp("actor_inc")
    write_c_header(actor, inc / "sac_actor_weights.h",
                   p_limit_hi_w=P_LIMIT_HI_W)

    build = subprocess.run(
        ["make", "test_actor", f"ACTOR_INC={inc}", "-B"],
        cwd=HOST_TEST, capture_output=True, text=True)
    if build.returncode != 0:
        pytest.fail(f"build failed:\n{build.stdout}\n{build.stderr}")
    return actor, HOST_TEST / "test_actor"


def run_probes(binary: Path, probes: np.ndarray
               ) -> tuple[np.ndarray, list[int], int]:
    text = "\n".join(" ".join(f"{v:.9g}" for v in row) for row in probes) + "\n"
    done = subprocess.run([str(binary)], input=text, capture_output=True,
                          text=True, check=True)
    lines = [l for l in done.stdout.splitlines() if l.strip()]
    geom = [int(x) for x in lines[0].split()[2:]]
    checksum = int(lines[1].split()[2], 16)
    return (np.array([[float(x) for x in r.split()] for r in lines[2:]]),
            geom, checksum)


def test_the_harness_compiled_the_weights_it_generated(harness):
    """The regression this file exists for, kept as its own test.

    A quoted #include is resolved against the including file's directory
    before any -I path, so firmware/main/actor.c picked up the deployed
    weights however the harness was invoked. Both networks are 8-64-64-3, so
    geometry matched, the harness agreed with itself, and the parity check
    passed while comparing two different policies. The checksum comes from
    actor.c itself, which is the only translation unit whose answer means
    anything here."""
    actor, binary = harness
    _, _, checksum = run_probes(binary, np.zeros((1, actor.layer_sizes[0])))
    assert checksum == actor_checksum(actor)


def test_the_c_actor_reports_the_geometry_it_was_given(harness):
    actor, binary = harness
    _, geom, checksum = run_probes(binary, np.zeros((1, actor.layer_sizes[0])))
    assert geom == [actor.layer_sizes[0], actor.layer_sizes[-1],
                    actor.n_params]
    # Shape alone does not identify a network. The deployed policy has the
    # same 8-64-64-3 geometry as this one, so without the checksum a harness
    # that compiled against the wrong header would pass this test.
    assert checksum == actor_checksum(actor)


def test_the_c_actor_matches_numpy_across_the_input_box(harness):
    actor, binary = harness
    rng = np.random.default_rng(20260831)
    probes = rng.uniform(-10.0, 10.0, size=(200, actor.layer_sizes[0]))
    got, _, _ = run_probes(binary, probes)
    want = np.array([actor.forward(p) for p in probes])
    err = np.abs(got - want).max()
    assert err <= TOL, f"worst difference {err:.3e}"


def test_the_c_actor_matches_numpy_at_the_corners(harness):
    """Where a layout error shows. A uniform interior sample visits saturation
    almost never, and saturation is exactly where a wrong sign survives."""
    actor, binary = harness
    n = actor.layer_sizes[0]
    corners = np.array([[s * 10.0] * n for s in (-1.0, 1.0)]
                       + [[0.0] * n]
                       + [[(-1.0) ** i * 10.0 for i in range(n)]])
    got, _, _ = run_probes(binary, corners)
    want = np.array([actor.forward(p) for p in corners])
    assert np.abs(got - want).max() <= TOL


def test_every_c_action_is_inside_the_actuator_range(harness):
    _, binary = harness
    rng = np.random.default_rng(7)
    probes = rng.uniform(-10.0, 10.0, size=(100, 8))
    got, _, _ = run_probes(binary, probes)
    assert np.all(np.abs(got) <= 1.0)
