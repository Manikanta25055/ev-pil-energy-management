# Claims for Section III (sec:platform)

| Number | Fragment | Source | Label |
|---|---|---|---|
| 10 ms, 100 Hz | control period | firmware/main/tasks.h CTRL_PERIOD_MS | MEASURED |
| 11 floats, 44 B; 4 values, 16 B | state and actuation frames | tasks.h STATE_PAYLOAD_BYTES, ACT_PAYLOAD_BYTES; src/evpil/protocol.py | n/a |
| 1 ms read window; 5 stale steps to limp | pipelined read, limp | tasks.c link_read_frame(...,1); tasks.h STALE_LIMIT_STEPS | n/a |
| two LX7 cores, 240 MHz, 8 MB PSRAM, N8R8 | target | docs/hardware-inventory.md; docs/g1-compute-budget.md raw lines | MEASURED |
| 344,268 B | free internal heap | docs/g1-compute-budget.md EVPIL-BOARD internal_free | MEASURED |
| core 0 / core 1; 10 Hz, 10 Hz, 2 Hz | tasks | tasks.c xTaskCreatePinnedToCore; tasks.h periods | n/a |
| 13 bins | histogram | tasks.h JITTER_N_BINS | n/a |
| 29.82 million/s | G1 throughput, both builds | docs/g1-arduino.json, g1-compute-budget.md | MEASURED |
| 36.46 to 35.03 ms | forecaster benchmark | docs/g5-latency.md; docs/g5-arduino.json | MEASURED |
| 0.121 to 0.123 ms | policy latency | docs/week10-arduino-port.md | MEASURED |
| 25 µs, 0 late | p99, ctrl_late both builds | docs/g3-loop-timing.json, g3-loop-timing-arduino.json | MEASURED |
| 3.30 ms, 6.1x | G1 margin | docs/g1-compute-budget.md | MEASURED |
| 1 of 7, 0.45 points | G2 | docs/g2-plant-validation.md (2.45 vs 2.00 pp, TripB08) | SIMULATED |
| 10%, 2 points | G2 criterion | docs/g2-plant-validation.md | SIMULATED |
| 14.5%, 10% | G4 weakest arm, criterion | docs/forecast-ladder.md | SIMULATED |
| 28,894 B, 300 KB | G5 memory | docs/g5-latency.md | MEASURED |
| 59,650 loops, 61 µs, 9 dropped, 1 limp | first Arduino run | docs/g3-loop-timing-arduino.json | MEASURED |
| 121,208 frames, 0 bad, 0 lost | host side | same, host block | MEASURED |
| 6 timeouts, 7,405 µs | synchronous loop | docs/g3-loop-timing.json / .md | MEASURED |
| 16,4,6,9,9; 44; 298,250; 8.8; 6.4 to 11.8 | repeats | docs/g3-repeat-arduino-1..5.json; docs/week10-arduino-port.md | MEASURED |
| 5,965 of 5,965 | policy steps | same repeat files actor_steps | MEASURED |
| 36 runs; seeds 0,1,2; offsets 100, 200 | campaign | docs/week10-pil-campaign.md; src/evpil/control/scenarios.py; scripts/run_b7_pil.py | MEASURED |
| 2.12e-06, same checksum | actor parity | docs/week10-arduino-port.md | MEASURED |
| 21 to 54 dropped frames, 4 cells | disturbed | docs/week11-plant-correction.md | MEASURED |
| 16 frames, 8 cells | set aside | docs/week14-fused-backup-traffic-repeats.md | MEASURED |
| 0.2%, 0.005 m/s, half of 10x penalty, 0.1 m/s | speed-estimator criteria, fixed 2026-10-06 | docs/superpowers/specs/2026-10-06-decision-model-design.md 7.3 (commit 9f0a663); docs/week12-speed-arms.md section 7 | MEASURED |
| 0.0193 vs 0.0104 m/s | clean tracking, UDDS | docs/week12-speed-arms.md section 7 | MEASURED |
| 9.44 to 0.24 Wh/km | 10x noise penalty recovered | docs/week12-speed-arms.md; paper 06 | MEASURED |
| 1 false alarm | first detector on the target | docs/week12-speed-arms.md section 7 | MEASURED |
| 551, 533 of 560 | bias-aware detector, validation, test | docs/week13-sensor-architectures.md section 4; paper 06 | SIMULATED |
| 120 of 120, 0.32 s, 0 alarms in 1 h | bias-aware detector on target | paper 06, docs/week14-fused-backup-traffic-repeats.md | MEASURED |
| criteria dated 2026-08-30 | gates G1 to G5 first committed | git log: 1c42f45 (20:39, spec with gate table) before 59b8a26 (21:26, G1 result) | n/a |
| 2026-10-06 17:15 | estimator and first-detector criteria | git log: 9f0a663, before c543285, 07419f6, 2de0f49 | n/a |
| 2026-10-08 21:36 | bias-aware registered cases and criteria | git log: c10d2c1 (sensor_eval.py and B7 in one commit) | n/a |
| 2026-09-21 | PIL acceptance rule: record 36 runs, no direction | git show f5feb51:.claude/night/GOAL.md, criterion 2 | n/a |
| 2026-08-30 | G2 split; one revision permitted by the spec; thresholds 10% and 2 points kept; torque bound 50% added | spec 6.1 at 207b224; docs/g2-plant-validation.md | SIMULATED |
| 2026-09-21 | delay exclusion, tracking 1 m/s or more; 25.7 to 43.4 m/s | commit b1fee30; paper 04 | MEASURED |
| 2026-10-07; 16 | re-run rule; 4 rule cells at 21 to 54 | scripts/finalize_corrected_campaign.py line 79; docs/week11-plant-correction.md; commit 2b928aa | MEASURED |
| 2026-10-06 | plant fix and DP guard recorded | commit 82ca2fe; spec 7.3 "Guard against a repeat of the week-10 error" | SIMULATED |
| 2026-10-09; 18 candidates | fused backup speed, rule fixed before runs | docs/week14-fused-backup-traffic-repeats.md | SIMULATED |
| 32 runs, 16 settings, 12 conditions, 5 nominal repeats | counts | docs/paper-table5-stats.json | MEASURED |
| r = -0.03 | dropped frames vs energy difference over 16 settings | docs/paper-table5-stats.json dropped_frames_vs_energy_corr -0.028 | MEASURED |
| +0.240, -0.669 to +1.228 | A3 on original model | spec section 4 / docs/week8-sac.md; paper 04 | SIMULATED |
| 0.0 percent | A1 accuracy change | docs/transformer-a1.md | SIMULATED |

| 0.01% to 0.16%, 0.5% | headroom on corrected plant | docs/2026-10-14-control-baselines-corrected.json (WLTC3b 0.031, UDDS 0.16, HWFET 0.01, US06 0.04 pct); plan docs/2026-10-14-measurement-plan.md | SIMULATED |
| 0.99/h, 196, 59%, 70 trips, 30.4 h, 16.2/h, 72% | bias-aware on logged trips | docs/2026-10-14-bias-aware-logged-replay.json | SIMULATED |
| 1.9/h, 21% | frozen test disabled (post hoc) | lead's update note UPDATE-R2B.md (not in the JSON summary; unverified by me) | SIMULATED |
| 14 variants, 0.12% to 0.81% | plant sensitivity | docs/2026-10-14-plant-sensitivity.json (nominal +0.362 US06, +0.203 HWFET; max 0.809 HWFET c_rr) | SIMULATED |

## Panel items

- R3 (one table of every criterion with outcome, including estimator clean-tracking 0.0193 against 0.0104 and the bias-aware 551 and 533 of 560): Table tab:platform-gates, now 14 rows covering gates, A1/A3, estimator, first detector, bias-aware detector.
- R3 (list of rules made after results were seen): Table tab:platform-revisions, six rows: G2 split, delay exclusion, 16-frame re-run rule, plant fix with added checks, second detector, fused backup speed.
- Dated records: git log shows dated commits, so the text says the dates come from the version history. Wording "pre-registered" is not used; "fixed in advance" is.
- Arm, cell/setting, comparable energy scale: defined in "Terms and Repetition".
- S6: dropped frames against energy difference r = -0.03, in "Real-Time Behaviour".
- Seeds replay only the noise draw: stated, plus the seed-level confound (DA m4) and at most three distinct draws among five nominal repeats.
- General-purpose, not automotive-qualified microcontroller: one sentence in the first subsection, pointing to the discussion.
- 36 runs, 32 valid: stated in "Terms and Repetition".
- DA M4: the energy-manager comparison had no outcome criterion; said in the text.
- Not done in this file: a repository or availability statement (lead's back matter).

## Git history findings (read-only)

- Gate criteria: the design spec with the gate table is in the first commit, 2026-08-30 20:39 +0530; the G1 result commit is 21:26 the same evening. G2 revision commit 22:58 (spec says one revision allowed, text of the permission is in the first commit).
- Estimator and detector (B5/B6) criteria: 2026-10-06 17:15, the first commit of the decision-model branch work; arms followed afterwards.
- Bias-aware detector: criteria file and detector were added in one commit, 2026-10-08 21:36. The commit message and docs say criteria were fixed before any learned arm was trained; there is no record that they preceded the detector itself.
- PIL campaign: the 2026-09-21 anchor (GOAL.md) states the acceptance rule as recorded-not-directional. No outcome criterion for learned versus rules exists anywhere in the history.
- The 16-frame threshold first appears in code on 2026-10-07 (scripts/finalize_corrected_campaign.py); an earlier docs mention is in the speed-arm record of 2026-10-07. Its origin is not recorded.
- The commit dates are author dates; they can be set by the author. No external timestamp or registry exists.



## Mismatches
- BRIEF says 99.9% within 25 µs; JSON shows all 59,650 loops in the first bin (p99.9 25 µs). Text says every loop.
- Period range (9,729 to 10,001 µs) in the JSON is a since-boot extreme including start-up; the gate uses the differenced histogram (scripts/run_g3.py). Not quoted.
- G3 "dropped" = rx_timeouts + rx_bad + stale_steps + host frames_dropped; host frames_dropped is 0 in all runs, so all events are late replies seen by the target.
- stale_worst (277 to 288) is a since-boot maximum including start-up; not quoted.
- G5 36.46 ms is the vendor-framework build; Arduino build is 35.03 ms. Both given.
- "Dropped" counts: report gives 3 (vendor) and 9 (Arduino); not compared as a rate change (record: open).

## Gaps
- Origin of the 16-dropped-frame threshold not recorded; no record of a statistical analysis plan.
- No evidence the B7 criteria preceded the B7 detector (same commit).
- Bias-aware on-target criterion: the on-target run used the same 0.5 s and false-alarm limits by reading of the registered criteria; the record does not state a separate on-target criterion.
- Dates in the version history are author-controlled; no external registry.
- G5 is the deployed graph with fixed weights, not a converted trained model (docs/g5-latency.md); stated in text.
- Supply current on the Arduino image not measured; stated.
- Jitter figure is from the CSV files; no external (logic analyser) timing was used in these records.

## Linter and words (final)
Before (previous draft): prose_lint clean, 1276 prose words, 65 sentences; measure.py SD 9.8, n 66, short 12, long 10.
After round 2b: prose_lint clean (1297 prose words), SD 10.9, body words about 1200 (over budget by tables of new rows' text). Earlier: prose_lint clean (1236 prose words, 65 sentences); measure.py SD 10.6, n 66, short 14, long 11. Body words excluding headings, tables and captions: 1147 (budget 1000 to 1150).
