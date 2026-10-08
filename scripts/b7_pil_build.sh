#!/usr/bin/env bash
# Build and flash a rule-manager image with a chosen speed estimator, without
# touching the tree.
#
# The energy manager is a compile-time choice made by the presence of
# firmware/main/sac_actor_weights.h. The speed-arm campaign of week 12 moved
# that header aside and put it back; this copies the firmware sources and
# scripts/arduino_build.sh to a scratch tree that leaves the header out, and
# builds from there. Nothing in the repository is moved or edited.
#
#   scripts/b7_pil_build.sh 5      B7 alone
#   scripts/b7_pil_build.sh 6      B7 with the rule monitor
#   scripts/b7_pil_build.sh 4      B6
#   scripts/b7_pil_build.sh 6 --no-flash    compile only
set -euo pipefail
MODE="${1:?speed estimator mode: 4, 5 or 6}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRATCH="${EVPIL_B7_SRC:-$HOME/.cache/evpil-b7-src}"
case "$SCRATCH" in *" "*) echo "scratch dir must not contain spaces" >&2; exit 2 ;; esac
rm -rf "$SCRATCH"
mkdir -p "$SCRATCH/scripts" "$SCRATCH/firmware/main"
cp "$ROOT/scripts/arduino_build.sh" "$SCRATCH/scripts/"
cp "$ROOT"/firmware/main/*.c "$ROOT"/firmware/main/*.h "$SCRATCH/firmware/main/"
rm -f "$SCRATCH/firmware/main/sac_actor_weights.h"
FLASH="--flash"
[ "${2:-}" = "--no-flash" ] && FLASH=""
EVPIL_ARDUINO_DIR="$HOME/.cache/evpil-arduino-b7-$MODE" \
    "$SCRATCH/scripts/arduino_build.sh" $FLASH -DFAULT_INJECT=0 \
    -DFALLBACK_ENABLED=1 "-DSPEED_KALMAN=$MODE"
