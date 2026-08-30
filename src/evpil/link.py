"""Host side of the PIL serial link: byte-stream framing and a pyserial wrapper."""

from __future__ import annotations

import struct
import time
from collections.abc import Iterator

import serial

from evpil.protocol import (
    CRC_SIZE, HEADER_SIZE, MAGIC, BadFrame, FrameType, unpack_frame,
)

_MAGIC_LE = struct.pack("<H", MAGIC)


class FrameAssembler:
    """Turns an arbitrarily-chunked byte stream into whole frames.

    Resynchronises by scanning for the magic prefix, so a corrupt or partial
    frame costs at most one frame rather than desynchronising the link.
    """

    def __init__(self) -> None:
        self._buf = bytearray()
        self._last_seq: int | None = None
        self.frames_ok = 0
        self.frames_bad = 0
        self.frames_dropped = 0

    def feed(self, data: bytes) -> Iterator[tuple[FrameType, int, int, bytes]]:
        self._buf.extend(data)

        while True:
            start = self._buf.find(_MAGIC_LE)
            if start < 0:
                # Keep one trailing byte: magic may straddle the chunk boundary.
                del self._buf[: max(0, len(self._buf) - 1)]
                return
            if start > 0:
                del self._buf[:start]

            if len(self._buf) < HEADER_SIZE + CRC_SIZE:
                return

            total = HEADER_SIZE + self._buf[3] + CRC_SIZE
            if len(self._buf) < total:
                return

            candidate = bytes(self._buf[:total])
            try:
                ftype, seq, t_us, payload = unpack_frame(candidate)
            except BadFrame:
                self.frames_bad += 1
                del self._buf[:2]      # skip this magic, rescan from the next byte
                continue

            del self._buf[:total]
            self.frames_ok += 1

            if self._last_seq is not None:
                gap = (seq - self._last_seq - 1) & 0xFFFFFFFF
                if 0 < gap < 1000:     # ignore wraps and resets
                    self.frames_dropped += gap
            self._last_seq = seq

            yield ftype, seq, t_us, payload


class SerialLink:
    """Blocking serial transport around FrameAssembler."""

    def __init__(self, port: str, baud: int = 921600) -> None:
        self.port = port
        self.baud = baud
        self._ser: serial.Serial | None = None
        self.asm = FrameAssembler()
        self._pending: list[tuple[FrameType, int, int, bytes]] = []

    def open(self) -> None:
        self._ser = serial.Serial(self.port, self.baud, timeout=0)
        self._ser.reset_input_buffer()

    def close(self) -> None:
        if self._ser is not None:
            self._ser.close()
            self._ser = None

    def send(self, frame: bytes) -> None:
        assert self._ser is not None, "call open() first"
        self._ser.write(frame)

    def recv(self, timeout_s: float = 0.1):
        assert self._ser is not None, "call open() first"
        deadline = time.perf_counter() + timeout_s
        while True:
            if self._pending:
                return self._pending.pop(0)
            waiting = self._ser.in_waiting
            if waiting:
                self._pending.extend(self.asm.feed(self._ser.read(waiting)))
                continue
            if time.perf_counter() >= deadline:
                return None
            time.sleep(0.0002)

    @property
    def stats(self) -> dict[str, int]:
        return {
            "frames_ok": self.asm.frames_ok,
            "frames_bad": self.asm.frames_bad,
            "frames_dropped": self.asm.frames_dropped,
        }

    def __enter__(self) -> "SerialLink":
        self.open()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
