# Claims, Section VII (06-estimation.md)

## Mismatches (read first)

1. Assignment: "200.3 against 190.5 Wh/km" and "a constant supervisory action degrades together with the rule manager". Files: `docs/week11-speed-arms.json` gives B0 200.26 (200.3) and the two-state filter 190.58 (190.6; 190.5 is the one-state filter, 190.47). Text uses 200.3 and 190.6. The constant-action comparison appears only in `paper/sources/status-report.md` line 1426; no JSON or record holds it, so the text does not use it.
2. The report's "40 faults" and "42 cases" are consistent with the JSON (40 fault runs + 2 clean runs per image).
3. `docs/week12-b6-alarm-replay.json` places the alarm at 1255.02 s; not quoted in the text.

## Numbers

| Number | Fragment | Source | Label |
|---|---|---|---|
| 190.98 to 200.42 | energy at floor and 10x, US06 | week12-speed-arms-b0.json (sensor_noise floor, severe) | MEASURED |
| 200.3 / 190.6 | baseline and estimator, 10x | week11-speed-arms.json summary noise-10x B0, B5 | SIMULATED |
| 100 Hz, 10 ms | loop rate | week12-speed-arms.md, firmware | MEASURED |
| q 0.002, q_d 0.02, first 600 s urban | filter settings | week11-speed-arms.json tuned, tuned_on | SIMULATED tuning |
| Table noise rows | energy and peak current | week12-speed-arms-b0.json, -b5.json | MEASURED |
| 9.44 / 4.9% / 0.24 | 10x loss | week12-speed-arms.json verdicts | MEASURED |
| 341 to 288 A | peak current | week12-speed-arms-b0/b5.json | MEASURED |
| 62 to 69 us, 10,000 us, no late step | computation | week12-speed-arms.json verdicts | MEASURED |
| within 0.1% | clean energy | verdicts b5 (max 0.093%) | MEASURED |
| 0.0193 vs 0.0104, 0.004 miss, 0.011 | urban tracking | verdicts (0.0089 minus 0.005); week12-speed-arms.md section 4 | MEASURED |
| 160 of 160, 0.21 s, 3.8 h, 0 false alarms | idealised accelerometer | week12-fault-arms-b6.json verdict | SIMULATED |
| 1 false alarm in 1.26 h | first detector on target | week12-speed-arms.json verdicts b6 | MEASURED |
| 0.018 low, 0.013 high | replay | week12-b6-alarm-replay.json | host replay |
| 70 trips, 30 h, 0.11 m/s^2, 0.22 m/s, 0.036 m/s, 99% | logged channel check | week12-accel-channel-check.json | logged data |
| 551 / 533 of 560, 0 clean false alarms | bias-aware detector | week13-arch-val.json, -test.json A0 b7 | SIMULATED |
| 75% to 98%, five of seven | earlier detector clean flagged share | week13-sensor-architectures.md section 4 table (82, 80, 98, 93, 75) | SIMULATED |
| 4,000 samples | C parity | week13-estimator-and-board.md section 3 | host test |
| t_s 6, h 30, alpha 0.2, 0.15 m/s, tau_b 2 s | detector settings | speed_estimators.py BiasAwareSettings | code |
| Table faults 7/7/6/6/7 of 8; 8 each; 24 each; worst 0.62, 0.65, 0.83, 0.72, 0.66 | by fault type | week13-b7-pil.json arms B6, B7 by_fault; week14-b7-pil-repeats.json B7 by_fault | MEASURED |
| 33 of 40, 40 of 40 within 0.32 s, 162 false alarms | first campaign | week13-b7-pil.json | MEASURED |
| 120 of 120, 74 us, 1 clean hour, 0 late | three draws | week14-b7-pil-repeats.json B7 pooled | MEASURED |
| 540,960 blocks; 99%, 88%, 94%, 1% | shadow scores | week13-sensor-architectures.md section 6 (arch-shadow) | SIMULATED |
| 1,508 and 550 parameters | GRU, FastGRNN | week13-sensor-architectures.md section 5 | n/a |
| 3.7 to 1.2, 5.1 to 1.4 m/s | monitor in loop | week13-arch-val.json, -test.json | SIMULATED |
| 9.7 to 12.8 m/s | learned reviewers worst | arch-val A2 gru16v3 9.68, A2 fastgrnn16v3 3.00 (A1 up to 12.76); arch-test 10.77, 12.84 | SIMULATED |
| 0.61 vs 0.67; 1.32 vs 0.83; 3 alarms | monitor on target | week13-b7-pil.json; week14-b7-pil-repeats.json | MEASURED |
| 0.62 vs 3.74; 2.59; six of seven | fused fallback | week14-b8-val.json, -test.json | SIMULATED |

## Gaps

- Fig. reviewers uses the final ("v3") reviewers; the JSON key without "v3" is a first attempt. "On the controller" in the reviewers figure means a simulated placement, not a board run.
- Reviewer FastGRNN validation worst case is 3.0 m/s; the "9.7 to 12.8" range mixes GRU validation and both reviewers on test (and delayed rows to 12.8).
- The mean-test threshold 0.036 m/s and the 0.2 s window are from week12 records, not re-derived.
- No per-fault-type breakdown exists for the simulated detection, so the table is the target data only.

## Linter and word count

prose_lint.py: 1625 prose words, 65 sentences, clean (no machine-writing tells detected).
Body word count excluding tables, equations and captions: 1452.
