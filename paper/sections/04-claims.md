# Claims, Section V (04-ems), round 2

## Panel items
- R2: replicate structure (5 nominal repeats, 12 distinct conditions, noise seeds 1,0,0,0,2), paired statistics, median and mean, "1 of 16" kept inside it, uphill exception stated against the repeat range. Where: subsection "Corrected Campaign on the Target"; Table tab:ems-campaign marks repeats with R; Fig. fig:ems-campaign remade (paired differences, repeats hatched, repeat range as band).
- R5: forecast ablation stated as two reference-derived channels, not the Transformer. Where: "Forecast Ablation", second sentence.
- R8: hyperparameter and reward-weight table (tab:ems-hyper); rule-constant origin in the "Control Structure" paragraph; no-sweep statement in "The Learned Policy". Gaps below.
- S5: US06 not unseen; tracking deficit 0.17 to 0.50 m/s on US06-based settings, 0.016 and 0.004 on UDDS and HWFET. Where: after Fig. fig:ems-campaign.
- S6: dropped frames against energy difference, r = -0.03.
- S3: outage subsection describes behaviour, no safety claim; crossover at 4 to 5 s stated.
- Minor: "Mixed" defined in the table caption; "36 runs, 32 of them in the valid set".
- Order as asked: control structure and rules, headroom, learned policy, forecast ablation, campaign, earlier campaign (pointer to Section @sec:plant), outage.

## Numbers
| Number | Fragment | Source | Status |
|---|---|---|---|
| 0.01% to 0.16%; 153.90/153.89, 167.93/167.67, 190.47/190.39, 175.99/175.94 | headroom | docs/week7-control.md table; week7-control-baselines.json | SIMULATED |
| 0.80 SOC, 12 degrees C | DP and campaign ambient | week7-control.md; scripts/run_pil_campaign.py T_AMBIENT_C | design |
| 0.85, 0.94, 2 m/s, 125/40 kW, 0.20, 0.07, 0.15, 30% | rule constants | src/evpil/control/rule_ems.py | design |
| 0.0003, 256, 1,000,000, 0.99, 0.005, auto | SAC library defaults | stable_baselines3 2.9.0 SAC signature | design |
| 1,000; 64,64; 200,000; 5; 300 | script settings | scripts/run_sac.py | design |
| 1.0, 1.0, 5.0, 2.0, 50.0, floor+0.02 | reward weights | src/evpil/control/env.py RewardWeights, step() | design |
| 154.86 +- 0.51; 155.12 +- 0.82; 153.90; seed 3 154.21 | retraining | docs/week11-sac-corrected.json | SIMULATED |
| 0.121 ms, 19.3 KB, 2e-06/2e-05, 0.84 ms | on-target cost | docs/week8-actor-onchip.json | MEASURED |
| +0.240 [-0.669, +1.228]; +0.262 [-0.698, +0.982] | forecast ablation | week8-sac.json a3; week11-sac-corrected.json a3 | SIMULATED |
| 36 runs, 32 valid, 2,282,832 steps, 0 late | campaign | week11-pil-corrected.json | MEASURED |
| 25.7 to 43.4 m/s; 0.504 m/s | excluded and largest valid error | week11-pil-corrected.json | MEASURED |
| 190.73 to 191.41 (0.36%); 191.43 to 191.98 (0.29%); +0.40, SD 0.22, [0.13, 0.67], n=5 | repeats | docs/paper-table5-stats.json nominal_replicates | MEASURED |
| +0.94% mean, +0.35% median (16); 11 of 12; +1.11% [0.27, 2.27]; +0.31% [0.17, 0.76]; Wilcoxon p 0.001; sign p 0.006 | paired statistics | paper-table5-stats.json | MEASURED |
| r = -0.03 | dropped frames vs energy | paper-table5-stats.json | MEASURED |
| seeds 1,0,0,0,2 | noise seeds of repeats | week11-pil-corrected.json, seed field | MEASURED |
| +5.71, +4.45, -0.02, 0.05 gap to lowest repeat | extremes | paper-table5-stats.json (0.035 - (-0.018)) | MEASURED |
| 0.17 to 0.24, 0.33, 0.504, 0.010 to 0.098, 0.016, 0.004 | tracking | week11-pil-corrected.json | MEASURED |
| 14 of 16, 8.28% | earlier campaign | week10-pil-campaign.json | MEASURED (withdrawn) |
| outage numbers | unchanged from previous draft | week11-a4-{on,off}-*s.json | MEASURED |

| 14 variants, +0.12% to +0.81% | plant sensitivity | docs/2026-10-14-plant-sensitivity.json | SIMULATED |
| DP re-run on corrected plant, unchanged | headroom | docs/2026-10-14-control-baselines-corrected.json | SIMULATED |

## Mismatches
- Resolved in update 2b: the DP was re-run on the corrected plant (docs/2026-10-14-control-baselines-corrected.json); gaps 0.03, 0.16, 0.01 (0.006), 0.04% unchanged.
- Table tab:ems-campaign "Mixed" and the four other R rows were reached through different axes but share the nominal condition; SOC 0.85 starts at 0.85, not 0.80, so it is not a repeat.
- Episode length 300 is the run_sac.py default; the week-11 record does not store the command line used for the corrected retraining.

## Gaps
- How the SAC reward weights and the numeric rule constants (0.85, 0.20, 40 kW, 0.15, 0.30) were chosen: no record found beyond the code comments; text says none was tuned and no sweep was run.
- Stable-Baselines3 version at training time (2.9.0 is the installed version); library defaults assumed.
- Equivalence margin: none set. Plant sensitivity now covered by H3 (limits stated in text).

## Lint and measure
Before: prose_lint clean (1595 words); sentence SD 12.4 (n=75). After: prose_lint clean (1911 words incl. table and captions); SD 12.6 (n=90). Body about 1,650 words, above the 1,400-1,600 budget by about 50.

Update 2b: lint clean before and after; SD 12.7 before, 12.7 after (see message).
