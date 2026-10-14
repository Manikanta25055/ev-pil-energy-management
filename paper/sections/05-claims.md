# Claims, Section VI (05-forecast), revised round 2

| Number | Fragment | Source | Status |
|---|---|---|---|
| 30 samples, 3.0 s, 10 Hz; 32 samples, 3.2 s; 8 signals | task window | src/evpil/forecast/windows.py FEATURE_COLUMNS; docs/forecast-guards.md | SIMULATED |
| 55,125 / 29,252 windows; 19 / 7 trips | splits | docs/forecast-ladder.json n_windows; forecast-guards.md | SIMULATED |
| R2 0.4018 real, -0.0044 shuffled; 257 parameters | shuffled-label check | forecast-guards.md Guard 2 | SIMULATED |
| 13.219 kW; 26.172 kW; 11.897 kW | persistence, drift, G4 bar | forecast-ladder.json final_step_rmse_w; forecast-guards.md | SIMULATED |
| 11.308 / 11.290 / 11.120 / 11.029 kW; 14.5 / 14.6 / 15.9 / 16.6 % | table | forecast-deploy-cost.csv (final_rmse_w, skill) | SIMULATED |
| 7.5, 20.4, 17.9, ~3,658 KB | sizes | forecast-deploy-cost.csv int8_bytes; transformer-a1.md | SIMULATED (estimates) |
| 0.26 ms, 0.6 % (ridge estimate); 19.84 ms; 22.28 ms | estimates | forecast-deploy-cost.csv | estimate |
| 35.07 ms, 36.46 ms, 88 %, 91 % | on target | docs/g5-latency.md | MEASURED |
| 87 %; 1.2 % | share of benefit; compute | (13.219-11.308)/(13.219-11.029)=87.3 %; 0.26/22.28 = 1.17 % | derived |
| 0.038 to 0.174 kW seed spread | transformer-a1.md | SIMULATED |
| 21,336 params; 11.057 / 11.052 kW; lambda 0.1 | ablation | transformer-a1.json | SIMULATED |
| 24.5 -> 2.5 %; 373 -> 139 W; 8.40 -> 5.00 V; 500 W tolerance | consistency | transformer-a1.json violation, mean_abs_residual, tolerances | SIMULATED |
| 1,024 exponentials, 4 heads, 2 layers; 7.25 ms; 0.64 ms; 64 % | cost gap | g5-latency.md | MEASURED |
| 11.051 -> 11.156 kW; 0.95 %; 71.7 -> 20.2 KB; 3.6x | quantisation | a2-quantisation.json; g5-latency.md | SIMULATED |
| 17,600 B; 11,294 B; 28,894 B; 9.4 % | memory | g5-latency.md, g5-arduino.json | MEASURED |

| 0.038 to 0.174 kW seed spread | seed spread | transformer-a1.md | SIMULATED |
| 24.5 -> 2.5 %; 500 W; 11.057 / 11.052 kW | physics-informed loss, one sentence | transformer-a1.json violation, tolerances | SIMULATED |
| 0.20 %, 0.89 % | distillation, one sentence | a2-distillation.json/md | SIMULATED |
| 7.89 ms of 14.18 ms | softmax 7.25 + layer norm 0.64 vs 36.46-22.28 | g5-latency.md | MEASURED, derived |

Cut in round 2: horizon figure (fig-forecast-horizon, no other section references it), charge-conservation paragraph, five-LSTM average, distillation detail, physics-loss detail, parameter counts. Numbers for those remain in the earlier rows only where still used.

## Panel items (W5, REFRAME Section 5)
- Cut to 600-750 words: body 728 by the linter count.
- Kept: task and safeguards, ladder table, latency estimate against measurement (22.28, 36.46, 35.03 ms; 64%), quantisation cost, one figure, one table.
- Physics-informed training and distillation: one sentence each.
- Energy manager did not use this forecaster: second sentence of the opening paragraph; the ablation channels are described in Section @sec:ems (R5).
- Perspective and EIC notes: figure caption and text now name the vendor-framework build for 36.46 ms and give 35.03 ms for the Arduino core; label overlap in the cost figure fixed.

## Mismatches
- docs/g5-arduino.json (Arduino core) gives 35.03 ms for the Transformer; the report and g5-latency.md give 36.46 ms (earlier toolchain). The brief's 36.46 ms is used.
- Brief says G4 passes for "four models"; the record counts three fitted arms in the ladder and four with the Transformer. Text says every fitted model.
- Report quotes 15,103 trees; JSON "params" for XGBoost is the same tree count, not parameters.

## Gaps
- No per-horizon values for XGBoost; no on-target timing for linear regression or XGBoost.
- Quantised model not run through an embedded runtime (gate G5 not closed in full).

- New citations chen2016 (XGBoost) and hochreiter1997 (LSTM) are not in 01-refs.json; entries written to 05-refs.json, verified by WebSearch (arXiv record and DOI; Neural Computation record). Lead should merge.

## Linter
Before (old 04-forecast.md, 1428 prose words): clean; sentence-length SD 11.9.
After (05-forecast.md, 728 prose words, 37 sentences): clean; SD 12.2 (measure.py).
