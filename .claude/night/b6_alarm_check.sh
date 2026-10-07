#!/usr/bin/env bash
# B6 on a healthy sensor, clean cycles only, twice over, on the image that
# reports which test raised the flag and where. To explain, or fail to
# reproduce, the one false alarm of the first speed-arms campaign.
set -u
cd "/Users/manikantagonugondla/Desktop/EV Drives Improvement"
HDR=firmware/main/sac_actor_weights.h
BAK="/private/tmp/claude-501/-Users-manikantagonugondla-Desktop-EV-Drives-Improvement/16b32815-3128-4659-a851-d63917dc8c6e/scratchpad/sac_actor_weights.h.alarmcheck.bak"
PORT=/dev/cu.usbmodem101
restore_header() { if [ ! -f "$HDR" ] && [ -f "$BAK" ]; then cp "$BAK" "$HDR"; echo "restored $HDR"; fi; }
trap restore_header EXIT INT TERM
cp "$HDR" "$BAK"
count() { python3 -c "import json
try: print(len(json.load(open('$1'))['runs']))
except Exception: print(0)"; }
rm -f "$HDR"
EVPIL_ARDUINO_DIR="$HOME/.cache/evpil-arduino-speed-b6" EVPIL_PORT="$PORT" \
    ./scripts/arduino_build.sh --flash -DFAULT_INJECT=0 -DFALLBACK_ENABLED=1 -DSPEED_KALMAN=4 \
    > .claude/night/b6-alarm-build.log 2>&1
RC=$?; restore_header
[ "$RC" -eq 0 ] || { echo "BUILD FAILED"; exit 1; }
echo "b6 image flashed"
for PASS in 1 2; do
    OUT=docs/week12-b6-alarm-check-$PASS.json
    CAP=8
    while [ "$(count $OUT)" -lt 3 ] && [ "$CAP" -gt 0 ]; do
        PYTHONPATH="src:." python3 scripts/run_pil_campaign.py --port "$PORT" --controller rule \
            --axis driving_condition --speed-est 4 --out-json "$OUT" >> .claude/night/b6-alarm.log 2>&1
        CAP=$((CAP - 1)); sleep 5
    done
    echo "pass $PASS: $(count $OUT)/3"
done
EVPIL_PORT="$PORT" ./scripts/arduino_build.sh --flash -DFAULT_INJECT=0 -DFALLBACK_ENABLED=1 \
    > .claude/night/b6-alarm-restore-build.log 2>&1 && echo "normal actor image restored"
echo "B6 ALARM CHECK COMPLETE"
