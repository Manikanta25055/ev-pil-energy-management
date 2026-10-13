# Claims, sections VIII to X

| Number | Fragment | Source | Status |
|---|---|---|---|
| 10.4, 9.5, 10.4, 0.0 (US06) | planning arms | docs/week13-energy-planner.json arms.*.saving_vs_tracked_frac (0.1044, 0.0946, 0.1041, 0.0003) | SIMULATED |
| 1.2, 0.8, 1.1, 0.3 (HWFET) | planning arms | same, validation.arms (0.0119, 0.0078, 0.0106, 0.0031) | SIMULATED |
| 10 m steps, 300 m horizon, 40 m replan, 1% arrival | planner description | docs/week13-energy-planning.md sec 1-2; a7 decision | SIMULATED |
| 5.1% at 25 m, 9.7% at 100 m, 12.6% at 200 m (US06) | corridor | docs/week14-corridor-planner.json routes.us06 | SIMULATED |
| -0.1% to 1.7% (HWFET) | corridor | same, routes.hwfet | SIMULATED |
| 0.01% to 0.16%; 5% to 23% | headroom | status-report.md sec 16 table | SIMULATED |
| +0.240 Wh/km, CI -0.669 to +1.228 | forecast ablation | docs/week8-sac.md sec 2 | SIMULATED |
| 8.28%, 14 of 16; 1 of 16, +0.94% | withdrawn gain | docs/week11-plant-correction.md lines 144-145 | MEASURED |
| 22.28 ms vs 36.46 ms, 64% | compute estimate | status-report.md summary | MEASURED (36.46) |
| 1.26 h, one false alarm, same step, four times | detector false alarm | status-report.md lines 1476-1484 | MEASURED, host replay |
| 0.61 vs 1.32 vs 0.83 m/s | rule monitor | status-report.md sec 33 | MEASURED |
| G2 1 of 7, 2.45 vs 2.00, 0.45 points | limitations | status-report.md summary, BRIEF | mixed |
| 3 stalls in 59,650 loops, 0 late | G3 | status-report.md summary | MEASURED |
| 0.11 m/s^2 | acceleration disagreement | docs/week12-speed-arms.md line 236 | logged data |
| 2.59 m/s heavier vehicle on US06 | fused estimator | status-report.md sec 33 | SIMULATED |
| 36 runs, 2,282,832 steps, 100 Hz, 9.44 to 0.24, 120 of 120 | conclusion | BRIEF canonical | MEASURED |

## Mismatches
- The report says the compute estimate was "64% low"; 36.46 is 64% above 22.28 (the estimate is 39% below the measurement). Text states "64% above the estimate".
- Report says 72 logged trips in places; the BRIEF says 70. Conclusion uses 70.
- The corridor planner at 200 m (12.6%) exceeds the empty-road 10.4%; the planners differ in construction (record says so; cause not established). The reference line in the figure is not directly comparable.
- Student saving is 0.03% in the JSON, shown as 0.0.

## Gaps
- No source mentions hardware-in-the-loop with a real inverter as planned work; omitted.
- The "one run per campaign cell" statement is taken from the assignment.
- Corridor limit on HWFET uses the validation split, US06 the test split.

## Linter and counts
prose_lint: clean, no machine-writing tells (1345 words before trim). Section words (incl. table and caption lines): see report.
