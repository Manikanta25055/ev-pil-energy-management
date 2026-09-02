"""The firmware must turn a policy output into the action the env did.

`EnergyManagementEnv.decode_action` maps the policy's three outputs in
[-1, 1] onto a regen blend, a power limit and an auxiliary derate. The
firmware has to apply the identical map, and this is the class of divergence
that hides best: every value the wrong map produces is still inside its
physical range, so the controller runs, the energy number is plausible, and
nothing raises. The only symptom is that the deployed policy is not the one
the paper's results describe.

So the bounds are exported into the generated header with the weights, and
this drives both implementations over the same inputs, including the corners
where a saturation or an off-by-a-factor-of-two would show.

Same discipline as test_c_parity.py and test_actor_c_parity.py: the reference
is computed here and the C side only prints, because expected values written
into the C file would have to be maintained twice.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from evpil.control.actor import write_c_header
from evpil.control.cycles import Cycle
from evpil.control.env import EnergyManagementEnv
from tests.control.test_actor import two_hidden

HOST_TEST = Path("firmware/host_test")
PARAMS = Path("data/i3_params.json")

# float32 in C against float64 here, over an affine map. The power limit is
# order 1e5, so it carries an absolute tolerance rather than a relative one.
REL = 1e-6
ABS_W = 0.5


def _params():
    from scripts.identify_params import params_from_json
    return params_from_json(str(PARAMS))


@pytest.fixture(scope="module")
def harness(tmp_path_factory):
    if shutil.which("cc") is None:
        pytest.skip("no C compiler available")
    if not (HOST_TEST / "test_decode.c").exists():
        pytest.skip("firmware host test not present")
    if not PARAMS.exists():
        pytest.skip("no identified parameters; run scripts/identify_params.py")

    params = _params()
    inc = tmp_path_factory.mktemp("decode_inc")
    # The decode block is what is under test, and it travels with the weights,
    # so a header has to be generated even though the weights are irrelevant.
    write_c_header(two_hidden(64), inc / "sac_actor_weights.h",
                   p_limit_hi_w=params.motor.power_max_w)
    subprocess.run(["make", "test_decode", f"ACTOR_INC={inc}"],
                   cwd=HOST_TEST, check=True, capture_output=True)
    return HOST_TEST / "test_decode"


def _env() -> EnergyManagementEnv:
    """An env only to borrow its decode. One flat cycle is enough for that."""
    n = 200
    cycle = Cycle(name="flat", dt_s=0.01,
                  v_ref_mps=np.full(n, 15.0),
                  grade_rad=np.zeros(n))
    return EnergyManagementEnv(_params(), [cycle], use_forecast=False, seed=0)


def _run(binary: Path, actions: np.ndarray) -> np.ndarray:
    text = "\n".join(" ".join(f"{v:.9e}" for v in row) for row in actions)
    out = subprocess.run([str(binary)], input=text + "\n", check=True,
                         capture_output=True, text=True).stdout
    rows = [list(map(float, line.split()))
            for line in out.splitlines() if line.strip()]
    return np.asarray(rows, dtype=float)


def _cases() -> np.ndarray:
    rng = np.random.default_rng(7)
    corners = np.array([
        [-1.0, -1.0, -1.0],   # every output at its floor
        [1.0, 1.0, 1.0],      # and at its ceiling
        [0.0, 0.0, 0.0],      # the midpoint, where a sign error survives
        [-1.0, 1.0, -1.0],
        [1.0, -1.0, 1.0],
        # Outside [-1, 1]. tanh cannot produce these, but both sides promise to
        # clip, and a parity that only holds for well-behaved inputs is not one
        # worth having.
        [-3.0, 4.0, -2.5],
        [2.0, -7.0, 9.0],
    ])
    interior = rng.uniform(-1.0, 1.0, size=(64, 3))
    return np.vstack([corners, interior])


def test_decode_matches_the_training_environment(harness):
    env = _env()
    actions = _cases()
    got = _run(harness, actions)
    assert got.shape == (len(actions), 3)

    want = np.array([env.decode_action(a) for a in actions], dtype=float)

    # Regen blend and derate are order 1; the power limit is order 1e5.
    assert got[:, 0] == pytest.approx(want[:, 0], rel=REL, abs=1e-7)
    assert got[:, 1] == pytest.approx(want[:, 1], rel=REL, abs=ABS_W)
    assert got[:, 2] == pytest.approx(want[:, 2], rel=REL, abs=1e-7)


def test_decode_stays_inside_the_action_space(harness):
    """Whatever comes in, what comes out has to be commandable.

    The firmware hands these straight to the plant, so a value outside these
    ranges is not a bad action, it is an invalid command.
    """
    env = _env()
    got = _run(harness, _cases())
    assert np.all((got[:, 0] >= 0.0) & (got[:, 0] <= 1.0))
    assert np.all(got[:, 1] >= env._p_limit_lo - ABS_W)
    assert np.all(got[:, 1] <= env._p_limit_hi + ABS_W)
    assert np.all((got[:, 2] >= 0.0) & (got[:, 2] <= env._derate_max + 1e-6))
