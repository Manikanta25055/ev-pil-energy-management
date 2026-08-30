"""Host side of the PIL serial link: byte-stream framing and a pyserial wrapper."""

from __future__ import annotations

import glob
import os
import struct
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

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
        # Sequence numbers are tracked per frame type. The control loop and the
        # diagnostics task each run their own counter, so a single shared
        # `last_seq` sees every alternation between them as a gap and reports
        # thousands of drops on a link that dropped nothing. Gate G3 is stated
        # as zero dropped frames, so this counter decides a verdict.
        self._last_seq: dict[int, int] = {}
        self.frames_ok = 0
        self.frames_bad = 0
        self.frames_dropped = 0
        self.dropped_by_type: dict[int, int] = {}

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

            previous = self._last_seq.get(int(ftype))
            if previous is not None:
                gap = (seq - previous - 1) & 0xFFFFFFFF
                if 0 < gap < 1000:     # ignore wraps and resets
                    self.frames_dropped += gap
                    self.dropped_by_type[int(ftype)] = \
                        self.dropped_by_type.get(int(ftype), 0) + gap
            self._last_seq[int(ftype)] = seq

            yield ftype, seq, t_us, payload


def _esptool_interpreter() -> str | None:
    """An interpreter that can `-m esptool`, preferring this one.

    esptool ships inside the ESP-IDF virtual environment rather than the
    system Python, so the caller's interpreter usually cannot import it.
    Searching for one that can keeps the reset working whether the script is
    run from inside an IDF shell or outside it.
    """
    import importlib.util

    if importlib.util.find_spec("esptool") is not None:
        return sys.executable

    for pattern in ("~/.espressif/python_env/*/bin/python",
                    "~/.espressif/python_env/*/bin/python3"):
        for candidate in sorted(glob.glob(os.path.expanduser(pattern))):
            probe = subprocess.run(
                [candidate, "-c", "import esptool"],
                capture_output=True, timeout=30,
            )
            if probe.returncode == 0:
                return candidate
    return None


def usb_jtag_hard_reset(port: str, chip: str = "esp32s3") -> bool:
    """Restart an ESP32-S3 over its native USB-Serial-JTAG. Returns success.

    Needed, not optional. Measured on this board: the peripheral streams at
    100 Hz with zero CRC failures on the first host connection after a reset,
    and delivers zero bytes on every reopen after that. Neither DTR nor RTS
    toggling from pyserial revives it -- replicating esptool's documented
    USB-JTAG reset sequence by hand was tried and did not work, so the reset
    goes through esptool itself, which does.

    That means the port re-enumerates and the caller must open it afterwards
    rather than before.
    """
    interpreter = _esptool_interpreter()
    if interpreter is None:
        return False

    cmd = [interpreter, "-m", "esptool", "--chip", chip, "-p", port,
           "--after", "hard_reset", "run"]
    try:
        done = subprocess.run(cmd, capture_output=True, timeout=90)
    except (OSError, subprocess.TimeoutExpired):
        return False
    if done.returncode != 0:
        return False

    for _ in range(60):                 # wait for the port to come back
        if Path(port).exists():
            break
        time.sleep(0.1)
    time.sleep(0.4)
    return True


def reset_and_reexec(port: str, drop_flag: str = "--reset",
                     add_flag: str = "--no-reset") -> None:
    """Reset the board, then restart this process to talk to it.

    The re-exec is not decoration. Measured on this machine: resetting through
    esptool and then opening the port from a *different* process reads frames
    every time, and doing both from the *same* process reads zero bytes every
    time, at any baud and after any settling delay. The boundary that matters
    is the process image, so the reliable sequence is to reset and then become
    a new process.

    Diagnosing why macOS behaves this way is not on the critical path for a
    timing gate, and a workaround that is understood and deterministic beats
    one that is elegant and intermittent. The cost is one extra exec.
    """
    if not usb_jtag_hard_reset(port):
        print("  reset failed: esptool not found or refused. Continuing "
              "without it; if no frames arrive, reset the board by hand.")
        return

    argv = [a for a in sys.argv if a != drop_flag] + [add_flag]
    os.execv(sys.executable, [sys.executable, *argv])


class SerialLink:
    """Blocking serial transport around FrameAssembler."""

    def __init__(self, port: str, baud: int = 921600, reset: bool = False) -> None:
        self.port = port
        self.baud = baud
        self.reset = reset
        self.reset_performed = False
        self.open_attempts = 0
        self._ser: serial.Serial | None = None
        self.asm = FrameAssembler()
        self._pending: list[tuple[FrameType, int, int, bytes]] = []

    def open(self, attempts: int = 6, probe_s: float = 1.5) -> None:
        """Open the port, retrying until the device is actually sending.

        Measured on the S3's native USB-Serial-JTAG: the first host connection
        after a board reset receives nothing at all, and the next one receives
        the full 100 Hz stream. Reopening is what establishes the link, so the
        retry is the mechanism rather than a defence against flakiness.

        Without this the caller waits out its whole timeout and reports a dead
        board, which is the wrong diagnosis and cost a long detour to reach.
        """
        # The reset happens before the port is opened, not after: it makes the
        # device re-enumerate, so a handle taken beforehand would be stale.
        self.reset_performed = usb_jtag_hard_reset(self.port) if self.reset else False

        last_error: OSError | None = None
        for attempt in range(attempts):
            try:
                ser = serial.Serial(self.port, self.baud, timeout=0)
            except OSError as exc:          # port still re-enumerating
                last_error = exc
                time.sleep(0.5)
                continue

            deadline = time.perf_counter() + probe_s
            while time.perf_counter() < deadline:
                if ser.in_waiting:
                    self._ser = ser
                    self.open_attempts = attempt + 1
                    return
                time.sleep(0.01)

            ser.close()
            time.sleep(0.2)

        if last_error is not None:
            raise last_error
        raise OSError(
            f"{self.port} opened but sent nothing in {attempts} attempts of "
            f"{probe_s:.1f}s. Is the firmware running?"
        )

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
            "open_attempts": self.open_attempts,
        }

    def __enter__(self) -> "SerialLink":
        self.open()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
