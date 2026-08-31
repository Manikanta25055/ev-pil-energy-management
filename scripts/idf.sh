#!/usr/bin/env bash
# Run idf.py against this project's firmware.
#
# Two things this wrapper exists for. The IDF checkout on this machine lives
# under a path with spaces, and its tools/idf.py is not marked executable, so
# `idf.py build` after sourcing export.sh fails with a permission error that
# looks like a PATH problem and is not one. Invoking it through the IDF's own
# interpreter sidesteps both.
#
#   ./scripts/idf.sh build
#   ./scripts/idf.sh -DFAULT_INJECT=1 build
#   ./scripts/idf.sh -p /dev/cu.usbmodem1101 flash

set -euo pipefail

IDF_PATH="${IDF_PATH:-/Users/manikantagonugondla/Desktop/Espressif 32 C6 Dev-Kit/esp-idf-v5.4}"
export IDF_PATH
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# shellcheck disable=SC1091
source "$IDF_PATH/export.sh" >/dev/null 2>&1

PY_IDF="$(ls -d "$HOME"/.espressif/python_env/*/bin/python | head -1)"
cd "$ROOT/firmware"
exec "$PY_IDF" "$IDF_PATH/tools/idf.py" "$@"
