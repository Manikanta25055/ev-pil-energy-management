# Claims, Section VI (05-ems)

## Mismatches and notes (read first)
- A3 interval: the brief gives +0.240 Wh/km. That value (CI -0.669 to +1.228) is `docs/week8-sac.json` a3, on the UNCORRECTED model (HWFET, no ceiling binds). The corrected retraining in `docs/week11-sac-corrected.json` gives +0.262 (CI -0.698 to +0.982). The text gives both, labelled.
- Rule tracking on US06-based settings: the week-11 record says "0.02 to 0.05"; the JSON gives 0.010 to 0.098 m/s (0.098 at driver 1.5). The text uses the JSON range.
- The brief mentions vehicle mass as a disturbance; the campaign has no mass axis (axes: driving condition, road grade, battery state, sensor noise, communication delay, driver aggression). The text says mass was not an axis.
- Actor latency: 0.121 ms is `docs/week8-actor-onchip.json` (first build); the Arduino-build file `week8-actor-onchip-arduino.json` gives 0.1233 ms. Text quotes 0.121 as in the brief.
- Mean difference 0.935% computed from JSON (0.9350), matches 0.94%. Old campaign mean -8.276% (first), -8.292% (repeat); text uses 8.28%.
- "Late steps" = ctrl_late = 0 in all 36 runs; dropped frames are not zero in the delay rows and are not late steps.
- Seed-level validation selection: seed 3 at 154.21 Wh/km (week11-sac-corrected.json rows).
- Not read in detail: `src/evpil/control/speed estimator` files and `scripts/plot_*.py` beyond plot_a4_sweep; SAC hyper-parameters other than net_arch, steps, seeds are library defaults (not stated in text). Gap: training-reward weights quoted only qualitatively.

## Numbers
| Number | Fragment | Source | Status |
|---|---|---|---|
| 100 Hz, 10 Hz | speed loop, manager rate | tasks.h CTRL/EMS_PERIOD_MS=100; sim.py OUTER_DECIMATION=10 | design |
| 0.85, 0.94, 2 m/s, 125 kW, 40 kW, 0.20, 0.07, 0.15, 30% | rule thresholds | src/evpil/control/rule_ems.py | design |
| 153.90/153.89, 167.93/167.67, 190.47/190.39 | headroom | status-report s16 (week7-control-baselines) | SIMULATED |
| 0.01% to 0.16%, 0.16% | gap range | status-report s16 table (0.01 to 0.16) | SIMULATED |
| 8 inputs, 3 outputs, 4,931, 8-64-64-3 | policy | env.py OBS_NAMES; week11-sac-corrected.json actor_cost | design |
| 200,000 steps, 5 seeds, WLTC3B/UDDS train, HWFET val, US06 sealed | training | run_sac.py; cycles.py CONTROL_SPLIT | SIMULATED |
| 154.86 +- 0.51; 155.12 +- 0.82; 153.90 | retraining | week11-sac-corrected.json summary | SIMULATED |
| seed 3, 154.21 | deployed seed | week11-sac-corrected.json rows | SIMULATED |
| 0.121 ms, 19.3 KB, 2.1e-06, 2e-05 | on-target cost | week8-actor-onchip.json | MEASURED |
| +0.240 [-0.669, +1.228] | A3 original | week8-sac.json a3 | SIMULATED |
| +0.262 [-0.698, +0.982] | A3 corrected | week11-sac-corrected.json a3 | SIMULATED |
| 36 runs, 2,282,832 steps, 0 late | campaign | week11-pil-corrected.json (sum steps, ctrl_late) | MEASURED |
| 16 valid, 1 lower, +0.94% | result | computed from week11-pil-corrected.json; finalization.json | MEASURED |
| table values | tab:ems-campaign | week11-pil-corrected.json equivalent_wh_per_km, tracking_rmse_mps | MEASURED |
| 25.7 to 43.4 m/s | excluded delay rows | week11-pil-corrected.json | MEASURED |
| 0.504 m/s, 0.010 to 0.098 | tracking ranges | week11-pil-corrected.json | MEASURED |
| +5.71%, +4.45%, 0.03% to 0.82%, -0.02% | extremes | week11-pil-corrected.json | MEASURED |
| 0.16% (identical campaigns) | repeat spread | week11-rule-arm-check.json | MEASURED |
| 14 of 16, 8.28%, 21.6% | withdrawn campaign | week10-pil-campaign.json, docs/week10-pil-campaign.md 6.2 | MEASURED (withdrawn) |
| 5 kW, 8.05 Wh/km, 12.89 km | ceiling artefact | week11-plant-correction.md s1 / .json | SIMULATED |
| +0.07% [-0.03, +0.17] | rule arm moved | week11-rule-arm-check.json | MEASURED |
| 300 ms, 5 periods, 50 ms, 10 N m/step | fallback | firmware/main/tasks.h, tasks.c | design |
| 0.2 to 10 s, 8 onsets | sweep | week11-a4-{on,off}-*s.json | MEASURED |
| 0.18 v 0.23; 3.73 v 6.67; 7.97 v 7.40; 18.2 v 13.3; 3.72 v 5.33 | worst/median errors | week11-a4-*.json err_peak_mps | MEASURED |

## Linter
prose_lint.py: clean, no machine-writing tells (final run, see message). Body word count about 1,500 excluding table, captions and headings.
