# Claims, Section VII (06-estimation.md), round 2

## Panel items

| Item | Where handled | How |
|---|---|---|
| R4 (detector result restated) | Bias-Aware Fault Detector, last two paragraphs | Faults injected in software; simulated accelerometer; 120 of 120 stated as 40 faults times 3 noise draws, "not independent events"; one clean hour bounded below about 3 per hour at 95% (rule of three, 3/1.00 h); simulated criteria not met (551 and 533 of 560, nine late on validation, 27 on test uncharacterised); not replayed on the 70 logged trips (only the slow disagreement of four logged trips per split was added to the simulated channel, per week13-sensor-architectures.md section 2). |
| S4 (Kalman baseline) | Estimator, paragraph after Table | Comparison is with the raw-reading loop only; no low-pass filter was run. |
| 0.24 floor arithmetic | Estimator, paragraph after Table | See Mismatches 1. Uses the second US06 floor run; first-floor result also given; baseline floor runs differ by 0.19; residual within run-to-run spread. |
| Failed clean-tracking criterion | Estimator, last paragraph | Kept as a failure (0.0193 against 0.0104 m/s). "Pre-registered" removed. |
| S3 (safety scope) | Opening paragraph; fallback and reviewer wording | No ISO 26262 or SOTIF claim; "for safety" wording not used. Fused fallback stated as not a working fallback by implication (SIMULATED, not ported). The 4 to 5 s outage-hold reversal is in Section VI (W4), not here. |
| GRU sentence rewritten | Learned Reviewers, second paragraph | Now: while the detector's flag was raised the GRU labelled a real fault correctly in 99% of blocks, the monitor 94%; while the flag was down, 88% against 1%. |
| R8 (reviewer settings) | Learned Reviewers, first paragraph | Parameter counts, 16 hidden states, AdamW at 3e-3 given; remaining settings listed in Gaps. |
| Theme link | Opening and reviewers paragraphs | Offline diagnostic accuracy did not predict closed-loop benefit. |

## Mismatches

1. Floor arithmetic for 0.24 Wh/km. `docs/week12-speed-arms-b0.json` and `-b5.json`: the cell labelled `sensor_noise floor` (seed 0) gives 190.977 (baseline) and 190.564 (two-state); `driving_condition aggressive_mixed` (US06 at the floor, seed 2) gives 190.787 and 190.610; `sensor_noise severe` (10x, seed 2) gives 200.420 and 190.800. Loss against the sensor_noise floor run: 200.420 - 190.977 = 9.443 (the 9.44 in `week12-speed-arms.json` verdicts) and 190.800 - 190.564 = 0.236 (the 0.24). Against the other floor run: 9.633 and 0.190. Baseline floor runs differ by 0.190 Wh/km (0.099%, `twin_cell_spread_percent` b0); the two-state floor runs differ by 0.046. The text states which floor each number uses. The 10x run shares seed 2 with the aggressive_mixed floor run, so that pairing (9.63 and 0.19) is the seed-matched one; the records label the sensor_noise floor row "second seed", and the text keeps that label.
2. Earlier mismatch kept: `docs/week11-speed-arms.json` gives 200.26 and 190.58 for the simulated 10x arms (text 200.3 and 190.6). The constant-action comparison appears only in `paper/sources/status-report.md`; not used.
3. Reviewer worst cases "9.7 to 12.8 m/s" in the previous draft mixed GRU validation, both reviewers on test and delayed rows; the text now gives GRU 9.7 (validation) and 10.8 (test), FastGRNN 3.0 and 12.8.

## Numbers

| Number | Fragment | Source | Label |
|---|---|---|---|
| 190.98, 200.42 | energy at floor and 10x, US06 | week12-speed-arms-b0.json (sensor_noise floor, severe) | MEASURED |
| 200.3, 190.6, 1,342 to 83 per km, five seeds | simulated 10x, reversals | week11-speed-arms.json summary noise-10x B0, B5 | SIMULATED |
| 100 Hz, 10 ms | loop rate | week12-speed-arms.md | MEASURED |
| q 0.002, q_d 0.02, first 600 s | filter settings | week11-speed-arms.json tuned, tuned_on | tuning on host |
| Table noise rows and peak currents | six cells | week12-speed-arms-b0.json, -b5.json | MEASURED |
| 9.44, 4.9%, 0.24 | 10x loss | week12-speed-arms.json verdicts b5 (9.4429, 0.2360); 9.44/190.98 = 4.94% | MEASURED |
| 9.63, 0.19, 0.19 spread | other floor run | computed from the b0 and b5 JSON as above | MEASURED |
| 341 to 288 A | peak current | week12-speed-arms-b0/b5.json | MEASURED |
| 62 to 69 us, 10,000 us, no late step | computation | week12-speed-arms.json verdicts | MEASURED |
| within 0.1% | clean energy | verdicts b5 (max 0.093%) | MEASURED |
| 0.0193, 0.0104, 0.004, 0.005, 0.011 | urban tracking; US06 floor runs 0.0161 and 0.0271 | verdicts; week12-speed-arms.md section 4 | MEASURED |
| 160 of 160, 0.21 s, 3.8 h | idealised accelerometer | week12-fault-arms-b6.json verdict | SIMULATED |
| 1 false alarm in 1.26 h | first detector on target | week12-speed-arms.json verdicts b6 (1.2595 h) | MEASURED |
| 0.018 low | dead-reckoned drift | week12-b6-alarm-replay.json | host replay |
| 70 trips, 30 h, 0.11 m/s^2, 0.22 m/s, 0.036 m/s, 99% | logged channel check | week12-accel-channel-check.json | logged data |
| 551 and 533 of 560, nine late, 27 late | bias-aware detector | week13-sensor-architectures.md sections 4 and 8; week13-arch-val.json, -test.json | SIMULATED |
| 4.5 h, 5.8 h clean, no false alarm | clean hours | week13-sensor-architectures.md sections 4 and 8 | SIMULATED |
| four logged trips per split | replayed slow disagreement | week13-sensor-architectures.md section 2 | SIMULATED |
| 4,000 samples | C parity | week13-estimator-and-board.md section 3 | host test |
| t_s 6, h 30, alpha 0.2, tau_b 2 s | detector settings | speed_estimators.py BiasAwareSettings | code |
| Table faults: 7/7/6/6/7 of 8; 8 each; 24 each; worst 0.62, 0.65, 0.83, 0.72, 0.66 | by fault type | week13-b7-pil.json by_fault; week14-b7-pil-repeats.json B7 by_fault | MEASURED |
| 33 of 40, 40 of 40 within 0.32 s, 162 false alarms | first campaign | week13-b7-pil.json | MEASURED |
| 120 of 120, 74 us, 1 clean hour, 0 late, 47 dropped early, 0.83 | three draws | week14-b7-pil-repeats.json B7 pooled (released_early 47, worst_peak_err 0.832, clean_hours 1.0000) | MEASURED |
| about 3 per hour at 95% | bound for 0 events in 1 h | rule of three, 3/1.0 h; derived, not in a file | derived |
| 540,960 blocks; 99%, 94%, 88%, 1% | shadow scores, fault recall flag up and flag down | week13-sensor-architectures.md section 6; week13-arch-shadow.json | SIMULATED |
| 1,508 and 550 parameters; 16 hidden states | GRU, FastGRNN | week13-sensor-architectures.md section 5 | n/a |
| AdamW, learning rate 3e-3 | reviewer training | scripts/train_reviewer.py line 197 | code |
| 3.7 to 1.2, 5.1 to 1.4 m/s | monitor in loop | week13-arch-val.json, -test.json | SIMULATED |
| 9.7, 10.8, 3.0, 12.8 m/s | learned reviewers worst | arch-val gru16v3 9.68, fastgrnn16v3 3.00; arch-test 10.77, 12.84 | SIMULATED |
| 0.61 vs 0.67; 1.32 vs 0.83; three alarms | monitor on target | week13-b7-pil.json; week14-b7-pil-repeats.json | MEASURED |
| 0.62 vs 3.74; 2.59; six of seven; two stuck | fused fallback | week14-b8-val.json, -test.json | SIMULATED |
| 70 to 1000 ms; 100 ms; twelve inputs | supervisory slot | week13-sensor-architectures.md sections 2 and 5 | SIMULATED |

## Gaps

- Training settings of the final ("v3") reviewers other than hidden size, optimiser and learning rate (epochs, batch size, class-weight mode, seed) are not recorded in a file I could read; `data/reviewer/` is absent. The script defaults are 40 epochs and square-root weighting, but the v3 run may have used other flags. The text omits them.
- Neither reviewer's on-target time or memory was measured (week13-sensor-architectures.md section 5); the text says so.
- No low-pass filter run, no replay of the bias-aware detector on the 70 logged trips, no per-fault-type simulated breakdown, and the 27 late test detections are uncharacterised.
- "Raw-reading loop": the records call the baseline the shipped loop; that it acts on the unfiltered reading is taken from the panel brief and the loop description, not re-verified in firmware.
- The monitor-on-target "3 alarms left raised" is taken from the week 14 table row "still raising the alarm when the run ended".

## Linter and measure

Before editing: prose_lint.py 1689 prose words, 66 sentences, clean; measure.py n=71, mean 20.8, SD 9.8. Body words (excluding tables, equations, captions): 1475.
After editing: prose_lint.py 1706 prose words, 71 sentences, clean; measure.py n=76, mean 19.8, SD 9.9 (short 14, long 16). Body words: 1502 by the same count, about 50 over the 1450 budget.
