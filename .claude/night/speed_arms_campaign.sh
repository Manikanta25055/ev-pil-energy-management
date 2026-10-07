#!/usr/bin/env bash
# The speed-loop arms on the board, all with the rule manager as the energy
# manager: the loop as shipped (b0, SPEED_KALMAN=0), the two-state Kalman
# estimate (b5, =3) and that plus the fault detector (b6, =4).
# Six cells each: three cycles at the noise floor, then US06 at the floor,
# 3x and 10x sensor noise. One image per arm; each run must report the
# estimator it was asked for or it is refused.
set -u
cd "/Users/manikantagonugondla/Desktop/EV Drives Improvement"
HDR=firmware/main/sac_actor_weights.h
BAK="/private/tmp/claude-501/-Users-manikantagonugondla-Desktop-EV-Drives-Improvement/16b32815-3128-4659-a851-d63917dc8c6e/scratchpad/sac_actor_weights.h.speedarms.bak"
PORT=/dev/cu.usbmodem101
N=6
LIMIT=16
restore_header() {
    if [ ! -f "$HDR" ] && [ -f "$BAK" ]; then cp "$BAK" "$HDR"; echo "restored $HDR"; fi
}
trap restore_header EXIT INT TERM
cp "$HDR" "$BAK"
count() { python3 -c "import json
try: print(len(json.load(open('$1'))['runs']))
except Exception: print(0)"; }
run_cells() {   # arm mode out
    local CAP=14 STALL=0
    while [ "$(count $3)" -lt $N ]; do
        [ "$CAP" -gt 0 ] || { echo "RELAUNCH CAP REACHED: $1 $(count $3)/$N"; return 1; }
        local B=$(count $3)
        PYTHONPATH="src:." python3 scripts/run_pil_campaign.py --port "$PORT" \
            --controller rule --axis driving_condition --axis sensor_noise \
            --speed-est $2 --out-json "$3" >> .claude/night/speed-arms-$1.log 2>&1
        if [ "$(count $3)" -le "$B" ]; then
            STALL=$((STALL + 1)); echo "NO PROGRESS ($STALL) on $1 at $(count $3)/$N"
            [ "$STALL" -lt 3 ] || { echo "STALLED: $1"; return 1; }
        else STALL=0; fi
        CAP=$((CAP - 1)); sleep 5
    done
}
for PAIR in b0:0 b5:3 b6:4; do
    ARM=${PAIR%%:*}; MODE=${PAIR##*:}
    OUT=docs/week12-speed-arms-$ARM.json
    if [ "$(count $OUT)" -lt $N ] || [ ! -f ".claude/night/speed-arms-$ARM.checked" ]; then
        rm -f "$HDR"
        EVPIL_ARDUINO_DIR="$HOME/.cache/evpil-arduino-speed-$ARM" EVPIL_PORT="$PORT" \
            ./scripts/arduino_build.sh --flash -DFAULT_INJECT=0 -DFALLBACK_ENABLED=1 \
            -DSPEED_KALMAN=$MODE > .claude/night/speed-arms-$ARM-build.log 2>&1
        RC=$?
        restore_header
        [ "$RC" -eq 0 ] || { echo "$ARM BUILD FAILED"; exit 1; }
        echo "$ARM image flashed (SPEED_KALMAN=$MODE)"
        run_cells $ARM $MODE $OUT || exit 1
        # Once: set aside any cell the host disturbed and take it again.
        python3 - <<PY
import json
d=json.load(open("$OUT"))
bad=[r for r in d["runs"] if r["dropped_frames"]>$LIMIT and r["tracking_rmse_mps"]<1.0]
if bad:
    json.dump({"port":d["port"],"reason":"dropped_frames > $LIMIT; taken again","runs":bad},open("docs/week12-speed-arms-$ARM-disturbed.json","w"),indent=1)
    json.dump({"port":d["port"],"runs":[r for r in d["runs"] if r not in bad]},open("$OUT","w"),indent=1)
print("$ARM set aside:",[(r["scenario"],r["level"],r["dropped_frames"]) for r in bad])
PY
        run_cells $ARM $MODE $OUT || exit 1
        touch ".claude/night/speed-arms-$ARM.checked"
        echo "$ARM complete: $(count $OUT)/$N"
    fi
done
# Leave the board as it was found: the normal actor image, handling on.
EVPIL_PORT="$PORT" ./scripts/arduino_build.sh --flash -DFAULT_INJECT=0 -DFALLBACK_ENABLED=1 \
    > .claude/night/speed-arms-restore-build.log 2>&1 && echo "normal actor image restored"
echo "SPEED ARMS CAMPAIGN COMPLETE"
