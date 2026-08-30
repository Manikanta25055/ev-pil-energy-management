"""The identified coefficients must not read as physical measurements.

`c_rr` identifies to 0.01947 on the i3 archive while an independent coastdown
on a comparable BEV measures 0.00878. The fitted number is a lumped loss term
wearing rolling resistance's name. This is the one thing about the parameter
file that a reader can get wrong in a way that invalidates a claim, so the
artefact is required to say so and this test is what keeps it saying so.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

PARAMS_PATH = Path(__file__).resolve().parents[2] / "data" / "i3_params.json"

# Fitted, and therefore not a property of any vehicle.
LUMPED = ("c_rr", "cd", "rot_mass_factor")


@pytest.fixture(scope="module")
def params() -> dict:
    return json.loads(PARAMS_PATH.read_text())


def test_lumped_coefficients_are_flagged_in_their_own_citations(params):
    for name in LUMPED:
        citation = params["citations"][name]
        assert "LUMPED" in citation, (
            f"citation for {name!r} does not flag it as a lumped coefficient. "
            f"A reader is entitled to treat an unqualified identified value as "
            f"a measurement, and for {name!r} that would be wrong."
        )


def test_file_carries_the_caveat_a_reader_meets_first(params):
    caveat = params["caveats"]
    for name in LUMPED:
        assert name in caveat
    # The coastdown comparison is the evidence, not an opinion; without the
    # numbers the caveat is just a disclaimer.
    assert "0.01947" in caveat and "0.00878" in caveat


def test_the_identified_c_rr_is_still_the_one_the_caveat_describes(params):
    # If a re-identification moves c_rr, the caveat's quoted number goes stale
    # and this test is the thing that notices.
    assert params["identified"]["c_rr"] == pytest.approx(0.01947, abs=5e-5)


def test_measured_quantities_are_not_swept_up_by_the_warning(params):
    # capacity_ah is genuinely measured, by Coulomb counting. The caveat must
    # not be so broad that it discredits the measurements alongside the fits.
    assert "MEASURED" in params["citations"]["battery"]
    assert "capacity_ah" not in params["caveats"]
