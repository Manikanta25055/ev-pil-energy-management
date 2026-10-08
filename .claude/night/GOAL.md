## OBJECTIVE
Every remaining stage of `docs/2026-10-07-model-advancement-research.md` that does not need Jev (P3, P5, P6, P7) has a recorded result or a recorded reason it was not run, on branch `feature/sensor-arch`.

All commands run from `/Users/manikantagonugondla/Desktop/EV Drives Improvement/.worktrees/sensor-arch`.
A criterion asks that a result exists and is honestly labelled. None asks that any arm wins.

## ACCEPTANCE
1. The suite is green — VERIFY: `PYTHONPATH="src:." python3 -m pytest tests -q` — EXPECT: exit code 0.
2. The registered sensor evaluation was not altered — VERIFY: `PYTHONPATH=src python3 -c "from evpil.control import sensor_eval as se; assert se.config_hash()=='8822ca1eb5a48b74'"` — EXPECT: exit code 0.
3. P3, A3 (a better speed while flagged / learned estimator component) is evaluated on both splits beside B7 alone and B7 with the rule monitor — VERIFY: `python3 -c "import json; ds=[json.load(open('docs/week13-a3-%s.json'%s)) for s in ('val','test')]; assert all(d['provenance'].startswith('SIMULATED') and {'A0 b7','A2 monitor'}<=set(d['rows']) and any(k.startswith('A3') for k in d['rows']) and all(r['summary']['named_faults']==560 for r in d['rows'].values()) for d in ds)"` — EXPECT: exit code 0.
4. P3, A4 (bounded torque correction) is either run or declined with a reason — VERIFY: `python3 -c "import json; d=json.load(open('docs/week13-a4-decision.json')); assert d['decision'] in ('run','skipped') and len(d['reason'])>40 and (d['decision']=='skipped' or d['result_file'])"` — EXPECT: exit code 0.
5. P5: B7 and the rule monitor in C agree with Python — VERIFY: `PYTHONPATH="src:." python3 -m pytest tests/control/test_b7_c_parity.py tests/control/test_monitor_c_parity.py -q` — EXPECT: exit code 0, at least 2 tests passed, none skipped.
6. P5: the firmware host harnesses still build — VERIFY: `make -C firmware/host_test check` — EXPECT: exit code 0.
7. P5: a board campaign of B7 (with and without the monitor) with injected faults is MEASURED, or the reason it could not be is recorded — VERIFY: `python3 -c "import json,os; p='docs/week13-b7-pil.json'; b='docs/week13-b7-pil-blocker.json'; d=json.load(open(p)) if os.path.exists(p) else None; assert (d and d['provenance'].startswith('MEASURED') and d['late_control_steps'] is not None and d['estimator_mode_verified'] is True and d['board_restored_to']=='actor') or (len(json.load(open(b))['blocker'])>40 and json.load(open(b))['board_restored_to']=='actor')"` — EXPECT: exit code 0.
8. P6: a constrained classical speed planner, a learned terminal cost and a student policy are compared on matched route, distance and arrival time — VERIFY: `python3 -c "import json; d=json.load(open('docs/week13-energy-planner.json')); a=d['arms']; assert {'tracked_cycle','classical','terminal_cost','student'}<=set(a); assert all(abs(a[k]['distance_km']-a['classical']['distance_km'])<0.01*a['classical']['distance_km'] and abs(a[k]['arrival_s']-a['classical']['arrival_s'])<=d['constraints']['arrival_tolerance_s'] and 'equivalent_wh_per_km' in a[k] and 'constraint_violations' in a[k] for k in a); assert d['provenance'].startswith('SIMULATED') and d['split']=='test'"` — EXPECT: exit code 0.
9. P7 (remote planning with buffering) is either run or declined with a reason — VERIFY: `python3 -c "import json; d=json.load(open('docs/week13-a7-decision.json')); assert d['decision'] in ('run','skipped') and len(d['reason'])>40 and (d['decision']=='skipped' or d['result_file'])"` — EXPECT: exit code 0.
10. The Jev stages are recorded as blocked, not filled in — VERIFY: `grep -c "Jev" docs/week13-plan-status.md && ! grep -rl '"reviewer": *"jev"' docs/*.json` — EXPECT: a count of at least 1 on the first line and no file names after it; exit code 0.
11. The write-ups exist and name what was not done — VERIFY: `grep -l "Not done" docs/week13-estimator-and-board.md docs/week13-energy-planning.md docs/week13-plan-status.md | wc -l` — EXPECT: `3`.
12. The sealed i3 test trips were not read by new code — VERIFY: `python3 -c "import json,subprocess,sys; t=json.load(open('data/splits.json'))['test']; out=subprocess.run(['git','grep','-l','-E','|'.join(t),'--','src','scripts'],capture_output=True,text=True).stdout.strip(); sys.exit(1 if out else 0)"` — EXPECT: exit code 0.
13. Nothing was pushed — VERIFY: `git branch -r --contains HEAD | wc -l` — EXPECT: `0`.
14. Everything is committed — VERIFY: `git status --porcelain | wc -l` — EXPECT: `0`.
15. Nothing is left running — VERIFY: `pgrep -f "[s]pawn_main|[r]un_arch_study|[r]un_sensor_eval|[r]un_pil|[a]rduino-cli"; echo $?` — EXPECT: `1` and no process lines. (The brackets keep the check from matching its own shell.)

## BLAST RADIUS
Inside the worktree `.worktrees/sensor-arch` only:
- `src/evpil/control/**` (new modules; in existing files only `speed_estimators.py`, `supervisor.py`, `sim.py`, `tiny_rnn.py`, and never `sensor_eval.py`'s registered constants)
- `src/evpil/plan/**` (new: the speed planner)
- `scripts/` new files, plus `scripts/sensor_arms.py`, `scripts/run_arch_study.py`, `scripts/run_sensor_eval.py`, `scripts/train_reviewer.py`
- `tests/control/**`, `tests/plan/**` (new tests; existing tests are not edited to make them pass)
- `firmware/main/control.c`, `control.h`, `reviewer.c`, `reviewer.h`, `tasks.c`, `tasks.h`, `CMakeLists.txt`; `firmware/host_test/**`
- `docs/week13-*`, `models/**`
- `data/reviewer*/`, `data/planner/` (gitignored working data)
- `.claude/night/**` in the worktree
- The board on `/dev/cu.usbmodem101`: flashing test images, and restoring the normal actor image at the end
- Outside the worktree, exactly two files: `.remember/remember.md` in the main checkout and the memory folder under `~/.claude/projects/-Users-manikantagonugondla-Desktop-EV-Drives-Improvement/memory/`

## OUT OF SCOPE
- Anything with Jev, Laya, Kev or Nimble: no purchase, no API call, no download, no stand-in model reported under their names (plan stages P4, most of P5-variants).
- `git push`, merging `feature/sensor-arch` into any branch, sending the supervisor note.
- Changing the registered cases, splits, seeds or criteria in `sensor_eval.py`, or loosening a bound after seeing a result. A new criterion set for a new task (energy planning) is written before its first run.
- Re-tuning B7 or retraining the reviewers so that a row passes; a fourth round of reviewer training.
- The main checkout's working tree, including its two untracked `docs/` files and the Codex agent's files (`AGENTS.md`, `scripts/build_report.py`, `scripts/corrected_campaign.py`, `scripts/finalize_corrected_campaign.py`).
- The 70-page report, the supervisor note, `src/evpil/plant/**`, the SAC actor and its weights header, the rule energy manager, the PID gains.
- The sealed i3 test trips and `data/splits.json`.
- The earlier campaigns' result files (`docs/week7-*` through `docs/week12-*`).
- Fixing the pre-existing skipped tests, the iCloud eviction of `.git`, or any unrelated bug met on the way: note it in the write-up and leave it.
- Any multiprocessing pool started from a heredoc; any board job while a second one is running.
