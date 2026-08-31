"""The generated header must be the actor that is actually deployed.

Two failure modes this catches, both silent:

  * the header is stale -- someone retrained and reflashed without exporting,
    so the board runs a policy from a previous run;
  * the header was hand-edited, which produces a policy nobody trained.

Skipped when no actor has been trained yet, because a fresh checkout has no
policy and that is not a failure.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pytest

from evpil.control.actor import Actor, write_c_header

ACTOR = Path("data/actors/sac-with-forecast-seed0.npz")
HEADER = Path("firmware/main/sac_actor_weights.h")


def _skip_unless_present():
    if not ACTOR.exists():
        pytest.skip("no trained actor; run scripts/run_sac.py")
    if not HEADER.exists():
        pytest.skip("no generated header; run scripts/verify_actor.py --export")


def test_the_committed_header_matches_the_committed_actor(tmp_path):
    _skip_unless_present()
    regenerated = tmp_path / "sac_actor_weights.h"
    write_c_header(Actor.load(ACTOR), regenerated)
    assert regenerated.read_text() == HEADER.read_text(), (
        "firmware/main/sac_actor_weights.h is not what the saved actor "
        "generates. Re-run scripts/verify_actor.py --export.")


def test_the_header_geometry_matches_the_actors(tmp_path):
    _skip_unless_present()
    actor = Actor.load(ACTOR)
    text = HEADER.read_text()
    n_in = int(re.search(r"SAC_ACTOR_N_IN\s+(\d+)", text).group(1))
    n_out = int(re.search(r"SAC_ACTOR_N_OUT\s+(\d+)", text).group(1))
    assert [n_in, n_out] == [actor.layer_sizes[0], actor.layer_sizes[-1]]


def test_the_deployed_actor_fits_the_g5_budget():
    """The standing rule on this project: no accuracy number ships without
    its on-device cost. This is the cost, asserted rather than hoped."""
    _skip_unless_present()
    cost = Actor.load(ACTOR).cost()
    assert cost["fits_footprint"]
    # 20.2 KB of the 300 KB budget already belongs to the quantised
    # forecaster, so the actor has to leave room for it.
    assert cost["footprint_kb"] + 20.2 < 300.0
