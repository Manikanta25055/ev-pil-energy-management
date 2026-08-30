#!/usr/bin/env bash
# Gate G3 campaign: reset the board, then measure the closed loop.
#
# The two steps are separate processes on purpose. Measured on this machine:
# resetting through esptool and then opening the port from a separate process
# reads frames every time; doing both from one Python process reads zero bytes
# every time, at any baud, with any settling delay, and with or without
# flushing the input buffer. The process boundary is the thing that matters.
# Why macOS behaves this way was not chased further: it is a host-side USB CDC
# quirk, not a property of the loop under test, and a deterministic workaround
# is worth more here than an explanation.
#
#   ./scripts/g3_campaign.sh [minutes] [port]

set -euo pipefail

MINUTES="${1:-10}"
PORT="${2:-/dev/cu.usbmodem1101}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

PY_IDF="$(ls -d "$HOME"/.espressif/python_env/*/bin/python 2>/dev/null | head -1)"
if [ -z "$PY_IDF" ]; then
    echo "esptool interpreter not found under ~/.espressif/python_env" >&2
    exit 1
fi

echo "resetting $PORT"
"$PY_IDF" -m esptool --chip esp32s3 -p "$PORT" --after hard_reset run >/dev/null
sleep 1

cd "$ROOT"
PYTHONPATH="src:." exec python3 scripts/run_g3.py \
    --minutes "$MINUTES" --port "$PORT" --no-reset "${@:3}"
