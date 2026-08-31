import pytest
from evpil.link import FrameAssembler
from evpil.protocol import BadFrame, FrameType, pack_actuation, pack_state


def test_assembler_yields_single_frame():
    asm = FrameAssembler()
    frame = pack_state(1, 100, [0.0] * 10)
    got = list(asm.feed(frame))
    assert len(got) == 1
    assert got[0][0] is FrameType.STATE
    assert got[0][1] == 1


def test_assembler_handles_split_across_chunks():
    asm = FrameAssembler()
    frame = pack_state(7, 200, [1.0] * 10)
    assert list(asm.feed(frame[:5])) == []
    assert list(asm.feed(frame[5:20])) == []
    got = list(asm.feed(frame[20:]))
    assert len(got) == 1
    assert got[0][1] == 7


def test_assembler_handles_two_frames_in_one_chunk():
    asm = FrameAssembler()
    chunk = pack_state(1, 1, [0.0] * 10) + pack_actuation(2, 2, [0.0] * 4)
    got = list(asm.feed(chunk))
    assert [g[1] for g in got] == [1, 2]


def test_assembler_resyncs_after_garbage():
    asm = FrameAssembler()
    frame = pack_state(9, 300, [2.0] * 10)
    got = list(asm.feed(b"\x00\xff\x13\x37" + frame))
    assert len(got) == 1
    assert got[0][1] == 9


def test_assembler_drops_corrupt_frame_and_recovers():
    asm = FrameAssembler()
    bad = bytearray(pack_state(1, 1, [0.0] * 10))
    bad[20] ^= 0xFF
    good = pack_state(2, 2, [0.0] * 10)

    got = list(asm.feed(bytes(bad) + good))
    assert [g[1] for g in got] == [2]
    assert asm.frames_bad == 1
    assert asm.frames_ok == 1


def test_assembler_counts_sequence_gaps():
    asm = FrameAssembler()
    list(asm.feed(pack_state(1, 1, [0.0] * 10)))
    list(asm.feed(pack_state(4, 4, [0.0] * 10)))
    assert asm.frames_dropped == 2


def test_sequence_gaps_are_counted_per_frame_type():
    """Gate G3 is stated as zero dropped frames, so this counter decides it.

    The control loop and the diagnostics task each run their own sequence
    counter. Tracking one shared `last_seq` across both reads every alternation
    between them as a gap: on a real ten-minute run that reported over a
    thousand drops on a link that dropped nothing.
    """
    from evpil.protocol import pack_actuation, pack_state

    asm = FrameAssembler()
    stream = b""
    for seq in range(4):
        stream += pack_state(seq, seq * 100, [0.0] * 10)
        stream += pack_actuation(seq, seq * 100, [0.0] * 4)
    # A third type on its own counter, interleaved at a different rate.
    stream += pack_state(4, 400, [0.0] * 10)

    list(asm.feed(stream))
    assert asm.frames_ok == 9
    assert asm.frames_dropped == 0


def test_a_genuine_gap_in_one_type_is_still_counted():
    from evpil.protocol import pack_state

    asm = FrameAssembler()
    list(asm.feed(pack_state(0, 0, [0.0] * 10)))
    list(asm.feed(pack_state(3, 0, [0.0] * 10)))     # 1 and 2 lost
    assert asm.frames_dropped == 2
    assert asm.dropped_by_type[int(FrameType.STATE)] == 2


def test_a_gap_in_one_type_does_not_pollute_another():
    from evpil.protocol import pack_actuation, pack_state

    asm = FrameAssembler()
    list(asm.feed(pack_state(0, 0, [0.0] * 10)))
    list(asm.feed(pack_actuation(50, 0, [0.0] * 4)))
    list(asm.feed(pack_state(1, 0, [0.0] * 10)))
    assert asm.frames_dropped == 0
