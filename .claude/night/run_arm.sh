#!/usr/bin/env bash
# Drive one arm of the PIL campaign to completion, tolerating a transient link
# failure without losing the night.
#
# The campaign script already resumes: it runs one cell per process, writes the
# file, and re-execs. So a relaunch after a crash costs nothing but the cell
# that was in flight. Run 9 of the actor arm died on
# "opened but sent nothing in 6 attempts", the board was healthy thirty seconds
# later, and without a wrapper that transient would have ended the run.
#
# The budgets are fixed here, deliberately, rather than decided while watching
# a failure: twenty relaunches, and three consecutive relaunches that record no
# new run means stop and leave it for a human.
#
#   .claude/night/run_arm.sh <controller> <out-json> <log>
set -u
CONTROLLER="$1"; OUT="$2"; LOG="$3"
PORT=/dev/cu.usbmodem101
CAP=20
STALL=0

count() { python3 -c "import json,sys
try: print(len(json.load(open('$OUT'))['runs']))
except Exception: print(0)"; }

while true; do
    N=$(count)
    if [ "$N" -ge 18 ]; then echo "ARM COMPLETE: $CONTROLLER 18/18"; exit 0; fi
    if [ "$CAP" -le 0 ]; then echo "RELAUNCH CAP REACHED: $CONTROLLER $N/18"; exit 1; fi
    PYTHONPATH="src:." python3 scripts/run_pil_campaign.py \
        --port "$PORT" --controller "$CONTROLLER" --out-json "$OUT" >> "$LOG" 2>&1
    M=$(count)
    if [ "$M" -le "$N" ]; then
        STALL=$((STALL + 1))
        echo "NO PROGRESS (consecutive $STALL) at $M/18 on $CONTROLLER"
        if [ "$STALL" -ge 3 ]; then
            echo "STALLED three times at $M/18 on $CONTROLLER; stopping"; exit 1
        fi
    else
        STALL=0
    fi
    CAP=$((CAP - 1))
    sleep 5
done
