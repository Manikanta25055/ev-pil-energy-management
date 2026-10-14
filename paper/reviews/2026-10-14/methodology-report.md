## Dimension Scores

Scores follow the Phase 1 scoring plan. No dissent was needed.

### D1: methodology_rigor
score: warn
Evidence for a warn, not a block. The paper labels MEASURED and SIMULATED consistently (Sec. III opening, Tables 5-7, Figs. 7-11). Timing is measured with a stated method (Sec. III.D, Fig. 2, 59,650 loops, five pooled runs, Poisson interval 6.4 to 11.8 for dropped frames). Parity tests tie Python to C (Sec. III.E). The forecaster test trips stay sealed (Sec. V.A). The G2 revision, the two excluded delay settings and the withdrawn 8.28% gain are all disclosed. These features keep D1 out of block.
Warn triggers that fired: (a) the headline comparison in Table 5 is one run per cell per controller with no interval on any cell or on the 0.94% mean ("no interval is attached to their average", Sec. VI.D), and the method behind the intervals that are given (+0.07% [-0.03, +0.17]; +0.262 [-0.698, +0.982]) is not named; (b) the quoted noise yardstick of 0.16% (two identical rule-arm campaigns) is smaller than the spread visible inside Table 5, where the nominally baseline US06 rows (Mixed, No delay, Flat, Noise 1x, Driver 1.0) give rule-arm energy from 190.73 to 191.41 Wh/km and paired differences from +0.03% to +0.55%; (c) plant validation is partial: G2 fails on 1 of 7 trips (Fig. 3), the validated envelope is winter only (-3.3 to 10.2 C, Sec. IV.A), transfer to the VED Leaf leaves 13.4% to 16.9% median trip energy error (Sec. IV.D), and the rolling coefficient is 2.2 times a published value (Sec. IV.C); (d) the final bias-aware detector is never replayed on the 70 logged trips where the real 0.11 m/s^2 acceleration gap was found (Sec. VII.C-D), and 120/120 detections and one clean hour carry no interval; (e) the SAC and rule-baseline tuning effort is not reported, although [10] is cited for exactly this sensitivity (Sec. II.B); (f) there is no code, firmware or data availability statement; (g) the US06 cycle that was "sealed for the final campaign" (Sec. VI.B) was already used in the earlier campaign whose results led to the plant fix (Sec. VI.E, Sec. IV.E).
No block trigger fired: the headline verdict is negative, the sign is the same in 15 of 16 cells, and the two large deficits (+5.71%, +4.45%) lie far outside any plausible noise.

### D2: domain_accuracy
score: warn
Cycle definitions (UDDS 1369 s, 11.99 km; HWFET 765 s, 16.51 km; US06 600 s, 12.89 km), the PIL versus HIL distinction, the equations (1)-(5) and the comparable energy scale are used correctly, and the authors audit and withdraw their own plant fault (Sec. IV.E). Warn triggers: the vehicle parameters that carry the energy results are lumped and in part non-physical by the authors' own account (Sec. IV.C: rolling coefficient 0.01947 against 0.00878, "none measures the quantity it is named after"; Table 3: R0 "identified, at lower bound", drivetrain efficiency assumed); the model is validated on winter trips only, while Sec. IV.D shows energy sloping with temperature from -15.8% to +15.6% and I could not find the ambient temperature used for the Table 5 campaign; the instantaneous battery power was not scorable (noise floor 77.7% of mean absolute power).

### D3: argumentative_coherence
score: warn
The central thesis (SAC not better than the rules on this plant, with the gain traced to an artefact) is consistent with Table 5, the DP bound (Sec. IX.A) and the corrected-campaign interval. Warn triggers: (a) the abstract states "Two acceptance gates fail", while Sec. VII.B reports a third pre-registered criterion failing (clean tracking, 0.0193 against 0.0104 m/s) and Sec. VII.D states the bias-aware detector "does not pass the registered criteria" in simulation (533 of 560 on test, 27 late detections uncharacterised); the abstract instead carries the 120/120 target result; (b) "removing the forecast changed nothing measurable" rests on a paired interval of -0.698 to +0.982 Wh/km, which is wide against the 0.94% effect under discussion and has no stated equivalence margin; (c) mechanisms for the reversal between offline and closed-loop reviewer ranking (Sec. VII.E, "a correct diagnosis keeps the flag up, and both fallback speeds then drift further") and for the 2.59 m/s failure of the fused estimator ("The cause was not tested") are explanations, not measurements; (d) the Conclusion line "classical estimation and hand-written rules survived measurement" covers the learned-reviewer comparison, which is simulated only (Sec. VII.E).

### D4: cross_disciplinary_relevance
score: pass
Table 1 and Sec. III define the protocol, PIL arrangement, gates and the measured/simulated labels in terms a machine-learning or embedded reader can follow. Generalisation is bounded explicitly: "these statements hold for this vehicle model, these four cycles and this class of processor, and no further" (Sec. IX.A) and Sec. IX.C (one board, one vehicle model, one algorithm, one reward design).

### D5: writing_and_structure
score: pass
The platform, plant, forecaster, energy manager, estimator and planner sections follow the order of the experiments; tables carry run counts in their captions (Tables 5-7) and Figs. 2-12 are legible at column width. Deductions are minor only (see Minor Issues): the statistical procedure is spread across sections, and there is no data availability statement (counted under D1).

## Failure Condition Checks

### F1
fired: false
No mandatory dimension (D1, D2, D3) scores block.

### F2
fired: true
Three mandatory dimensions (D1, D2, D3) score warn, which is two or more.

### F3
fired: false
The only high-priority dimension (D4) scores pass.

### F0
fired: false
Not every mandatory dimension scores pass.

## Review Body

# Peer Review Report

## Manuscript Information
- Title: Learned Versus Rule-Based Energy Management for Electric Vehicles on a Microcontroller: A Processor-in-the-Loop Study With Pre-Registered Acceptance Gates
- Review Date: 2026-10-14
- Review Round: Round 1 (simulated)

## Reviewer Information
- Reviewer Role: Peer Reviewer 1 (Methodology)
- Reviewer Identity: Experimental-methods specialist for hardware-in-the-loop and processor-in-the-loop validation and reinforcement-learning benchmarking.
- Review Focus: Study design and baseline fairness, run counts and statistical reporting, plant validation, data splits, handling of pre-registration deviations, timing methodology and reproducibility. Literature coverage and cross-field impact are left to other reviewers.

## Overall Assessment

### Recommendation
Major Revision

### Confidence Score
4

### Summary Assessment
The manuscript compares a rule-based energy manager with a SAC policy on an ESP32-S3 at 100 Hz, with a simulated vehicle identified from logged BMW i3 trips. It reports a negative result (learned policy better in 1 of 16 settings, 0.94% more energy on average), withdraws an earlier 8.28% gain traced to a plant fault, and adds forecasting, Kalman estimation, fault detection and planning studies. The work is unusually candid. Gates are listed with outcomes, failures are kept as failures, and every claim is tagged measured or simulated. For IEEE Access, where technical soundness and reproducibility outweigh novelty, that is the right posture. The weaknesses are in statistical support and design headroom. The central comparison is one run per cell with no interval, and the noise yardstick quoted is smaller than the replicate spread visible in Table 5. The plant that reversed one campaign is validated on winter trips only and fails its own gate once. The benchmark leaves almost no room for a learned policy (DP bound 0.16%), so the negative result is close to guaranteed. The final fault detector is never checked against the real logged data that motivated it. There is no code or data availability statement. None of this contradicts the main verdict, but all of it limits how far the verdict reaches. I recommend major revision.

## Strengths

### S1: Gates, deviations and withdrawn results are reported openly
Table 2 lists each gate with the criterion fixed in advance and the result as recorded, including two failures (G2, G3). The single revision to G2 is described step by step (Sec. III.C, Sec. IV.C), the withdrawn 8.28% gain is shown with the mechanism and a sweep that reproduces it (Sec. IV.E, Fig. 4), and the failed clean-tracking criterion "stays a failure because the bound came first" (Sec. VII.B). This is the practice the pre-registration claim needs.

### S2: Measured and simulated claims are separated throughout
The rule is stated in Sec. III and applied in every table caption and figure caption (Tables 5-7, Figs. 7-11). Estimates are kept apart from measurements; for example the 22.28 ms Transformer estimate versus 36.46 ms measured (Sec. V.D), with the 64% gap used to restrict estimates to ranking.

### S3: Timing methodology on the target is sound and honestly reported
G3 is evaluated over 59,650 loops and five pooled runs (298,250 loops), with a histogram (Fig. 2), a worst-case computation time, a Poisson interval on dropped frames, and a clear statement that the zero-drop criterion cannot be met against a non-real-time host (Sec. III.D). The move from the vendor framework to the Arduino core is declared and every gate is re-measured (Sec. III.B).

### S4: Leakage safeguards and parity tests
Splits are by trip, not by window (Sec. IV.A, Sec. V.A); the forecast target-from-input check, the shuffled-label check and the persistence baseline are fixed before fitting (Sec. V.A); validation trips used for early stopping are acknowledged as slightly optimistic (Sec. V.B); and Python-to-C parity tests cover frame format, controllers, estimator and detector (Sec. III.E).

### S5: The baseline is bounded by an optimum, not only by tuning effort
The offline DP result (rules within 0.01% to 0.16% of optimum on four cycles, Sec. IX.A) shows the rules are not a weak baseline on energy, which answers the concern raised through [10] in Sec. II.B.

## Weaknesses

### W1: The main comparison has no run-to-run uncertainty, and the stated yardstick understates the spread
**Severity**: MAJOR
**Problem**: Table 5 and Fig. 7 give one run per cell per controller (Sec. VI.D: "Each cell ran once per controller with its own noise seed"). The verdict "1 of 16" and "0.94% more on average" carry no interval ("no interval is attached to their average"). The yardstick used to call the single win "within noise" is "the 0.16% mean spread between two identical rule-arm campaigns" (Sec. VI.D, and +0.07% [-0.03, +0.17] in Sec. IV.E), but the nominally baseline US06 rows of Table 5 (Mixed 191.41, No delay 190.73, Flat 190.75, Noise 1x 190.75, Driver 1.0 190.99 Wh/km for the rules) differ by 0.36%, and the paired learned-minus-rules difference in those same rows runs from +0.03% to +0.55%. The uphill cell that counts as the win is -0.02%. The seed policy also fixes noise seeds 0, 1, 2 to the three levels of each axis (Sec. III.E), so seed and factor level are crossed in a fixed pattern. The 95% intervals that are reported do not say how they were computed or on how many pairs.
**Why it matters**: The headline count (1 of 16) depends on a cell whose sign is inside the baseline replicate spread, and the mean 0.94% is dominated by two cells (+5.71%, +4.45%); the median is about 0.34%. A reader cannot tell how stable either summary is.
**Suggestion**: Repeat each cell with at least five fresh noise seeds per controller, report a paired bootstrap interval per cell and for the across-setting mean and median, name the interval method, treat the baseline-equivalent rows as a replicate noise estimate, and report the learned-minus-rules difference against that spread. Decouple noise seed from factor level.

### W2: The benchmark has almost no headroom, and tuning effort for both arms is not reported
**Severity**: MAJOR
**Problem**: Sec. IX.A shows the rules sit within 0.01% to 0.16% of the DP optimum, and Sec. VI.A prices shed cabin heat at exactly the energy it saves, so shedding is neutral by construction. A learned policy "has at most 0.16% to gain" (Sec. VI.D). The negative result is therefore close to determined by the task, not only by the learning method. The SAC arm uses "one reward design" (Sec. IX.C) with no reported search over reward weights, learning rate, network size or training budget, and its tracking RMSE (0.17 to 0.50 m/s, Table 5) is 5 to 40 times the rules' 0.004 to 0.098 m/s, which points at the tracking term or its weight. The rules' constants are "not tuned against any test cycle" (Sec. VI.A) with no tuning procedure described.
**Why it matters**: The title and abstract frame the study as learned versus rule-based energy management. With a 0.16% ceiling the experiment cannot discriminate between a good and a poor learned policy, and the tracking gap suggests the policy may be poorly specified rather than inherently limited.
**Suggestion**: State the achievable gain beside every verdict (energy gap to DP per setting). Add at least one condition with real headroom, such as temperatures where shedding matters or a task variant where the speed loop does not fix the load. Report a bounded reward-weight and hyperparameter sweep (even three weights on the tracking term) and the budget given to each arm. Add an equivalence margin so "not better" is also stated as "not worse than X".

### W3: Plant validation did not cover the closed-loop path that later reversed a campaign, and the verdict's sensitivity to the plant is untested
**Severity**: MAJOR
**Problem**: G2 replays logged torque and checks power and SOC (Sec. IV.C), so the battery-power ceiling logic that caused the 8.28% artefact (Sec. IV.E) was never exercised by a gate; it was found "from three oddities in the campaign tables". After the fix the verdict reversed from 14 of 16 wins to 1 of 16. The model still fails G2 on one of seven trips (B08, 2.45 pp against 2.00 pp, Fig. 3), is validated on winter trips only (Sec. IV.A), has a median energy error of 13.4% to 16.9% on the VED transfer (Sec. IV.D), and uses lumped coefficients with R0 at its lower bound (Table 3). The sealed US06 cycle was visible in the earlier campaign (Sec. VI.B versus VI.E).
**Why it matters**: One plant defect already changed the answer once. The current verdict is stated as a result for "this vehicle model" (Sec. IX.A), but no check shows that it survives plausible plant error.
**Suggestion**: Add closed-loop invariance gates before any campaign (for instance, a non-binding limit must leave outputs unchanged, which the paper only runs after the fault). Run the 16-setting comparison on a small plant-perturbation set (rolling coefficient, R0, regeneration ceiling, auxiliary slope, each at plausible bounds) and report whether the verdict changes. State the ambient temperature used in each campaign and its relation to the validated -3.3 to 10.2 C range. Say plainly which cycles were exposed before the "sealed" campaign.

### W4: Fault-detection evidence is small, simulated, and not checked on the real logged data
**Severity**: MAJOR
**Problem**: The headline "120 of 120 ... no false alarm in one clean hour" (abstract, Table 7) rests on five fault types, 24 runs each from three noise draws that share injection settings, and about one clean hour. A 120/120 result bounds the miss rate only to about 2.5% at 95% (one-sided), and zero alarms in one hour bounds the false-alarm rate at about three per hour; neither bound is stated. The earlier detector raised an alarm after 1.26 h. The sensor is simulated, "no physical accelerometer was used" (Sec. VII), and the bias state was designed after the logged trips showed a 0.11 m/s^2 slow component (Sec. VII.C). The bias-aware detector is not replayed on those 70 logged trips (30 h), although the earlier one was (flagged 99% of the time). In simulation on the registered set it does not pass its criteria (533 of 560 on test; 27 late detections uncharacterised, Sec. VII.D).
**Why it matters**: The 120/120 figure is the abstract's second positive result, yet the registered simulated set gives 95.2% on test, and the one real-data stress test was left out.
**Suggestion**: Replay the final detector on the 70 logged trips (and the VED trips) and report the flagged share against the earlier 99%. Report exact (Clopper-Pearson) bounds for 120/120 and a rate bound with exposure hours for false alarms. Give both the on-target 120/120 and the simulated 533/560 in the abstract. Characterise the 27 late detections. Increase clean-driving exposure to tens of hours of replayed logged data.

### W5: No code, firmware or data availability statement
**Severity**: MAJOR
**Problem**: Sec. III.E stresses provenance ("each result is tied to the file that produced it"), but the manuscript does not name a repository, firmware build, generated weight header, training seeds, toolchain versions or release date for anything beyond the two public datasets [13], [14]. Because the controller arm is a compile-time choice (Sec. III.B), the exact images matter.
**Why it matters**: Reproducibility is the main review criterion at this venue, and the study's value depends on others being able to rerun the 36-run campaign.
**Suggestion**: Add a data and code availability statement with a persistent identifier covering firmware for both controller images, the weight header, plant parameters, the campaign configuration (cell list, noise seeds), the logged raw results, and the pre-registration record (see W6).

### W6: Post-hoc exclusions and unverifiable pre-registration provenance
**Severity**: MINOR
**Problem**: The two nonzero delay settings were excluded after the runs were seen, with the exclusion threshold (tracking error of 1 m/s or more) "fixed after those runs were seen" (Sec. VI.D). Cells above 16 dropped frames were re-run, and eight cells in the fault campaign were set aside (Sec. III.E); the origin of the 16-frame threshold is not given. The G2 revision came after the original criterion failed on all seven trips (Sec. III.C). All are disclosed, but the manuscript gives no dated record showing when gates and criteria were fixed.
**Why it matters**: The paper rests its credibility on pre-registration, and each post-hoc step is small but they add up; a reader needs the timestamps to believe "written before each experiment".
**Suggestion**: Cite a dated, immutable record (repository tag or commit) for the gates and the campaign definition. Tabulate every exclusion and re-run (count, rule, when the rule was fixed) in one place, and give the excluded delay-setting results in the appendix so readers can see them.

## Detailed Comments

### Title & Abstract
The title promises "Pre-Registered Acceptance Gates"; the abstract says "Two acceptance gates fail" but Sec. VII.B reports a third failed pre-registered criterion and Sec. VII.D a detector that does not pass its registered criteria in simulation. The abstract should state the full count of failed criteria and pair the on-target 120/120 with the simulated 533/560.

### Introduction
The three questions (logged data, closed loop, real-time deadline) map onto the experiments, and the PIL-versus-HIL distinction is made early. The contribution list is measured-or-simulated labelled. No methodological objection.

### Literature Review / Theoretical Framework
Outside my scope, except the point that [10] is cited for seed and tuning sensitivity, which the paper itself then does not address for its SAC arm (W2).

### Methodology / Research Design
The PIL arrangement, serial protocol, pipelined mode one period stale (Sec. III.A) and the compile-time controller selection with a diagnostic counter as check (Sec. III.B) are well specified. Gaps: noise seed crossed with factor level (Sec. III.E); the origin of the 16-drop rule; tuning budgets for both arms; no stated statistical analysis plan. The one-factor-at-a-time design (Sec. VI.D) leaves interactions (for example downhill with low SOC) untested.

### Results / Findings
Table 5 and Fig. 7 are clear, with per-cell values and tracking RMSE in the same table. The text says the other 13 settings "lie between 0.03% and 0.82%", but Table 5 includes -0.02% (uphill) among the 14 US06 cells, so the range should be restated. The Kalman result (9.44 to 0.24 Wh/km at ten times noise, Table 6) is a large effect against a baseline run-to-run difference of about 0.1% and is credible; note that the 0.24 and 9.44 are computed against second-seed floor runs (190.56 and 190.98), and the first-seed floors differ by 0.19 Wh/km, so the 0.24 is within seed noise and should be described as "no measurable loss". Forecast Table 4 acknowledges top-three differences are within seed spread (0.038 to 0.174 kW).

### Discussion
Sec. IX.A (rules within 0.16% of DP) is the strongest argument in the paper and should move into the Introduction or Sec. VI as the framing of the whole comparison. Sec. IX.B (what the method caught) is a useful account of the process but ought to state which of the four catches the gates would have caught on their own (the power-limit fault was not).

### Conclusion
Mostly consistent with the evidence. The last-but-one sentence ("classical estimation and hand-written rules survived measurement") is stronger than the simulated reviewer comparison supports; the final sentence on the accelerometer is well judged.

### References
Citations of [10], [11] on RL reproducibility fit the paper's stance. No methodology issue.

## Questions for Authors

1. How many distinct noise seeds underlie Table 5, and what is the paired spread of learned minus rules across repeat runs of one identical cell, for both US06 and the other cycles? How were the 95% intervals in Sec. IV.E and Sec. VI.C computed, and on how many pairs?
2. What happens to the 1-of-16 verdict and the 0.94% mean if the rolling coefficient, R0 and regeneration ceiling are moved across plausible bounds? Which ambient temperature do the Table 5 campaigns use, and how does it relate to the winter-only validation envelope?
3. What was the tuning budget and procedure for the rule constants and for the SAC reward weights, learning rate and network size, and why is the SAC tracking RMSE 5 to 40 times the rules'?
4. How does the bias-aware detector behave on the 70 logged trips (30 h), where the earlier detector flagged 99% of the time?
5. Where is the dated record that fixes the gates, and what is the code, firmware and data release plan?

## Minor Issues

### Language / Grammar
- Sec. VI.D, "the other 13 settings lie between 0.03% and 0.82%" does not match Table 5 (uphill is -0.02%).
- Abstract and Sec. VI.D give 36 runs and 2,282,832 control steps including the four runs of the excluded delay settings; say so, or restate for the 32 valid runs.

### Citation Format
- [12] Espressif datasheet and [15] EPA schedules lack version, date or URL; [33] has no report number.

### Figures and Tables
- Table 5: add units to the RMSE columns in the header row and the per-cell repeat count to the table itself (it is in the caption), and add a column for the rule-arm replicate spread once repeats exist.
- Fig. 7a: a zero reference line and error bars would help once intervals exist.
- Fig. 8: mark the number of onsets per point (eight) on the axis, and give the crossover in the caption as unmeasured.
- Table 6: add the second-seed floor row to Fig. 9 so the 0.19 Wh/km floor difference is visible.
- Report intervals for the detector counts in Table 7.

### Layout
- Page 11 has a large empty block between the text and Table 5; Table 5 and Fig. 7 could sit together.

## Dimension Scores (template summary)

Scores on the 0-100 rubric are not produced here; the contract uses block, warn and pass (see the Dimension Scores section above).

## Editorial Decision

editorial_decision: major_revision
Derived from F2 (severity 70, two or more mandatory dimensions at warn or worse; D1, D2 and D3 each score warn). F1 and F3 did not fire, and F0 does not apply. Recommendation: Major Revision, confidence 4. The mandatory fixes are repeat runs with intervals for the main comparison (W1), a plant-sensitivity check of the verdict together with closed-loop gate coverage (W3), real-data and interval-bounded fault-detector evidence (W4), and a code and data availability statement (W5). The paper's own failed gates and withdrawn result show the authors can meet these requests.
