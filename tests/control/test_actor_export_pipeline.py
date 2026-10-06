"""The generated header must be the actor that is actually deployed.

Two failure modes this catches, both silent:

  * the header is stale -- someone retrained and reflashed without exporting,
    so the board runs a policy from a previous run;
  * the header was hand-edited, which produces a policy nobody trained.

Skipped when no actor has been trained yet, because a fresh checkout has no
policy and that is not a failure.

**Which actor is deployed is a decision, and it is recorded here.** As of
2026-09-02 the device ships the SAC actor trained *without* the forecast, and
no forecaster. The forecast channels of its observation are held at zero, which
is how the without-forecast arm was trained, so the policy sees at deployment
exactly what it saw during training. Ablation A3 found the forecast made no
difference to control, and the forecaster costs 35 ms of a 40 ms budget, so
what it bought did not pay for what it cost.

Seed 3 of five, chosen on the validation cycle (HWFET) at 154.07 Wh/km. US06
stays sealed. Choosing on validation is the point of having one; choosing on
the sealed cycle would be selection on the test set.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from evpil.control.actor import Actor, write_c_header

# The deployed policy. Changing this line changes what the firmware runs, which
# is why it is one line and not a search path.
# Since 2026-10-06 this is the actor retrained on the corrected plant
# (docs/week11-plant-correction.md). The one in data/actors/ learned to lower
# a power ceiling that cost it nothing.
ACTOR = Path("data/actors-corrected/sac-without-forecast-seed3.npz")
HEADER = Path("firmware/main/sac_actor_weights.h")
PARAMS = Path("data/i3_params.json")


def _skip_unless_present():
    if not ACTOR.exists():
        pytest.skip("no trained actor; run scripts/run_sac.py")
    if not HEADER.exists():
        pytest.skip("no generated header; run scripts/verify_actor.py --export")


def _p_limit_hi_w() -> float:
    from scripts.identify_params import params_from_json
    return params_from_json(str(PARAMS)).motor.power_max_w


def test_the_committed_header_matches_the_committed_actor(tmp_path):
    _skip_unless_present()
    regenerated = tmp_path / "sac_actor_weights.h"
    write_c_header(Actor.load(ACTOR), regenerated,
                   p_limit_hi_w=_p_limit_hi_w())
    assert regenerated.read_text() == HEADER.read_text(), (
        "firmware/main/sac_actor_weights.h is not what the saved actor "
        "generates. Re-run scripts/verify_actor.py --export --actor "
        f"{ACTOR}.")


def test_the_deployed_actor_is_a_no_forecast_one():
    """The decision, asserted rather than left in a document.

    Deploying a with-forecast actor while shipping no forecaster would feed it
    two permanently zero channels it was never trained to see. That reads as a
    working controller and is a different one.
    """
    assert "without-forecast" in ACTOR.name


def test_the_header_geometry_matches_the_actors(tmp_path):
    _skip_unless_present()
    actor = Actor.load(ACTOR)
    text = HEADER.read_text()
    n_in = int(re.search(r"SAC_ACTOR_N_IN\s+(\d+)", text).group(1))
    n_out = int(re.search(r"SAC_ACTOR_N_OUT\s+(\d+)", text).group(1))
    assert [n_in, n_out] == [actor.layer_sizes[0], actor.layer_sizes[-1]]


def test_the_header_carries_the_action_decode_bounds():
    """The firmware has to decode the action the way the env encoded it.

    These are emitted with the weights rather than written into the firmware,
    because a policy decoded against different bounds is a different
    controller and every number it produces still looks reasonable.
    """
    _skip_unless_present()
    text = HEADER.read_text()
    from evpil.control.env import DERATE_MAX, P_LIMIT_LO_W
    lo = float(re.search(r"p_limit_lo_w = ([-\d.e+f]+);", text)
               .group(1).rstrip("f"))
    hi = float(re.search(r"p_limit_hi_w = ([-\d.e+f]+);", text)
               .group(1).rstrip("f"))
    dr = float(re.search(r"derate_max = ([-\d.e+f]+);", text)
               .group(1).rstrip("f"))
    assert lo == pytest.approx(P_LIMIT_LO_W)
    assert hi == pytest.approx(_p_limit_hi_w())
    assert dr == pytest.approx(DERATE_MAX)


def test_the_deployed_actor_fits_the_g5_budget():
    """The standing rule on this project: no accuracy number ships without
    its on-device cost. This is the cost, asserted rather than hoped.

    The forecaster's 20.2 KB is no longer reserved. It is not deployed, which
    is the decision this file records, and reserving budget for a model that
    does not ship would understate the headroom the actor actually has.
    """
    _skip_unless_present()
    cost = Actor.load(ACTOR).cost()
    assert cost["fits_footprint"]
    assert cost["footprint_kb"] < 300.0
