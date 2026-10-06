#!/usr/bin/env bash
# Ablation A4 swept again on the corrected plant, actor in the loop.
# Same lengths, onsets and switches as docs/week9-a4.md sections 10 and 11.
# Writes docs/week11-a4-{on,off}-{len}s.json; the week-9 files stay as measured.
# Skips any length whose file already exists, so a relaunch resumes.
set -u
cd "/Users/manikantagonugondla/Desktop/EV Drives Improvement"
PORT=/dev/cu.usbmodem101
[ -f firmware/main/sac_actor_weights.h ] || { echo "no actor header"; exit 1; }
for MODE in on off; do
    if [ "$MODE" = on ]; then FB=1; FLAG=""; else FB=0; FLAG="--fallback-off"; fi
    NEED=0
    for S in 0.2 0.5 1 2 3 4 5 10; do
        [ -f "docs/week11-a4-$MODE-${S}s.json" ] || NEED=1
    done
    [ "$NEED" -eq 1 ] || continue
    EVPIL_ARDUINO_DIR="$HOME/.cache/evpil-arduino-a4$MODE" EVPIL_PORT="$PORT" \
        ./scripts/arduino_build.sh --flash -DFAULT_INJECT=0 -DFALLBACK_ENABLED=$FB \
        > .claude/night/corrected-a4-$MODE-build.log 2>&1 \
        || { echo "A4 $MODE BUILD FAILED"; exit 1; }
    echo "A4 $MODE image flashed"
    for S in 0.2 0.5 1 2 3 4 5 10; do
        OUT="docs/week11-a4-$MODE-${S}s.json"
        [ -f "$OUT" ] && continue
        for TRY in 1 2 3; do
            PYTHONPATH="src:." python3 scripts/run_a4_closedloop.py --port "$PORT" \
                --blackout-s "$S" $FLAG --out-json "$OUT" \
                >> .claude/night/corrected-a4-$MODE.log 2>&1 && break
            echo "A4 $MODE ${S}s attempt $TRY failed"; rm -f "$OUT"; sleep 5
        done
        [ -f "$OUT" ] || { echo "A4 $MODE ${S}s GAVE UP"; exit 1; }
        echo "A4 $MODE ${S}s done"
    done
done
echo "A4 SWEEP COMPLETE"
