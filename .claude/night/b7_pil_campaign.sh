#!/usr/bin/env bash
# Injected sensor faults on the board: B7 with the rule monitor (mode 6),
# B7 alone (5), B6 (4). 42 cells each. One image per arm; each run must
# report the estimator it was asked for or it is refused. The board is left
# holding the normal actor image, built from the main checkout.
set -u
W="/Users/manikantagonugondla/Desktop/EV Drives Improvement/.worktrees/sensor-arch"
MAIN="/Users/manikantagonugondla/Desktop/EV Drives Improvement"
cd "$W"
PORT=/dev/cu.usbmodem101
N=42
LOG=.claude/night
count() { python3 -c "import json
try: print(len(json.load(open('$1'))['runs']))
except Exception: print(0)"; }
restore() {
    ( cd "$MAIN" && EVPIL_PORT="$PORT" ./scripts/arduino_build.sh --flash \
        -DFAULT_INJECT=0 -DFALLBACK_ENABLED=1 ) > "$W/$LOG/b7-pil-restore-build.log" 2>&1 \
        && echo "actor image flashed" || echo "RESTORE BUILD FAILED"
    sleep 5
    PYTHONPATH="src:." python3 scripts/run_b7_pil.py --port "$PORT" --probe \
        2>> $LOG/b7-pil-probe.log | tail -1 > $LOG/b7-pil-restored.json
    cat $LOG/b7-pil-restored.json
}
run_cells() {   # arm mode out
    local CAP=40 STALL=0
    while [ "$(count $3)" -lt $N ]; do
        [ "$CAP" -gt 0 ] || { echo "RELAUNCH CAP REACHED: $1 $(count $3)/$N"; return 1; }
        local B=$(count $3)
        PYTHONPATH="src:." python3 scripts/run_b7_pil.py --port "$PORT" \
            --speed-est $2 --out-json "$3" >> $LOG/b7-pil-$1.log 2>&1
        if [ "$(count $3)" -le "$B" ]; then
            STALL=$((STALL + 1)); echo "NO PROGRESS ($STALL) on $1 at $(count $3)/$N"
            [ "$STALL" -lt 3 ] || { echo "STALLED: $1"; return 1; }
            sleep 10
        else STALL=0; fi
        CAP=$((CAP - 1)); sleep 3
    done
}
FAILED=0
for PAIR in b7mon:6 b7:5 b6:4; do
    ARM=${PAIR%%:*}; MODE=${PAIR##*:}
    OUT=docs/week13-b7-pil-$ARM.json
    if [ "$(count $OUT)" -lt $N ]; then
        EVPIL_PORT="$PORT" ./scripts/b7_pil_build.sh $MODE > $LOG/b7-pil-$ARM-build.log 2>&1 \
            || { echo "$ARM BUILD FAILED"; FAILED=1; break; }
        echo "$ARM image flashed (SPEED_KALMAN=$MODE)"
        sleep 5
        run_cells $ARM $MODE $OUT || { FAILED=1; break; }
        echo "$ARM complete: $(count $OUT)/$N"
    fi
done
restore
[ "$FAILED" -eq 0 ] && echo "B7 PIL CAMPAIGN COMPLETE" || echo "B7 PIL CAMPAIGN STOPPED EARLY"
