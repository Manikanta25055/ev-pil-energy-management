#!/usr/bin/env bash
# Some rule-arm cells of the corrected campaign ran while other jobs on the
# laptop were disturbing the host link (dropped frames 21 to 54 against 0 to
# 10 in the repeat campaign). Wait for the arm to finish, set those cells
# aside in their own file, and run them again on a quiet machine. The rule
# image is still flashed, so no build is needed.
set -u
cd "/Users/manikantagonugondla/Desktop/EV Drives Improvement"
OUT=docs/week11-pil-corrected-rule.json
SIDE=docs/week11-pil-corrected-rule-disturbed.json
LIMIT=16
count() { python3 -c "import json
try: print(len(json.load(open('$OUT'))['runs']))
except Exception: print(0)"; }
while pgrep -f "^bash .*/run_arm[.]sh rule " >/dev/null; do sleep 20; done
[ "$(count)" -ge 18 ] || { echo "rule arm ended at $(count)/18; not re-running"; exit 1; }
python3 - <<PY
import json
d=json.load(open("$OUT"))
bad=[r for r in d["runs"] if r["dropped_frames"]>$LIMIT and r["tracking_rmse_mps"]<1.0]
keep=[r for r in d["runs"] if r not in bad]
json.dump({"port":d["port"],"reason":"dropped_frames > $LIMIT while other jobs loaded the host; re-run on a quiet machine","runs":bad},open("$SIDE","w"),indent=1)
json.dump({"port":d["port"],"runs":keep},open("$OUT","w"),indent=1)
print("set aside",[(r["scenario"],r["level"],r["dropped_frames"]) for r in bad])
PY
./.claude/night/run_arm.sh rule "$OUT" .claude/night/corrected-rule.log
python3 -c "
import json
for r in json.load(open('$OUT'))['runs']: print(r['scenario'],r['level'],round(r['equivalent_wh_per_km'],2),'drop',r['dropped_frames'])"
echo "RULE ARM FINAL"
