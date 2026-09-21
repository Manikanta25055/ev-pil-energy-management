#!/usr/bin/env bash
# Carry the campaign from "actor arm running" to "both arms merged".
#
# Waits for the actor arm, flashes the rule image, runs the rule arm, merges.
# Written so the night does not stall at a transition waiting for a human.
#
# The rule image is selected by the ABSENCE of the generated weights header.
# Nothing under firmware/ is edited: the header is copied aside and restored,
# and the restore is in a trap so it happens even if the build dies or the
# script is killed. A dirty firmware/ would invalidate the next build in a way
# that is hard to notice.
set -u
cd "/Users/manikantagonugondla/Desktop/EV Drives Improvement"

SCRATCH="/private/tmp/claude-501/-Users-manikantagonugondla-Desktop-EV-Drives-Improvement/61a84646-b87b-4d3a-8fb2-d43f441e592e/scratchpad"
HDR=firmware/main/sac_actor_weights.h
BAK="$SCRATCH/sac_actor_weights.h.bak"
PORT=/dev/cu.usbmodem101

restore_header() {
    if [ ! -f "$HDR" ] && [ -f "$BAK" ]; then
        cp "$BAK" "$HDR"
        echo "restored $HDR"
    fi
}
trap restore_header EXIT INT TERM

count() { python3 -c "import json
try: print(len(json.load(open('$1'))['runs']))
except Exception: print(0)"; }

echo "waiting for the actor arm to finish"
for _ in $(seq 1 240); do
    [ "$(count docs/week10-pil-actor.json)" -ge 18 ] && break
    pgrep -f "run_arm.sh actor" >/dev/null 2>&1 || {
        if [ "$(count docs/week10-pil-actor.json)" -lt 18 ]; then
            echo "ACTOR WRAPPER GONE at $(count docs/week10-pil-actor.json)/18; stopping"
            exit 1
        fi
    }
    sleep 60
done

N=$(count docs/week10-pil-actor.json)
if [ "$N" -lt 18 ]; then echo "TIMED OUT waiting for actor arm at $N/18"; exit 1; fi
echo "actor arm complete: $N/18"

echo "flashing the rule image"
cp "$HDR" "$BAK"
rm -f "$HDR"
EVPIL_ARDUINO_DIR="$HOME/.cache/evpil-arduino-rule" EVPIL_PORT="$PORT" \
    ./scripts/arduino_build.sh --flash -DFAULT_INJECT=0 -DFALLBACK_ENABLED=1 \
    > .claude/night/rule-build.log 2>&1
BUILD_RC=$?
restore_header
if [ "$BUILD_RC" -ne 0 ]; then
    echo "RULE BUILD FAILED rc=$BUILD_RC; see .claude/night/rule-build.log"; exit 1
fi
if ! git diff --quiet -- firmware/; then
    echo "firmware/ is dirty after the rule build; stopping rather than measuring"
    git status --porcelain firmware/
    exit 1
fi
echo "rule image flashed, firmware/ clean"

echo "running the rule arm"
./.claude/night/run_arm.sh rule docs/week10-pil-rule.json .claude/night/pil-rule.log \
    >> .claude/night/arm-rule-wrapper.log 2>&1
R=$(count docs/week10-pil-rule.json)
if [ "$R" -lt 18 ]; then echo "RULE ARM INCOMPLETE at $R/18"; exit 1; fi

echo "merging both arms"
python3 -c "
import json
a=json.load(open('docs/week10-pil-actor.json'))
b=json.load(open('docs/week10-pil-rule.json'))
runs=a['runs']+b['runs']
keys={(r['scenario'],r['level'],r['controller'],r['seed']) for r in runs}
assert len(keys)==len(runs)==36, f'{len(runs)} runs, {len(keys)} distinct'
json.dump({'port':a['port'],'runs':runs}, open('docs/week10-pil-campaign.json','w'), indent=1)
print('merged 36 runs')
"
echo "CAMPAIGN COMPLETE"
