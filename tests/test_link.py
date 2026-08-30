import pytest
from evpil.link import FrameAssembler
from evpil.protocol import BadFrame, FrameType, pack_actuation, pack_state


def test_assembler_yields_single_frame():
    asm = FrameAssembler()
    frame = pack_state(1, 100, [0.0] * 8)
    got = list(asm.feed(frame))
    assert len(got) == 1
    assert got[0][0] is FrameType.STATE
    assert got[0][1] == 1


def test_assembler_handles_split_across_chunks():
    asm = FrameAssembler()
    frame = pack_state(7, 200, [1.0] * 8)
    assert list(asm.feed(frame[:5])) == []
    assert list(asm.feed(frame[5:20])) == []
    got = list(asm.feed(frame[20:]))
    assert len(got) == 1
    assert got[0][1] == 7


def test_assembler_handles_two_frames_in_one_chunk():
    asm = FrameAssembler()
    chunk = pack_state(1, 1, [0.0] * 8) + pack_actuation(2, 2, [0.0] * 3)
    got = list(asm.feed(chunk))
    assert [g[1] for g in got] == [1, 2]


def test_assembler_resyncs_after_garbage():
    asm = FrameAssembler()
    frame = pack_state(9, 300, [2.0] * 8)
    got = list(asm.feed(b"\x00\xff\x13\x37" + frame))
    assert len(got) == 1
    assert got[0][1] == 9


def test_assembler_drops_corrupt_frame_and_recovers():
    asm = FrameAssembler()
    bad = bytearray(pack_state(1, 1, [0.0] * 8))
    bad[20] ^= 0xFF
    good = pack_state(2, 2, [0.0] * 8)

    got = list(asm.feed(bytes(bad) + good))
    assert [g[1] for g in got] == [2]
    assert asm.frames_bad == 1
    assert asm.frames_ok == 1


def test_assembler_counts_sequence_gaps():
    asm = FrameAssembler()
    list(asm.feed(pack_state(1, 1, [0.0] * 8)))
    list(asm.feed(pack_state(4, 4, [0.0] * 8)))
    assert asm.frames_dropped == 2
