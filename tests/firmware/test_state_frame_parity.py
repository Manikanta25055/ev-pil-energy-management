"""The state frame's two definitions must agree on its size and its order.

`evpil.protocol.STATE_FIELDS` says what the host sends. `plant_state_t` in
tasks.h and the unpack in tasks.c say what the board reads. They are written
out separately, and week 10 added a field to both, which is exactly the edit
that leaves them one apart.

A mismatch is not a crash. The firmware checks the payload length, so a frame
of the wrong size is dropped and the board simply stops receiving state, which
looks like a dead link rather than a schema error. A frame of the *right* size
with the fields in a different order is worse: it is accepted, and the
controller acts on a grade it thinks is a speed.

Parsed out of the C rather than restated here, same discipline as
test_a4_expectations.py.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from evpil.protocol import (
    ACTUATION_FIELDS, DIAG_FIELDS, STATE_FIELDS, STATE_PAYLOAD_SIZE,
)

FW = Path(__file__).resolve().parents[2] / "firmware" / "main"
TASKS_H = FW / "tasks.h"
TASKS_C = FW / "tasks.c"


def header_define(name: str) -> int:
    m = re.search(rf"^#define\s+{name}\s+(\d+)\s*$", TASKS_H.read_text(),
                  re.MULTILINE)
    assert m, f"{name} not found in tasks.h"
    return int(m.group(1))


def test_state_payload_size_agrees():
    assert header_define("STATE_PAYLOAD_BYTES") == STATE_PAYLOAD_SIZE


def test_actuation_payload_size_agrees():
    assert header_define("ACT_PAYLOAD_BYTES") == 4 * len(ACTUATION_FIELDS)


def test_the_firmware_assigns_every_state_field_in_order():
    """`s_state.<field> = v[i]` for every i, in the host's order.

    Catches the reordering case, which the length check cannot see.
    """
    text = TASKS_C.read_text()
    pairs = dict(
        (int(idx), name)
        for name, idx in re.findall(r"s_state\.(\w+)\s*=\s*v\[(\d+)\]", text)
    )
    assert len(pairs) == len(STATE_FIELDS), (
        f"firmware assigns {len(pairs)} state fields, host sends "
        f"{len(STATE_FIELDS)}")
    for i, field in enumerate(STATE_FIELDS):
        assert pairs.get(i) == field, (
            f"state field {i} is {field!r} on the host and "
            f"{pairs.get(i)!r} in tasks.c")


def test_the_diag_frame_carries_every_counter_the_host_expects():
    """The DIAG array's width has to match DIAG_FIELDS.

    The host raises on a wrong-sized DIAG payload, so this fails loudly rather
    than silently. It is here because the same week-10 edit touched it, and a
    counter added on one side only is a whole campaign's diagnostics lost.
    """
    text = TASKS_C.read_text()
    m = re.search(r"uint32_t u32\[(\d+)\]", text)
    assert m, "the DIAG counter array was not found in tasks.c"
    assert int(m.group(1)) == len(DIAG_FIELDS)


@pytest.mark.parametrize("field", ["t_batt_c", "actor_steps", "actor_wcet_us"])
def test_week10_additions_reached_the_firmware(field):
    """Named individually, because these three are why this file exists."""
    assert field in TASKS_H.read_text()
