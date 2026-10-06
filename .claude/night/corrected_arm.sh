#!/usr/bin/env bash
# One arm of the campaign on the corrected plant (the power ceiling now limits
# torque). Writes to week11 files; the week-10 campaigns stay as measured.
#
#   .claude/night/corrected_arm.sh rule|actor
set -u
cd "/Users/manikantagonugondla/Desktop/EV Drives Improvement"
ARM="$1"
HDR=firmware/main/sac_actor_weights.h
BAK="/private/tmp/claude-501/-Users-manikantagonugondla-Desktop-EV-Drives-Improvement/16b32815-3128-4659-a851-d63917dc8c6e/scratchpad/sac_actor_weights.h.bak"
PORT=/dev/cu.usbmodem101
OUT=docs/week11-pil-corrected-$ARM.json
restore_header() {
    if [ ! -f "$HDR" ] && [ -f "$BAK" ]; then cp "$BAK" "$HDR"; echo "restored $HDR"; fi
}
trap restore_header EXIT INT TERM
cp "$HDR" "$BAK"
if [ "$ARM" = rule ]; then
    rm -f "$HDR"
    EVPIL_ARDUINO_DIR="$HOME/.cache/evpil-arduino-rule" EVPIL_PORT="$PORT" \
        ./scripts/arduino_build.sh --flash -DFAULT_INJECT=0 -DFALLBACK_ENABLED=1 \
        > .claude/night/corrected-$ARM-build.log 2>&1
    RC=$?
    restore_header
else
    EVPIL_PORT="$PORT" ./scripts/arduino_build.sh --flash \
        -DFAULT_INJECT=0 -DFALLBACK_ENABLED=1 > .claude/night/corrected-$ARM-build.log 2>&1
    RC=$?
fi
[ "$RC" -eq 0 ] || { echo "$ARM BUILD FAILED"; exit 1; }
echo "$ARM image flashed"
./.claude/night/run_arm.sh "$ARM" "$OUT" .claude/night/corrected-$ARM.log
