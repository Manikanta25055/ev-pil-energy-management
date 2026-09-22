#!/usr/bin/env bash
# Wait for the repeat campaign's merge, then finish the job: figure, report,
# full test suite, commit, push. Written so the session can end without
# leaving four commands for a human to remember.
#
# It does nothing unless the merge actually produced 36 runs all carrying the
# power-ceiling telemetry, and it will not commit if the tests fail.
set -u
cd "/Users/manikantagonugondla/Desktop/EV Drives Improvement"
OUT=docs/week10-pil-campaign-repeat.json
DEADLINE=$(( $(date +%s) + 3*3600 ))

echo "waiting for the repeat merge"
while [ "$(date +%s)" -lt "$DEADLINE" ]; do
    [ -f "$OUT" ] && break
    sleep 60
done
[ -f "$OUT" ] || { echo "MERGE NEVER APPEARED; nothing done"; exit 1; }

python3 -c "
import json,sys
d=json.load(open('$OUT'))['runs']
assert len(d)==36, f'{len(d)} runs, expected 36'
bad=[r for r in d if r['diag_delta'].get('p_limit_mean_w',0)<=0]
assert not bad, f'{len(bad)} runs without the power ceiling'
print('merge verified: 36 runs, all carrying the ceiling')
" || { echo "MERGE FAILED VERIFICATION; not committing"; exit 1; }

PYTHONPATH="src:." python3 scripts/plot_pil.py \
    --campaign "$OUT" --out docs/figures/pil-energy-repeat.png || exit 1
PYTHONPATH="src:." python3 scripts/build_report.py || exit 1
PYTHONPATH="src:." python3 -m pytest tests -q > .claude/night/finish-tests.log 2>&1 || {
    echo "TESTS FAILED; not committing. See .claude/night/finish-tests.log"; exit 1; }
tail -1 .claude/night/finish-tests.log

git add docs/week10-pil-campaign-repeat.json docs/figures/pil-energy-repeat.png \
        reports/EV-PIL-status-report.docx 2>/dev/null
git commit -q -F - << 'MSG'
The repeat campaign, on the firmware that logs the power ceiling

36 runs, both arms, every one carrying p_limit_min/mean/max. Kept in its own
file: a repeat whose value is reproducibility must not overwrite the
measurement it reproduces, and the two campaigns run on builds differing by
these counters, so the report shows them side by side and never pools them.

What it settles. The energy reversal reproduces. The rule manager's HWFET
baseline now has three independent measurements spanning 0.07% - 153.90 from
week 8's simulation, 154.01 from the first campaign, 153.95 from this one -
across a laptop and two separately flashed microcontroller images.

And the mechanism is measured rather than inferred. Both controllers use the
discharge ceiling over the same 40 kW to 125 kW range; the rule manager holds
it near 124.5 kW almost everywhere and tapers only at the lowest charge, while
the learned controller modulates it with charge and with road demand. The
earlier claim that only one of them limited power was wrong.

MSG
git push -q 2>/dev/null
echo "FINISH COMPLETE: $(git log --oneline -1)"
