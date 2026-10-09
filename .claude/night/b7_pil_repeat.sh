#!/usr/bin/env bash
# Repeats of the board fault campaign for B7 with the rule monitor (mode 6)
# and B7 alone (5), with other draws of noise: seed offsets 100 and 200.
# 42 cells per arm per offset. The board is left holding the actor image.
set -u
MAIN="/Users/manikantagonugondla/Desktop/EV Drives Improvement"
cd "$MAIN"
PORT=/dev/cu.usbmodem101
N=42
LOG=.claude/night
count() { python3 -c "import json
try: print(len(json.load(open('$1'))['runs']))
except Exception: print(0)"; }
run_cells() {   # arm mode out offset
    local CAP=40 STALL=0
    while [ "$(count $3)" -lt $N ]; do
        [ "$CAP" -gt 0 ] || { echo "RELAUNCH CAP REACHED: $1 $(count $3)/$N"; return 1; }
        local B=$(count $3)
        PYTHONPATH="src:." python3 scripts/run_b7_pil.py --port "$PORT" \
            --speed-est $2 --seed-offset $4 --out-json "$3" >> $LOG/b7-pil-repeat-$1.log 2>&1
        if [ "$(count $3)" -le "$B" ]; then
            STALL=$((STALL + 1)); echo "NO PROGRESS ($STALL) on $1 at $(count $3)/$N"
            [ "$STALL" -lt 3 ] || { echo "STALLED: $1"; return 1; }
            sleep 10
        else STALL=0; fi
        CAP=$((CAP - 1)); sleep 3
    done
}
FAILED=0
for PAIR in b7mon:6 b7:5; do
    ARM=${PAIR%%:*}; MODE=${PAIR##*:}
    EVPIL_PORT="$PORT" ./scripts/b7_pil_build.sh $MODE > $LOG/b7-pil-repeat-$ARM-build.log 2>&1 \
        || { echo "$ARM BUILD FAILED"; FAILED=1; break; }
    echo "$ARM image flashed (SPEED_KALMAN=$MODE)"; sleep 5
    for OFF in 100 200; do
        OUT=docs/week14-b7-pil-$ARM-seed$OFF.json
        run_cells $ARM $MODE $OUT $OFF || { FAILED=1; break 2; }
        echo "$ARM offset $OFF complete: $(count $OUT)/$N"
    done
done
( EVPIL_PORT="$PORT" ./scripts/arduino_build.sh --flash -DFAULT_INJECT=0 -DFALLBACK_ENABLED=1 ) \
    > $LOG/b7-pil-repeat-restore-build.log 2>&1 && echo "actor image flashed" || echo "RESTORE BUILD FAILED"
sleep 5
PYTHONPATH="src:." python3 scripts/run_b7_pil.py --port "$PORT" --probe 2>> $LOG/b7-pil-probe.log | tail -1 > $LOG/b7-pil-repeat-restored.json
cat $LOG/b7-pil-repeat-restored.json
[ "$FAILED" -eq 0 ] && echo "B7 PIL REPEAT COMPLETE" || echo "B7 PIL REPEAT STOPPED EARLY"
