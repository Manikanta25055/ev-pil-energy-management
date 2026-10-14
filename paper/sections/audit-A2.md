# Audit A2: abstract, 01-intro-related, 02-platform, 03-plant, 04-ems

Sources opened: docs/week11-pil-corrected.json, paper-table5-stats.json, week10-pil-campaign(.json, -repeat.json), week11-plant-correction(.md, .json), week11-rule-arm-check.json, week11-sac-corrected.json, week7-control-baselines.json, g1/g3/g5 (md and Arduino json), week8-actor-onchip(-arduino).json, week10-arduino-port.md, week12-speed-arms.md, week13-sensor-architectures.md, week13-estimator-and-board.md, week14-fused-backup-traffic-repeats.md, dataset-provenance.md, g2-*, ved-generalisation.*, data/i3_params.json, splits files, rule_ems.py, env.py, run_sac.py, tasks.c/.h, git log dates, design spec. About 190 numbers checked; the large majority recomputed from JSON.

## Findings

| location | text | issue | source checked | action |
|---|---|---|---|---|
| 02 table, row "A1, A3" | Id "A1, A3" | internal ablation codes in paper text | BRIEF s4 | fixed: "Ablations" |
| 02 table G1 | "Pass: 3.30 ms, margin 6.1x", MEASURED | 3.30 ms is 98,304 MACs / 29.82 MMAC/s (computed); only throughput measured (previous audit item, not applied) | g1-compute-budget.md | fixed: "3.30 ms from measured throughput" |
| 02 L45 | "the deployed policy matches its NumPy original to 2.12e-06" | check was run on the earlier with-forecast seed 0 network, not deployed seed 3 | week8-actor-onchip(-arduino).json | fixed: "a policy network of the deployed shape, exported from an earlier seed" |
| 04 L90 | "no vehicle state for five control periods (50 ms)" | limp ramp starts on the sixth stale step (stale_run > 5); 02 says "more than five" | tasks.c L236, tasks.h L118 | fixed: "more than five" |
| 04 L41 | "0.121 ms per decision" | 0.121 ms is the vendor-build figure on the seed-0 network; shipped Arduino image gives 0.123 ms (02 L22 gives both) | week8-actor-onchip(-arduino).json | reported |
| Abstract | "ran in 36.46 ms of a 40 ms budget" | vendor-framework build; Arduino core (shipped image) is 35.03 ms; no label in abstract | g5-latency.md, g5-arduino.json | reported |
| 03 L88 | "A limit that does not bind leaves every output bit-identical" | test only compares two non-binding limits on one step; evidence for "unchanged" is rule/DP rows identical to last digit (earlier audit item, not applied) | tests/plant/test_plant.py L182 | reported |
| 03 L82 | "the repeat campaign showed both controllers used the same 40 to 125 kW range" | ceiling means 123.4 kW (rules) vs 72.0 kW (learned); min 40 kW rule floor; "same range" is the action-space range, wording is loose but defensible. No separate record states the "belief" | week10-pil-campaign-repeat.json | reported (low) |
| 04 L19, table ems-hyper | "deployed actor", "Actor and critic" | network term, not the internal code; acceptable | | reported (low) |
| 03 eq. plant-motor, plant-battery, plant-limit | never referenced in text | only fig/table order matters; equations unreferenced | | reported (low) |
| 03 eq. plant-battery | R0 shown without temperature term | code uses R0(T); earlier audit item, not applied | battery.py | reported |
| 02 L18 / fig platform-architecture | estimator box always drawn | text says "in some builds"; earlier item | tasks.h | reported |

All other numbers verified (no change), including:
- Corrected campaign table: all 16 rows, both arms, energy, RMSE, differences; 36 runs; 2,282,832 steps; 0 late; 0.84 ms worst policy step; tracking ranges (0.168 to 0.237, 0.331, 0.504, 0.010 to 0.098, 0.016, 0.004); excluded delay RMSE 25.7 to 43.4; seeds (three of five repeats use seed 0); r = -0.028.
- Table5 stats: 11 of 12, median +0.31 (0.17 to 0.76), mean +1.11 (0.27 to 2.27; 0.265 rounds up), Wilcoxon 0.001, sign 0.006, repeats 190.73 to 191.41 (0.36%), 191.43 to 191.98 (0.29%), +0.40, SD 0.22, t 0.13 to 0.67, mean16 +0.94, median16 +0.35, uphill -0.02 is 0.05 below lowest repeat. Mixed +0.0349 shown as +0.03 (correct).
- DP gaps and Wh/km (153.90/153.89, 167.93/167.67, 190.47/190.39, 175.99/175.94); rule constants; SAC hyperparameters (episode 300, learning starts 1000, reward weights, 0.02 margin); 154.86 +- 0.51, 155.12 +- 0.82, seed 3 154.21; A3 +0.240 [-0.669, +1.228] and corrected +0.262 [-0.698, +0.982].
- Earlier campaign: 8.28%, 8.29%, 14 of 16, 21.61/14.54/7.57, 10.14/7.53/4.79, 0.27, 0.09, ceilings 72.0 and 123.4 kW; sweep 8.05, 190.39, 174.85, 156.16 over 4.453 km, 16.15 m/s, 189.80; 176.71, 176.53, 190.71, 190.47, 0.48, 0.0013; +0.07% (-0.03, +0.17), 0.46, 0.57; 15 days (2026-09-21 to 10-06).
- G2 (48.6, 8.3, 0.19, 2.45), transfer 16.9/14.4/13.4 on 89 validation trips, 33 of 70, 19/7/7, -3.3 to 10.2 C, i3 parameter table, 543 W measured at rest (code confirms), 0.00878 ratio 2.2.
- Platform: 59,650 loops, 61 us, 121,208 frames, 16/4/6/9/9, mean 8.8, Poisson 6.4 to 11.8, 0 late, 29.82, 35.03/36.46, 0.123/0.121, 28,894 B, frame 11 floats in / 4 out, task layout, 551/533 of 560, 120 of 120 within 0.32 s (0.33 with the rule monitor), 9.44 to 0.24, 0.0193 vs 0.0104, 1 false alarm, commit dates (2026-08-30 spec before G1 commit, 10-06 estimator, 10-08 bias-aware).
- Abstract numbers: 8.28, 11 of 12, 0.31 (0.17 to 0.76), 0.16, 9.44 to 0.24, 36.46/40, 64% each appear in the body with the same value. The abstract does not say how many acceptance criteria were missed (body: five); see decisions.

## Cross-references

All @sec, @fig, @tab, @eq ids in the five files resolve to ids defined in the section files. Every figure and table is referenced before it appears. All [@keys] exist in 01-refs.json or 05-refs.json (44 keys). No internal codes (B5 to B8, week, Jev, Codex, Claude, "the board", "chip"), first person or dashes found; "A1, A3" fixed. Trip IDs (B08) are dataset names.

## Panel items

- R1: handled. Bounded task and 0.01% to 0.16% headroom in Introduction para 3, Section V, abstract; title bounded to the artefact.
- R2: handled. Replicate structure, 12 conditions, paired median/mean/intervals/tests, uphill inside repeat range, Table 5 marks repeats, figure with band.
- R3: handled. Two tables (criteria fixed in advance with dates; post-hoc revisions), failed clean-tracking and detector criteria included, dates verified in git. Abstract does not list the count of misses (decision below).
- R5: handled. Section V "Forecast Ablation" states the two reference-derived channels and that the Transformer never ran in the loop. Abstract does not repeat the forecast ablation, so no mismatch.
- R7: handled. "Limits of Plant Fidelity" covers 2.2 times rolling coefficient, rotational factor, regeneration ceiling, drivetrain efficiency, winter-only envelope, G2 1 of 7, 13.4% to 16.9%; says no sensitivity study.
- R8: handled. Table of SAC settings and reward weights verified against code; rule constants and their origin given. GRU/FastGRNN settings are outside scope.
- W1 to W4 items in scope: handled (bounded task, contributions list, related-work additions, G table and post-hoc table, "arm"/"setting"/comparable scale defined, r = -0.03, 36 runs and 32 valid, artefact as centre of Section IV, S5 US06 statement, safety wording in outage subsection, Mixed row defined). Not verifiable here: the three reviewer-supplied references and the 8 to 14 new references (references not audited beyond key existence).

## Needs the lead's decision

1. Abstract: add the build or label to "36.46 ms" (vendor build; 35.03 ms on the shipped Arduino image) and consider stating "five acceptance criteria missed" for R3.
2. 03 L88 "bit-identical": reword to what the evidence shows (non-binding limits give equal outputs in a unit test; rule and DP results unchanged to the last digit).
3. 04 L41: say which build the 0.121 ms (vendor build, seed-0 network) belongs to, or give 0.123 ms for the shipped image.
4. 03 equations: add R0 temperature term or say R0 is taken at reference temperature; reference or drop unreferenced equations.
5. 02 architecture figure: mark the estimator and detector box optional.
