"""Ablation A4's expectations, pinned against the firmware they describe.

`scripts/run_fallback.py` says which counters must read zero when the firmware
is built with -DFALLBACK_ENABLED=0. That claim is only true while those two
counters are the ones actually inside `#if FALLBACK_ENABLED` in tasks.c. Adding
a third guarded counter, or moving one out, would leave the harness scoring the
ablation against a firmware that no longer matches it -- and because a wrong
expectation here reads as "the ablation failed" rather than as an error, it
would be believed.

So the guard is parsed out of the C rather than restated in Python. Same
discipline as tests/control/test_c_parity.py: the reference values live in one
place, and the test drives both sides.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from scripts.run_fallback import COUNTERS, expectations

TASKS_C = Path(__file__).resolve().parents[2] / "firmware" / "main" / "tasks.c"

# The counters the harness claims are removed by the ablation.
GUARDED = {"ctrl_fallback_steps", "limp_steps"}


def guarded_counters() -> set[str]:
    """Counters incremented inside `#if FALLBACK_ENABLED` in tasks.c.

    Tracks nesting rather than pairing the first #if with the first #endif:
    the control body has `#if !CTRL_PIPELINED` blocks around the same region,
    and a naive scan would attribute their counters to the wrong switch.
    """
    found: set[str] = set()
    depth = 0          # conditional nesting depth
    fallback_at = None  # depth at which FALLBACK_ENABLED opened, if open

    for line in TASKS_C.read_text().splitlines():
        stripped = line.strip()
        if re.match(r"#\s*if", stripped):
            depth += 1
            if fallback_at is None and "FALLBACK_ENABLED" in stripped:
                fallback_at = depth
            continue
        if re.match(r"#\s*endif", stripped):
            if fallback_at is not None and depth == fallback_at:
                fallback_at = None
            depth -= 1
            continue
        if re.match(r"#\s*el(se|if)", stripped):
            # An #else at the FALLBACK_ENABLED depth leaves the taken branch.
            if fallback_at is not None and depth == fallback_at:
                fallback_at = None
            continue
        if fallback_at is not None:
            m = re.search(r"s_diag\.(\w+)\+\+", stripped)
            if m:
                found.add(m.group(1))
    return found


def test_firmware_guards_exactly_the_counters_the_harness_zeroes():
    assert guarded_counters() == GUARDED


def test_a4_requires_the_guarded_counters_to_be_exactly_zero():
    expect = expectations(fallback_off=True)
    for name in GUARDED:
        assert expect[name] == (0, 0), (
            f"{name} is compiled out under A4, so it must be required to be "
            f"exactly 0, not {expect[name]}"
        )


def test_normal_build_requires_the_guarded_counters_to_move():
    expect = expectations(fallback_off=False)
    for name in GUARDED:
        lo, _ = expect[name]
        assert lo >= 1, f"{name} must be required to move in the normal build"


def test_unguarded_counters_are_expected_identically_in_both_modes():
    """The point of a controlled ablation: only the guarded pair may differ."""
    off = expectations(fallback_off=True)
    on = expectations(fallback_off=False)
    assert set(off) == set(on)
    for name in set(off) - GUARDED:
        assert off[name] == on[name], (
            f"{name} is outside the switch, so A4 must not change what is "
            f"expected of it"
        )


def test_ctrl_late_must_stay_zero_in_both_modes():
    """The fallback path is not allowed to cost the loop its own deadline."""
    for mode in (True, False):
        assert expectations(fallback_off=mode)["ctrl_late"] == (0, 0)


@pytest.mark.parametrize("mode", [True, False])
def test_every_expectation_names_a_real_counter(mode):
    assert set(expectations(fallback_off=mode)) <= set(COUNTERS)
