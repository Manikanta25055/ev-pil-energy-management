"""Every PIL campaign number in the report must come from the campaign file.

The report is generated, so in principle its figures cannot drift from the
measurements. In practice the way that guarantee fails is a number typed into
a sentence during a late edit, which then survives every regeneration and
disagrees with the table three inches above it.

This test reads the rendered .docx back and checks the campaign table cell by
cell against `docs/week10-pil-campaign.json`. It is deliberately not a test of
`build_report.py`'s internals: it compares the artefact that gets emailed with
the data it claims to be about.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

docx = pytest.importorskip("docx")

CAMPAIGN = Path("docs/week10-pil-campaign.json")
REPORT = Path("reports/EV-PIL-status-report.docx")

HEADER = ["Varied", "Setting", "Rules: tracking error, m/s",
          "Learned: tracking error, m/s", "Rules: energy, Wh/km",
          "Learned: energy, Wh/km"]

TIMING_HEADER = ["Controller", "Runs", "Control steps", "Missed deadlines",
                 "Late or lost frames", "Worst inference, us"]


def _require_inputs():
    if not CAMPAIGN.exists():
        pytest.skip("the PIL campaign has not been run yet")
    if not REPORT.exists():
        pytest.skip("the report has not been generated yet")


def test_report_is_not_older_than_the_campaign():
    """Guards the one way this file could pass while proving nothing.

    Every other test here skips when the campaign has not been run, and a
    suite of skips exits zero. That is fine while the campaign is still
    running and dishonest afterwards, so this test does not skip once the
    measurements exist: if the campaign file is present, the report must have
    been regenerated after it.
    """
    if not CAMPAIGN.exists():
        pytest.skip("the PIL campaign has not been run yet")
    assert REPORT.exists(), (
        "the campaign has been measured but the report has not been "
        "regenerated from it")
    assert REPORT.stat().st_mtime >= CAMPAIGN.stat().st_mtime, (
        "the report is older than the campaign file it claims to report; "
        "re-run scripts/build_report.py")


@pytest.fixture(scope="module")
def campaign():
    _require_inputs()
    return json.loads(CAMPAIGN.read_text())


@pytest.fixture(scope="module")
def document():
    _require_inputs()
    return docx.Document(str(REPORT))


def _find_table(document, header):
    for t in document.tables:
        if [c.text for c in t.rows[0].cells] == header:
            return t
    raise AssertionError(f"no table in the report with header {header}")


def test_campaign_file_holds_thirty_six_runs(campaign):
    assert len(campaign["runs"]) == 36


def test_every_campaign_cell_matches_the_report(campaign, document):
    """The load-bearing test: each rendered cell equals the measurement."""
    by_key = {(r["scenario"], r["level"], r["controller"]): r
              for r in campaign["runs"]}
    table = _find_table(document, HEADER)

    from evpil.control.scenarios import AXES
    levels = {lv.level: axis for axis in AXES for lv in AXES[axis]}

    body = table.rows[1:]
    assert len(body) == 18, f"expected 18 settings, found {len(body)}"

    for row in body:
        cells = [c.text for c in row.cells]
        level = cells[1].replace(" ", "_")
        axis = levels[level]
        rule = by_key[(axis, level, "rule")]
        actor = by_key[(axis, level, "actor")]

        assert cells[2] == f"{rule['tracking_rmse_mps']:.4f}", cells
        assert cells[3] == f"{actor['tracking_rmse_mps']:.4f}", cells
        assert cells[4] == f"{rule['equivalent_wh_per_km']:.2f}", cells
        assert cells[5] == f"{actor['equivalent_wh_per_km']:.2f}", cells


def test_timing_table_matches_the_campaign(campaign, document):
    runs = campaign["runs"]
    table = _find_table(document, TIMING_HEADER)
    seen = {}
    for row in table.rows[1:]:
        cells = [c.text for c in row.cells]
        seen[cells[0]] = cells

    for controller, label in (("rule", "Rules"), ("actor", "Learned")):
        arm = [r for r in runs if r["controller"] == controller]
        cells = seen[label]
        assert cells[1] == f"{len(arm)}"
        assert cells[2] == f"{sum(r['steps'] for r in arm):,}"
        assert cells[3] == f"{sum(r['ctrl_late'] for r in arm)}"
        assert cells[4] == f"{sum(r['dropped_frames'] for r in arm):,}"
        assert cells[5] == f"{max(r['actor_wcet_us'] for r in arm)}"


def test_the_headline_count_is_not_typed_in(campaign, document):
    """The sentence counting settings where the policy costs more energy."""
    runs = campaign["runs"]
    by_key = {(r["scenario"], r["level"], r["controller"]): r for r in runs}
    keys = {(r["scenario"], r["level"]) for r in runs}
    worse = sum(
        1 for axis, level in keys
        if by_key[(axis, level, "actor")]["equivalent_wh_per_km"]
        > by_key[(axis, level, "rule")]["equivalent_wh_per_km"])

    text = "\n".join(p.text for p in document.paragraphs)
    needle = (f"The learned controller uses more energy than the rules in "
              f"{worse} of the {len(keys)} settings")
    assert needle in text, (
        "the report's headline sentence does not match the campaign file; "
        f"expected to find: {needle!r}")


def test_report_does_not_recommend_the_learned_controller(document):
    """A standing constraint, not a stylistic one.

    The policy is measurably worse on energy than the rules it replaces. The
    report is allowed to say the deployment demonstrates a timing result; it
    is not allowed to imply the controller is recommended.
    """
    text = "\n".join(p.text for p in document.paragraphs).lower()
    assert "is not recommended on energy grounds" in text
