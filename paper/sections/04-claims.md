# Claims, Section V (04-forecast)

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
| 11.007 kW five-LSTM mean | ensemble | forecast-ladder.json | SIMULATED |
| 87 %; 1.2 % | share of benefit; compute | (13.219-11.308)/(13.219-11.029)=87.3 %; 0.26/22.28 = 1.17 % | derived |
| 0.038 to 0.174 kW seed spread | transformer-a1.md | SIMULATED |
| 10.926 kW | 3-model mean at 3 s | transformer-a1.json arms.plain-1ch.final_rmse_w | SIMULATED |
| 21,336 params; 11.057 / 11.052 kW; lambda 0.1 | ablation | transformer-a1.json | SIMULATED |
| 24.5 -> 2.5 %; 373 -> 139 W; 8.40 -> 5.00 V; 500 W tolerance | consistency | transformer-a1.json violation, mean_abs_residual, tolerances | SIMULATED |
| 95.8 %; 0.00022; 11.542 kW; 4.4 %; 0.988 -> 0.966 | charge constraint | transformer-a1.md | SIMULATED |
| 1,024 exponentials, 4 heads, 2 layers; 7.25 ms; 0.64 ms; 64 % | cost gap | g5-latency.md | MEASURED |
| 11.051 -> 11.156 kW; 0.95 %; 71.7 -> 20.2 KB; 3.6x | quantisation | a2-quantisation.json; g5-latency.md | SIMULATED |
| 17,600 B; 11,294 B; 28,894 B; 9.4 % | memory | g5-latency.md, g5-arduino.json | MEASURED |
| 136,414 / 18,366 / 5,102 params; +21.9 W, 0.20 %; +99.2 W, 0.89 % | distillation | a2-distillation.json/md | SIMULATED |
| 26.7x params, 23.1x memory; 11.212 vs 11.148 kW; 64.3 W; 99.2 W; 6.1 KB; 6.75 ms | teacher | a2-distillation.md | SIMULATED (6.75 ms estimate) |

## Mismatches
- The ladder JSON/CSV per-horizon curves for LSTM and Transformer are ensemble (mean-prediction) values, 11.007 and 10.926 kW at 3 s; the headline 11.120 and 11.029 kW are means of single-model RMSEs. Figure caption states this.
- docs/g5-arduino.json (Arduino core) gives 35.03 ms for the Transformer; the report and g5-latency.md give 36.46 ms (earlier toolchain). The brief's 36.46 ms is used.
- Brief says G4 passes for "four models"; the record counts three fitted arms in the ladder and four with the Transformer. Text says every fitted model.
- Report quotes 15,103 trees; JSON "params" for XGBoost is the same tree count, not parameters.

## Gaps
- No per-horizon values for XGBoost; no on-target timing for linear regression or XGBoost.
- Quantised model not run through an embedded runtime (gate G5 not closed in full).

## Linter
paper/sections/04-forecast.md (1309 prose words, 62 sentences): clean - no machine-writing tells detected. Word count (prose): 1309.
