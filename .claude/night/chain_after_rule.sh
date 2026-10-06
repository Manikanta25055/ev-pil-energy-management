#!/usr/bin/env bash
# After the rule arm and its re-runs: flash the retrained actor, run its arm,
# re-run any cell the host disturbed, merge the two arms, then sweep A4.
set -u
cd "/Users/manikantagonugondla/Desktop/EV Drives Improvement"
R=docs/week11-pil-corrected-rule.json
A=docs/week11-pil-corrected-actor.json
OUT=docs/week11-pil-corrected.json
LIMIT=16
count() { python3 -c "import json
try: print(len(json.load(open('$1'))['runs']))
except Exception: print(0)"; }
while pgrep -f "rerun_disturbed_rule.sh|run_arm.sh rule" >/dev/null; do sleep 20; done
[ "$(count $R)" -ge 18 ] || { echo "RULE ARM INCOMPLETE at $(count $R)/18"; exit 1; }
echo "rule arm complete; starting the actor arm"

./.claude/night/corrected_arm.sh actor || { echo "ACTOR ARM FAILED"; exit 1; }
[ "$(count $A)" -ge 18 ] || { echo "ACTOR ARM INCOMPLETE at $(count $A)/18"; exit 1; }

python3 - <<PY
import json
d=json.load(open("$A"))
bad=[r for r in d["runs"] if r["dropped_frames"]>$LIMIT and r["tracking_rmse_mps"]<1.0]
if bad:
    keep=[r for r in d["runs"] if r not in bad]
    json.dump({"port":d["port"],"reason":"dropped_frames > $LIMIT; re-run","runs":bad},open("docs/week11-pil-corrected-actor-disturbed.json","w"),indent=1)
    json.dump({"port":d["port"],"runs":keep},open("$A","w"),indent=1)
print("actor cells set aside:",[(r["scenario"],r["level"],r["dropped_frames"]) for r in bad])
PY
[ "$(count $A)" -ge 18 ] || ./.claude/night/run_arm.sh actor "$A" .claude/night/corrected-actor.log

python3 - <<PY
import json
a=json.load(open("$A")); b=json.load(open("$R"))
runs=b["runs"]+a["runs"]
keys={(r["scenario"],r["level"],r["controller"]) for r in runs}
assert len(keys)==len(runs)==36, f"{len(runs)} runs, {len(keys)} distinct"
assert all(r["actor_steps"]==0 for r in b["runs"]) and all(r["actor_steps"]>0 for r in a["runs"])
json.dump({"port":a["port"],"runs":runs},open("$OUT","w"),indent=1)
print("merged 36 runs")
PY
echo "CORRECTED CAMPAIGN COMPLETE"
./.claude/night/corrected_a4.sh
echo "CHAIN COMPLETE"
