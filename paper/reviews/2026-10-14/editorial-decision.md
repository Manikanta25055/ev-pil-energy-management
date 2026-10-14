# Editorial Decision

## Manuscript Information
- Title: Learned Versus Rule-Based Energy Management for Electric Vehicles on a Microcontroller: A Processor-in-the-Loop Study With Pre-Registered Acceptance Gates
- Manuscript: mock IEEE Access draft, `paper/EV-PIL-mock-paper-IEEE-Access.pdf` (18 pages), commit d24ae52
- Decision date: 2026-10-14
- Review round: 1 (simulated; academic-paper-reviewer v1.9.1, full mode, sprint contract `reviewer/reviewer_full/v1`)

## Decision

### Major Revision

No reviewer and no failure condition supports Reject. The Devil's Advocate raised no CRITICAL issue.

## Contract Synthesis (mechanical, Sprint Contract Section 8)

Step 1, scoring matrix:

| Dimension | Priority | EIC | R1 Methodology | R2 Domain | R3 Perspective | DA |
|---|---|---|---|---|---|---|
| D1 methodology_rigor | mandatory | warn | warn | warn | warn | warn |
| D2 domain_accuracy | mandatory | warn | warn | warn | pass | warn |
| D3 argumentative_coherence | mandatory | warn | warn | warn | pass | warn |
| D4 cross_disciplinary_relevance | high | pass | pass | pass | warn | warn |
| D5 writing_and_structure | normal | warn | pass | pass | pass | warn |

Step 2, failure conditions (N = 5; majority means at least 4):

| Condition | Quantifier | Holds for | Fired |
|---|---|---|---|
| F1 any mandatory dimension scores block (sev 90) | any | 0 of 5 | false |
| F2 two or more mandatory dimensions warn or worse (sev 70) | majority | 4 of 5 (EIC, R1, R2, DA) | true |
| F3 any high-priority dimension scores block (sev 60) | any | 0 of 5 | false |
| F0 every mandatory dimension scores pass (sev 10) | all | 0 of 5 | false |

Step 3: the only fired condition is F2, so the decision is `major_revision`.

## Reviewer Summary

| Reviewer | Role | Recommendation | Confidence |
|---|---|---|---|
| EIC | Associate Editor, IEEE Access (vehicular technology, EV powertrain control) | Major | 4 |
| R1 | HIL/PIL validation and RL benchmarking methods | Major | 4 |
| R2 | BEV energy management and eco-driving | Major (borderline Minor) | 4 |
| R3 | Embedded ML, functional safety, ML reproducibility | Minor (borderline Major) | 4 |
| DA | Sceptic of learning-based control claims | Major, no CRITICAL | 4 |

EIC novelty rating: 5 of 10. Most original contribution, in the EIC's words: the audited withdrawal of the 8.28% learned-policy gain traced to a power ceiling applied to the bill but not to delivered torque, diagnosed with a controller-free sweep (Fig. 4, Sec. IV-E, VI-E).

## Strengths the panel agrees on

- The 8.28% gain is withdrawn in the paper itself, with the mechanism shown (EIC, R1, R2, R3, DA).
- MEASURED and SIMULATED labels are applied consistently (all five).
- The dynamic-programming bound shows the rule baseline is not a straw man (R1, R2, R3, DA).
- On-target timing is measured, including the estimate against the measurement and the failed frame criterion (R1, R2, R3).
- Leakage safeguards, Python-to-C parity tests and a diagnostic that confirms which controller ran (R1, R3).
- Offline classification accuracy did not predict closed-loop benefit for the learned reviewers (R2, R3).

## Consensus Analysis

### [CONSENSUS-5] All reviewers

1. **No uncertainty on the headline comparison.** Table 5 is one run per cell per controller, with no interval on any cell or on the 0.94% mean (R1 W1, R2 W2, R3 W1, DA M6, EIC question). The reviewers counted six rows that repeat the US06 baseline (EIC, R1, DA M2). The campaign data show five (Mixed, No delay, Flat, Noise 1x, Driver 1.0; SOC 0.55 starts at a different charge level), with rule-arm energy 190.73 to 191.41 Wh/km. That makes 12 distinct conditions, not 16 (synthesizer check against docs/week11-pil-corrected.json). The mean is driven by two cells, +5.71% downhill and +4.45% at 10x noise; the median is about 0.3% (R3, DA).
2. **The fault-detector headline is stronger than its basis.** 120 of 120 is 40 software-injected faults times 3 noise draws, against a simulated sensor. The detector was never replayed on the 70 logged trips that broke the first detector. In simulation it misses its registered criteria (551 and 533 of 560), which the abstract omits. One clean hour without false alarms carries no interval; at 95% that is about 3 false alarms per hour (R1 W4, R2 W3, R3 W3, DA M10, EIC 4). Verified in Sec. VII-D.

### [CONSENSUS-4]

3. **"Pre-registered" claims more than the record shows** (EIC 3, R1 W6, R2 W3, DA M4). The delay-exclusion rule was "fixed after those runs were seen" (Sec. VI-D). The abstract says "Two acceptance gates fail", but Sec. VII reports a further failed registered criterion (clean tracking, 0.0193 against 0.0104 m/s) and the detector's failed criteria. There are no dates or commit references for the gates. The headline learned-versus-rules comparison has no registered criterion in Table 2 (DA M4). R3 did not raise this.
4. **The null result is largely built into the task, and the title does not say so** (EIC 1, R1 W2, R2 W5, DA M1). Speed is fixed by the tracking loop, the policy has three actuation numbers, shed heat is charged back at its own price, and the rules sit within 0.01% to 0.16% of the DP optimum (Sec. IX-A). The title and abstract read as a general learned-versus-rule verdict. R3 did not raise this.

### [CONSENSUS-3]

5. **No code, firmware or data availability statement** (EIC 5, R1 W5, DA M9). Verified: none in the manuscript. With the controller arm selected at compile time, the exact images matter (R1).
6. **Plant fidelity is not carried into the conclusions** (R1 W3, R2 W4, DA M5). The rolling coefficient is 2.2 times a published value, G2 fails on 1 of 7 trips, the validated envelope is winter only, and transfer to the VED vehicle leaves 13.4% to 16.9% median energy error. There is no sensitivity study, and G2 never exercised the power-ceiling path that reversed the earlier campaign.
7. **Related work is thin and hybrid-centric for a BEV study** (R2 W1, EIC 5, DA M8). Speed planning (Sec. VIII) cites only Bellman. R2 confirmed by search three missing references: Sciarretta et al., IEEE CSM 2015 (eco-driving); Liu et al., IEEE/ASME TMech 2017 (RL EMS); Agarwal et al., NeurIPS 2021 (RL statistical reporting).

### [SPLIT] / single-reviewer issues kept

- **The forecast ablation is not the Transformer** (DA M3, verified in Sec. VI-B). The ablated channels are the mean and maximum of reference-implied traction power. The abstract puts "removing the forecast from the policy changed nothing" right after the Transformer sentence, so a reader assumes the Transformer was ablated. This is kept as Required because it is a factual mismatch.
- **Four studies in one 18-page paper** (EIC 2): forecasting ends in a null effect, and planning is simulated only.
- **The Kalman estimator is compared only against the raw-reading loop** (EIC 4, R2 W6). There is no low-pass filter baseline.
- **Safety wording has no stated scope** (R3 W2). "The handling is there for safety" appears without any ISO 26262 or SOTIF disclaimer, and Fig. 8 shows the fallback benefit reversing between 4 and 5 s.
- **Tuning budget** (R1 W2, DA M9). There is one SAC reward design with no sweep, the rule tuning procedure is not described, and no hyperparameters are given for SAC, GRU or FastGRNN.
- **US06 was not truly sealed** (R1 g, DA M2). It was used in the earlier campaign that led to the plant fix, and it lies outside the training cycles. The learned tracking deficit appears on US06 only.
- **Dropped frames are not linked to energy** (DA M7). There were 4 to 16 per run, plus a post-hoc re-run rule, against an effect size of 0.03% to 0.8%.
- **ESP32-S3 results are not mapped to automotive-class MCUs** (R3 W5, EIC 5).

### Disagreements and resolution

- **D2 and D3: R3 scored pass, the other four warn.** The editor resolved this as warn. The undercounted failed criteria in the abstract and the forecast-ablation mismatch were checked against the text and hold.
- **Overall severity: R3 Minor, the others Major.** The contract decides: F2 fired.
- **R1 minor item rejected on verification.** R1 said "the other 13 settings lie between 0.03% and 0.82%" conflicts with uphill at -0.02%. Uphill is the single win, counted separately (1 + 2 + 13 = 16), so the sentence is correct.

### Devil's Advocate strongest counter-argument (summary)

The null result is close to built in. The speed reference is locked, shed heat is charged at exactly what it saves, and the rules are within 0.16% of optimal, so a learned policy has nothing to win and a tracking penalty to pay. The plant fault was caught only because a result looked too good for the learned policy (Sec. IV-E, IX-B), not because the gate method caught it. The DA judged the narrowly stated claim (this SAC policy, tuned once, on this plant and board) supported and Sec. IX-C states that scope, hence no CRITICAL issue.

## Decision Rationale

All five reviewers judged the work honest and carefully measured, and none found a block-level defect. The central negative result survives in its narrow form. Four of five reviewers found warn-level problems on at least two mandatory dimensions, so the contract requires Major Revision. The problems fall into two groups.

The first group is a mismatch between what the manuscript claims and what it shows. The title promises a general verdict on a task whose headroom is at most 0.16%. The abstract undercounts failed registered criteria. The "1 of 16" count includes five replicates. The forecast that was ablated is not the forecaster the paper describes. The 120 of 120 detector result rests on simulated faults. Text revisions fix all of these.

The second group needs analysis that may already be possible from existing data: intervals or paired statistics on Table 5, an availability statement, and plant sensitivity. The EIC's novelty rating (5 of 10) and R3's W4 both point to a framing the evidence supports better than the current title: an audit of how a vehicle-model artefact produced an 8% learned gain, plus a headroom bound showing why no honest gain was available. Minor Revision was rejected because the framing and statistics issues touch the headline claim. Reject was rejected because no reviewer found the core result unsupported.

## Required Revisions

| # | Item | Source | Severity | Section | New data? |
|---|---|---|---|---|---|
| R1 | Bound the title and abstract to the tested task; state the 0.01% to 0.16% headroom early | EIC, R1, R2, DA | Major | Title, Abstract, I, VI | No |
| R2 | Uncertainty on Table 5: paired differences with intervals, median, and the replicate structure stated (12 distinct conditions, 5 of the 16 settings repeat the baseline) | All five | Major | VI-D, Table 5, Fig. 7 | Analysis only; repeats if available |
| R3 | List every failed registered criterion and every post-hoc rule in one table, and make the abstract match | EIC, R1, R2, DA | Major | Abstract, III, Table 2, VI-D, VII | No |
| R4 | Restate the detector result: simulated faults, 3 draws of 40, failed simulated criteria, clean-hour interval; replay it on the 70 logged trips or state that it was not | All five | Major | Abstract, VII-C/D | Replay is host-side |
| R5 | Correct the forecast-ablation wording: two reference-derived channels, not the Transformer | DA, verified | Major | Abstract, VI-B | No |
| R6 | Add a code, firmware and data availability statement, including the exact images | EIC, R1, DA | Major | Back matter | No |
| R7 | Plant sensitivity on rolling coefficient, rotational factor, regeneration ceiling and drivetrain efficiency, or state the limit plainly in IX-C | R1, R2, DA | Major | IV, IX-C | Simulation, or text only |
| R8 | Report the SAC reward weights and hyperparameters, the rule tuning procedure, and GRU/FastGRNN settings | R1, DA | Major | VI-B, VII-E | No |

## Suggested Revisions

| # | Item | Source | Section |
|---|---|---|---|
| S1 | Reframe around the artefact audit and the headroom bound; shrink forecasting (V) and planning (VIII) to supporting roles | EIC, R3 W4 | Whole paper |
| S2 | Add BEV eco-driving and RL-EMS references, including the three confirmed by R2 | R2, EIC, DA | II, VIII |
| S3 | Scope statement on safety: no ISO 26262 or SOTIF claim; discuss the Fig. 8 reversal at 4 to 5 s | R3 | VI-F, VII, IX |
| S4 | Low-pass filter baseline for the Kalman result, or say why none was used | EIC, R2 | VII-B |
| S5 | Say that US06 was seen in the earlier campaign; note that the tracking deficit is US06-only | R1, DA | VI-B, VI-D |
| S6 | Relate dropped frames per run to energy differences | DA | III, VI-D |
| S7 | One paragraph on transfer to automotive-class MCUs: what ports and what does not | R3, EIC | IX-C |
| S8 | State the audit test from IX-A as a reusable check: a learner must not beat the offline optimum on the same plant | R3 | IX-A/B |

## Revision Roadmap

### Priority 1: framing and claim-evidence match (text only, about 2 to 3 days)
- [ ] R1, R3, R5: rewrite the title and abstract; build one table of all registered criteria and post-hoc rules
- [ ] S1: decide the reframe before editing sections (see the pending novelty note)
- [ ] R6, R8: availability statement and hyperparameter table

### Priority 2: analysis on existing data (about 3 to 5 days)
- [ ] R2: paired intervals and median for Table 5; replicate structure; check whether existing board repeats can supply run-to-run spread
- [ ] R4: replay the bias-aware detector on the 70 logged trips (host-side), or state that it was not done
- [ ] R7: plant sensitivity in simulation, or a firm limitation statement
- [ ] S4, S6: low-pass baseline (needs new runs) or a stated reason; dropped frames against energy

### Priority 3: literature and polish (about 2 days)
- [ ] S2, S3, S5, S7, S8
- [ ] Minor items from the reports: define "arm", "cell" and the "Mixed" row in Table 5; rewrite the GRU sentence in VII-E ("88% with none, against 94% and 1%"); the abstract's "36 runs" includes 4 excluded delay runs; blank space on page 11; cite XGBoost and LSTM

Estimated total: 2 to 3 weeks if R4, R7 and S4 stay host-side or text-only.

## Process notes

- Reviewer reports: `eic-report.md`, `methodology-report.md`, `domain-report.md`, `perspective-report.md`, `devils-advocate-report.md`. The paper-blind scoring plans are in the `*-phase1.md` files.
- Reviewers were Sonnet 5.5 at medium effort. Phase 1 was meant to be paper-blind, but the subagents load project memory automatically, and two Phase 1 plans mention project details (power ceiling, cabin-heat charge-back). The separation is therefore weaker than the protocol intends.
- Reviewers read only the rendered PDF and section sources, not the claims or audit files. The synthesizer checked the specific numeric claims used above against `paper/sections/`.
