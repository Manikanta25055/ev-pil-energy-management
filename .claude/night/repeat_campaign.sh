#!/usr/bin/env bash
# The repeat campaign, on the build that logs the power ceiling.
#
# Flash actor, run 18; flash rule, run 18; merge and assert 36 distinct cells.
# Writes to a NEW file: the first campaign stays exactly as measured, because
# a repeat whose value is reproducibility must not overwrite the thing it is
# reproducing.
#
# Nothing under firmware/ is edited. The rule image is selected by the absence
# of the generated weights header, copied aside and restored in an EXIT trap.
set -u
cd "/Users/manikantagonugondla/Desktop/EV Drives Improvement"

SCRATCH="/private/tmp/claude-501/-Users-manikantagonugondla-Desktop-EV-Drives-Improvement/61a84646-b87b-4d3a-8fb2-d43f441e592e/scratchpad"
HDR=firmware/main/sac_actor_weights.h
BAK="$SCRATCH/sac_actor_weights.h.bak"
PORT=/dev/cu.usbmodem101
A=docs/week10-pil-campaign-repeat-actor.json
R=docs/week10-pil-campaign-repeat-rule.json
OUT=docs/week10-pil-campaign-repeat.json

restore_header() {
    if [ ! -f "$HDR" ] && [ -f "$BAK" ]; then cp "$BAK" "$HDR"; echo "restored $HDR"; fi
}
trap restore_header EXIT INT TERM
cp "$HDR" "$BAK"

count() { python3 -c "import json
try: print(len(json.load(open('$1'))['runs']))
except Exception: print(0)"; }

if [ "$(count $A)" -lt 18 ]; then
    echo "flashing the actor image"
    EVPIL_PORT="$PORT" ./scripts/arduino_build.sh --flash \
        -DFAULT_INJECT=0 -DFALLBACK_ENABLED=1 > .claude/night/repeat-actor-build.log 2>&1 \
        || { echo "ACTOR BUILD FAILED"; exit 1; }
    git diff --quiet -- firmware/ || { echo "firmware/ dirty after build"; exit 1; }
    echo "actor image flashed, firmware/ clean"
    ./.claude/night/run_arm.sh actor "$A" .claude/night/repeat-actor.log \
        >> .claude/night/repeat-actor-wrapper.log 2>&1
fi
[ "$(count $A)" -ge 18 ] || { echo "REPEAT ACTOR ARM INCOMPLETE at $(count $A)/18"; exit 1; }
echo "repeat actor arm complete"

if [ "$(count $R)" -lt 18 ]; then
    echo "flashing the rule image"
    rm -f "$HDR"
    EVPIL_ARDUINO_DIR="$HOME/.cache/evpil-arduino-rule" EVPIL_PORT="$PORT" \
        ./scripts/arduino_build.sh --flash -DFAULT_INJECT=0 -DFALLBACK_ENABLED=1 \
        > .claude/night/repeat-rule-build.log 2>&1
    RC=$?
    restore_header
    [ "$RC" -eq 0 ] || { echo "RULE BUILD FAILED"; exit 1; }
    git diff --quiet -- firmware/ || { echo "firmware/ dirty after build"; exit 1; }
    echo "rule image flashed, firmware/ clean"
    ./.claude/night/run_arm.sh rule "$R" .claude/night/repeat-rule.log \
        >> .claude/night/repeat-rule-wrapper.log 2>&1
fi
[ "$(count $R)" -ge 18 ] || { echo "REPEAT RULE ARM INCOMPLETE at $(count $R)/18"; exit 1; }
echo "repeat rule arm complete"

python3 -c "
import json
a=json.load(open('$A')); b=json.load(open('$R'))
runs=a['runs']+b['runs']
keys={(r['scenario'],r['level'],r['controller'],r['seed']) for r in runs}
assert len(keys)==len(runs)==36, f'{len(runs)} runs, {len(keys)} distinct'
missing=[r for r in runs if r.get('p_limit_mean_w') is None and 'p_limit_mean_w' not in r.get('diag_delta',{})]
assert not missing, f'{len(missing)} runs carry no power-ceiling telemetry'
json.dump({'port':a['port'],'runs':runs}, open('$OUT','w'), indent=1)
print('merged 36 runs, all carrying the power ceiling')
"
echo "REPEAT CAMPAIGN COMPLETE"
