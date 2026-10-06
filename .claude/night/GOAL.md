# Night Protocol anchor — EV PIL, close out the corrected campaign

Written 2026-10-07 00:58 IST. Deadline: 07:00 IST the same morning.
The previous anchor is kept as `.claude/night/GOAL-2026-09-21.md`.

Two agents share this repository tonight. The board chain
(`.claude/night/chain_after_rule.sh`, PID 76070) is mine. The finisher
(`scripts/finalize_corrected_campaign.py`, PID 86802) is the Codex agent's and
starts when the chain exits. The criteria below are about outcomes and do not
care which agent produced them. Read `.claude/night/finalize-corrected-status.json`
before every increment.

## OBJECTIVE
The corrected-plant work is closed: every measurement is taken, reported,
reviewed, tested and committed locally, with no job running and no loose end
recorded, so that the model research in `docs/2026-10-07-model-advancement-research.md`
can start from a settled baseline.

## ACCEPTANCE
All commands run from the repository root, `/Users/manikantagonugondla/Desktop/EV Drives Improvement`.

1. The corrected campaign is complete and clean — VERIFY:
   `python3 -c "import json;r=json.load(open('docs/week11-pil-corrected.json'))['runs'];k={(x['scenario'],x['level'],x['controller']) for x in r};assert len(r)==len(k)==36;assert sum(x['controller']=='rule' for x in r)==18;assert all(x['ctrl_late']==0 for x in r);assert all((x['actor_steps']>0)==(x['controller']=='actor') for x in r);assert not [x for x in r if x['tracking_rmse_mps']<1.0 and x['dropped_frames']>16];print('OK campaign')"`
   — EXPECT: prints `OK campaign`, exit 0.

2. The A4 sweep on the corrected plant is complete and paired — VERIFY:
   `python3 -c "import json;L=['0.2','0.5','1','2','3','4','5','10'];[(lambda a,b:(a['n_blackouts']==8 and [x['onset_s'] for x in a['blackouts']]==[x['onset_s'] for x in b['blackouts']]) or (_ for _ in ()).throw(AssertionError(s)))(json.load(open(f'docs/week11-a4-on-{s}s.json')),json.load(open(f'docs/week11-a4-off-{s}s.json'))) for s in L];print('OK a4')"`
   — EXPECT: prints `OK a4`, exit 0.

3. The report and the supervisor note are rebuilt from the final data — VERIFY:
   `test reports/EV-PIL-status-report.docx -nt docs/week11-pil-corrected.json && test reports/supervisor-correction-note.docx -nt docs/week11-pil-corrected.json && echo OK`
   — EXPECT: prints `OK`.

4. Both documents have been looked at page by page and the manifest says so — VERIFY:
   `python3 -c "import json;d=json.load(open('docs/week11-corrected-finalization.json'));assert d['visual_review_pending'] is False;print('OK review')"`
   — EXPECT: prints `OK review`, exit 0.

5. The correction note carries the board result — VERIFY:
   `grep -c "^## 7. The campaign on the corrected plant, MEASURED" docs/week11-plant-correction.md`
   — EXPECT: `1`.

6. The rule-arm shift against the earlier campaign is explained from data, not left as a remark — VERIFY:
   `python3 -c "import json;d=json.load(open('docs/week11-rule-arm-check.json'));assert d['conclusion'] and d['rows'];print('OK rule-arm')" && grep -c "^## 8. Why the rule arm moved" docs/week11-plant-correction.md`
   — EXPECT: prints `OK rule-arm` then `1`.

7. The full test suite passes — VERIFY:
   `PYTHONPATH="src:." python3 -m pytest tests -q`
   — EXPECT: exit 0, last line reports passed and no failed or error.

8. Nothing is left running — VERIFY:
   `pgrep -f "run_pil_campaign|run_arm.sh|chain_after_rule|rerun_disturbed|corrected_a4|run_a4_closedloop|finalize_corrected_campaign" ; echo "rc=$?"`
   — EXPECT: last line `rc=1`.

9. Everything is committed locally and the tree is clean, apart from the operator's own research file — VERIFY:
   `git status --porcelain | grep -v "docs/2026-10-07-model-advancement-research.md" | wc -l | tr -d ' '`
   — EXPECT: `0`.

10. The handoff says the work is closed — VERIFY:
    `grep -c "^Corrected campaign: closed" .remember/remember.md`
    — EXPECT: `1`.

11. Project memory records the measured result — VERIFY:
    `grep -c "week11-pil-corrected.json" "$HOME/.claude/projects/-Users-manikantagonugondla-Desktop-EV-Drives-Improvement/memory/ev-pil-gate-status.md"`
    — EXPECT: `1` or more.

12. The Kalman branch is merged, or the reason it could not be is written down
    — VERIFY:
    `(git merge-base --is-ancestor feature/decision-model HEAD || test -s .claude/night/MERGE-BLOCKED.md) && echo OK`
    — EXPECT: prints `OK`. If merged, criterion 7 must pass on the merged tree.

> **AMENDED 2026-10-07 00:58 by the operator, in chat:** "you can merge the
> kalman branch if there are no issues". Criterion 12 and the merge clause
> below record that. "No issues" is taken to mean all four of: the merge has no
> conflicts; the full suite passes on the merged tree; the firmware defaults
> are unchanged (`SPEED_FILTER_ALPHA 1.0f`, `SPEED_KALMAN 0`); and it happens
> only after the board chain and the finisher have both exited, because the
> chain builds from `firmware/main/` and the finisher hashes its sources. If
> any of the four fails, the merge is aborted and `MERGE-BLOCKED.md` says which.

## BLAST RADIUS
May be created or modified:

- `docs/week11-*.json`, `docs/week11-*.csv`, `docs/week11-plant-correction.md`
- `docs/figures/pil-energy-corrected.png`, `docs/figures/week11-a4-corrected-sweep.png`
- `reports/EV-PIL-status-report.docx`, `reports/supervisor-correction-note.docx`
- `scripts/build_report.py`, `scripts/plot_a4_sweep.py`, `scripts/plot_pil.py`,
  `scripts/build_supervisor_note.py`, `scripts/corrected_campaign.py`,
  `scripts/finalize_corrected_campaign.py`, and one new read-only analysis
  script `scripts/check_rule_arm.py`
- `tests/test_corrected_finalization.py`
- `AGENTS.md` (commit as written; no edits)
- `.claude/night/*`, `.remember/*`
- `~/.claude/projects/-Users-manikantagonugondla-Desktop-EV-Drives-Improvement/memory/*`

The four finisher-hashed sources (`scripts/build_report.py`,
`scripts/corrected_campaign.py`, `scripts/finalize_corrected_campaign.py`,
`tests/test_corrected_finalization.py`) may be edited only after the finisher
has exited or been stopped by whoever owns it.

By `git merge feature/decision-model` only, never by hand edit: whatever that
branch carries under `src/evpil/control/`, `firmware/main/`,
`firmware/host_test/`, `tests/control/`, `scripts/`, `docs/` and `.gitignore`.

Board actions allowed: flashing and running the images the chain already
builds, and re-running a campaign or A4 cell that failed or was disturbed.

## OUT OF SCOPE
- Anything in `docs/2026-10-07-model-advancement-research.md`: reading it to
  plan is fine, acting on it is tomorrow's work. No new model, no training, no
  new experiment.
- `src/` and `firmware/`. If the rule-arm check finds a defect in the plant or
  the firmware, record it in the note and the handoff and stop there.
- On `feature/decision-model`: no rebase, no new commits, no port of B5 or B6
  to C, no board run of the Kalman arms, no resolving a merge conflict by
  editing. Merging it as it stands is in scope (criterion 12).
- Retraining SAC, choosing a different seed, re-tuning any arm.
- Rebuilding the `comm_delay` axis with a delivery queue.
- `git push`, sending or drafting the supervisor email in Gmail, opening a PR.
- Deleting or overwriting `docs/week11-pil-corrected-rule-disturbed.json` or
  any week-10 measurement file.
- Starting a second board job, a second finisher, or killing the Codex
  agent's finisher or wake-up watcher because it is slow.
- Side compute while a board cell is running: no multi-process sweeps, no
  cross-compiles, no full test suite until the board is idle.
- Unrelated fixes met along the way, including the report's three pre-existing
  MED prose findings and any test that was already failing.
