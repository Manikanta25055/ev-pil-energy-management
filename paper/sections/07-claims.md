# Claims, sections VIII to X (round 2)

## Numbers

| Number | Fragment | Source | Status |
|---|---|---|---|
| 10.4, 9.5, 10.4, 0.03 (US06) | planning arms table | docs/week13-energy-planner.json arms.*.saving_vs_tracked_frac (0.1044, 0.0946, 0.1041, 0.00028) | SIMULATED |
| 1.2, 0.8, 1.1, 0.3 (HWFET) | planning arms table | same, validation.arms (0.0119, 0.0078, 0.0106, 0.0031) | SIMULATED |
| 10 m steps, 300 m horizon, 40 m replan, 1% arrival | planner description | docs/week13-energy-planning.md sec 1-2 | SIMULATED |
| 0.19 s for 323 replans, Python on laptop, not ported | planning time | docs/week13-energy-planning.md sec 6 (lines 103-105) | SIMULATED |
| 5.1% at 25 m, 9.7% at 100 m, 12.6% at 200 m (US06) | corridor | docs/week14-corridor-planner.json routes.us06 (0.0513, 0.0971, 0.1255) | SIMULATED |
| -0.1% to 1.7% (HWFET) | corridor | same, routes.hwfet (-0.0006 to 0.0166) | SIMULATED |
| 0.01% to 0.16% | DP headroom | docs/week7-control.md lines 22-29 | SIMULATED |
| 5% to 10% when speed is free | planning headroom | 5.1% (25 m) to 10.4% (no traffic), above | SIMULATED |
| 11 of 12 conditions, one exception inside repeat range | corrected campaign | docs/paper-table5-stats.json conditions_12.sign_test; nominal_replicates.rule_range_pct 0.357 | MEASURED |
| 8.28%, 14 of 16; 1 of 16, +0.94% | conclusion | docs/week11-plant-correction.md lines 144-145 | MEASURED |
| 22.28 ms estimate, 36.46 ms, 64% higher | latency | docs/g5-latency.md; 36.46/22.28 = 1.64 | MEASURED (36.46) |
| 0.61 vs 0.67 m/s first run; 1.32 vs 0.83 m/s three draws | rule monitor | docs/week13-sensor-architectures.md / week14-fused-backup-traffic-repeats.md; Section @sec:estimation | MEASURED |
| 19.3 KB (policy), 28,894 B (forecaster graph) | weight memory | docs/week10-deployment.md; docs/g5-arduino.json | MEASURED |
| 29.82 million MAC/s | throughput | docs/g1-arduino.json | MEASURED |
| 25 µs period deviation; 8.8 dropped frames per run | timing | docs/g3-repeat-arduino-1..5.json; g3-loop-timing-arduino.json | MEASURED |
| 3.73 vs 6.67 m/s (4 s); 7.40 vs 7.97 (5 s); 13.3 vs 18.2 (10 s) | outage handling | docs/week11-a4-{on,off}-{4,5,10}s.json; week11-plant-correction.md lines 166-175 | MEASURED |
| 2.2 times; 1 of 7; 2.45 vs 2.00; 0.45 points | plant fidelity | docs/g2-plant-validation.md; docs/ved-generalisation.md; Section @sec:plant | SIMULATED vs logged |
| 13.4% to 16.9% median energy error | VED transfer | docs/ved-generalisation.md | SIMULATED vs logged |
| 0.17 to 0.50 m/s (US06); 0.004, 0.016 (UDDS, HWFET) | tracking deficit | docs/week11-pil-corrected.json; REFRAME Section 5 W4 S5 | MEASURED |
| r = -0.03 | dropped frames vs energy | docs/paper-table5-stats.json dropped_frames_vs_energy_corr -0.028 | MEASURED |
| 9.44 to 0.24 Wh/km; 120 of 120; 2.59 not used | conclusion | BRIEF canonical | MEASURED |

## Mismatches

- The old text gave the forecast ablation as +0.240; that figure is from the original model (docs/week8-sac.md). The corrected +0.262 is in docs/week11-sac-corrected.json (diff_mean_wh_per_km 0.2622). This section no longer quotes either; it leaves the ablation to Section @sec:ems.
- The record says the compute estimate was "64% low"; 36.46 is 64% above 22.28. The text says "64% higher" and "64% low once" for the throughput-based estimate.
- Student saving on US06 is 0.03% in the JSON (earlier draft showed 0.0); the table now shows 0.03.
- The 200 m corridor figure (12.6%) exceeds the empty-road 10.4%; the planners differ in construction and the cause was not established.
- 0.61 vs 0.67 m/s is taken from the Section @sec:estimation draft; if W6 changes that sentence, this must follow.

## Gaps

- The citation key sciarretta2015 is used in Section @sec:planning; it must exist in 01-refs.json (W1 is to add and verify it). If absent, remove the citation.
- No source describes fault-tolerance features of automotive MCUs beyond the statement that they were not examined; the text makes no claim about them.
- Whether the bias-aware detector was replayed on the 70 logged trips: the text says it was not (as in REFRAME); update if the measurement round adds it.
- No plant sensitivity study exists; stated as not run.
- Corridor limit uses the HWFET validation split and the US06 test split.

## Panel items (W7)

- Planning short, SIMULATED, framed as headroom when speed is free and where a learned method could be tested: Section VIII opening, closing sentences, and Future text in IX.
- S2/R: eco-driving reference added to Section VIII (sciarretta2015, key pending, see Gaps).
- Discussion (a) why the rules held: IX, "Why the Rules Held", with the 11 of 12 result carried from Section @sec:ems.
- Discussion (b) audit checks as a reusable procedure, including that anomalies and not the gates triggered the audit and that the trigger was one-sided: "The Audit as a Procedure".
- S8: the test "a learner must not beat the offline optimum on the same plant" stated as a check, with billing-against-motion and limits-act-on-motion: same subsection.
- (c) S7 transfer: "What Transfers to Vehicle Hardware" (operation counts and weight memory port; jitter against a non-real-time host, radio stacks, flash and cache, supply current do not; not an automotive-qualified part).
- (d) S3 safety scope: "Scope of the Safety Claims" (no ISO 26262 or SOTIF claim, fault model, 4 to 5 s reversal, behaviour not safety measure).
- (e) limitations: one vehicle model, one board, one algorithm and reward design, one run per cell except the nominal repeats, plant fidelity (R7, firm statement, no sensitivity study), simulated faults, US06 not unseen (S5), G3 failure and dropped-frame relation (S6), Kalman baseline only raw (S4), detector not replayed on logged trips.
- Conclusion 236 words, no numbers beyond the abstract's (8.28%, 14 of 16, 1 of 16, 0.94%, 0.01% to 0.16%, 9.44 to 0.24, 120 of 120, 5% to 10%).

## Linter and measure

Before: prose_lint clean (1327 prose words); measure SD 10.6 (n=60).
After: prose_lint clean (1647 prose words); measure SD 10.6 (n=83).
Body words: Section VIII 422, Section IX 965, Section X 236 (budget 350/850/220; IX and VIII run over, IX by about 115).
