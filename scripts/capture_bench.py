"""Capture the on-device benchmark lines from the console into JSON.

Gates G1 and G5 print their results with printf and, until now, were read off
a serial monitor and copied into a note by hand. That was survivable while
there was one build to measure. The move to the Arduino core means every one
of them has to be taken again, on two toolchains, so the transcription step is
now the least reliable part of the measurement and is worth removing.

The firmware prints one `EVPIL-<tag> key=value ...` line per result. This reads
them off the port, parses the key-value pairs, and writes them with the build
that produced them, so a number in a note can be traced to a command.

    ./scripts/arduino_build.sh --flash -DRUN_G1_BENCHMARK=1
    PYTHONPATH="src:." python3 scripts/capture_bench.py --tag G1 \\
        --toolchain arduino --out-json docs/g1-arduino.json

Nothing here interprets the numbers or compares them to a threshold. It is a
transcriber.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

import serial

LINE = re.compile(rb"EVPIL-([A-Z0-9]+)\s+(.*)")


def parse_pairs(blob: str) -> dict:
    """`seq=32 d_model=64 forward_us=36.4` into a dict, numbers as numbers."""
    out: dict = {}
    for token in blob.split():
        if "=" not in token:
            continue
        key, _, value = token.partition("=")
        try:
            out[key] = int(value)
        except ValueError:
            try:
                out[key] = float(value)
            except ValueError:
                out[key] = value
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/cu.usbmodem1101")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--tag", default="G1",
                    help="the EVPIL- tag to collect, e.g. G1, G5, BOARD")
    ap.add_argument("--seconds", type=float, default=60.0,
                    help="how long to listen before giving up")
    ap.add_argument("--expect", type=int, default=1,
                    help="stop early once this many lines have arrived")
    ap.add_argument("--toolchain", default="idf", choices=("idf", "arduino"),
                    help="recorded alongside the numbers, not detected")
    ap.add_argument("--note", default="",
                    help="free text recorded with the capture")
    ap.add_argument("--out-json", default=None)
    args = ap.parse_args()

    want = args.tag.encode()
    lines: list[dict] = []
    raw: list[str] = []

    print(f"listening on {args.port} for EVPIL-{args.tag} "
          f"({args.seconds:.0f} s, want {args.expect})")
    deadline = time.time() + args.seconds
    with serial.Serial(args.port, args.baud, timeout=0.5) as ser:
        while time.time() < deadline and len(lines) < args.expect:
            chunk = ser.readline()
            if not chunk:
                continue
            m = LINE.search(chunk)
            if not m:
                continue
            tag, rest = m.group(1), m.group(2)
            text = chunk.decode("utf-8", "replace").strip()
            if tag != want:
                # Kept out of the result but shown, because EVPIL-BOARD on
                # boot is how you tell the board came up at all.
                print(f"  (other) {text}")
                continue
            raw.append(text)
            lines.append(parse_pairs(rest.decode("utf-8", "replace")))
            print(f"  {text}")

    if not lines:
        raise SystemExit(
            f"no EVPIL-{args.tag} line in {args.seconds:.0f} s. The bench "
            f"build prints once at boot, so reset the board while this is "
            f"listening, or reflash with the benchmark switch set.")

    payload = {
        "tag": args.tag,
        "toolchain": args.toolchain,
        "port": args.port,
        "captured_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "note": args.note,
        "lines": lines,
        "raw": raw,
    }
    if args.out_json:
        out = Path(args.out_json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2) + "\n")
        print(f"wrote {out}")
    else:
        print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
