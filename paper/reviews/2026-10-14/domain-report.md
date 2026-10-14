## Dimension Scores

### D1: methodology_rigor
score: warn
The study design is unusually transparent for this field: standard cycles (UDDS, HWFET, US06, WLTC3B, Sec. IV-A, VI-A), a stated longitudinal model (Eqs. 1-5, Table 3), a comparable-energy scale that charges shed cabin heat back (Sec. VI-B), measured versus simulated labels on every result, and a timing record on the target (Table 2, Fig. 2). The Phase 1 block trigger (a plant or accounting choice that favours one arm) was found in the earlier campaign, but the paper identifies it, fixes it and withdraws the result (Sec. IV-E, VI-E), so it does not fire on the reported results. Warn triggers that do fire: (a) the headline comparison, Table 5 and Fig. 7, is one run per cell per controller with no interval, and the paper itself says seeds only replay the noise draw (Sec. III-E), so most per-setting differences (+0.03 to +0.82%) cannot be separated from run-to-run spread (the rule arm differs by 0.16% between identical campaigns, Sec. VI-D); (b) the plant fails its own gate G2 on 1 of 7 trips (B08, 2.45 against 2.00 pp, Fig. 3) and the fitted chassis coefficients are admittedly lumped (c_rr = 0.01947 against 0.00878 measured on a Leaf, Sec. IV-C), so the absolute Wh/km and the regeneration headroom are not trustworthy; (c) an exclusion rule was fixed after results were seen (Sec. VI-D: "tracking error of 1 m/s or more for either controller, was fixed after these runs were seen"), removing two of three delay levels; (d) only one learned algorithm and one reward design (Sec. IX-C).

### D2: domain_accuracy
score: warn
Strong points: the paper states precisely what the energy manager controls in a single-source BEV (regeneration blend, discharge ceiling, auxiliary shed; speed reference not touched, Sec. VI-A), distinguishes PIL from HIL (Sec. I, III-A), reports correct cycle lengths and distances (UDDS 1369 s/11.99 km, HWFET 765 s/16.51 km, US06 600 s/12.89 km), and the DP bound argument (Sec. VI-A, IX-A) is physically sound. Block triggers do not fire: no physics error that changes a conclusion was found and no prior work is misdescribed. Warn triggers that fire: (a) the related-work base for learned EMS is three hybrid-vehicle works plus one BEV/ultracapacitor work (Sec. II-B, Table 1); no ECMS-style or MPC baseline is built, no BEV eco-driving or predictive speed-and-energy literature is cited although Sec. VIII is an eco-driving study (the DP planner [19] saves 10.4% on the US06 route), and no RL-reliability literature beyond [10]; (b) Table 1 is made of six works with many "not stated" cells, so the novelty statement "none states a loop timing measured on the target processor" (Sec. I) rests on a small, selected sample; (c) XGBoost and LSTM are used without citation (Table 4), and the Kalman estimator is evaluated against a "baseline speed loop" whose filtering is not described (Sec. VII-A, VII-B), so the claim that classical estimation "survived measurement" (Sec. X) cannot be placed against a simple low-pass or moving-average filter; (d) the sensor noise is seeded white noise scaled by a "stated floor" (Sec. VI-D, VII-A) while real vehicle speed signals have quantisation and wheel-slip error, which limits the transfer of the 9.44 to 0.24 Wh/km figure.

### D3: argumentative_coherence
score: warn
The thesis (rules held, forecast and learned policy gain nothing, the usable result is estimation) follows from the tables, mechanisms are tied to logged quantities (Sec. IV-E fixed-ceiling sweep, Fig. 4; Sec. VII-A reversal counts), and negative or reversed results are reported (Sec. VI-E). Block triggers do not fire. Warn triggers that fire: (a) the abstract says "the one criterion revised afterwards is reported" and "Two acceptance gates fail", but Sec. VI-D reports a post-hoc exclusion rule, Sec. VII-B reports a failed pre-registered clean-tracking bound (0.0193 against 0.0104 m/s, tolerance 0.005), and Sec. VII-D says the bias-aware detector does not pass its registered criteria; the count of failed or altered criteria is therefore larger than the abstract states; (b) "pre-registered" in the title and abstract overstates a procedure in which gates were written in the project record, not deposited with a time-stamped registry, and one gate was revised after failing on all seven trips; (c) the headline "0.94% more energy on average" is pulled by two settings (+5.71% downhill, +4.45% noise 10x); the other 13 lie between 0.03 and 0.82%, which the text states, but the abstract reports only the mean; (d) the negative result is strongly conditioned on the design: with speed fixed by an inner loop and only three actuation numbers (Sec. VI-A), the DP bound leaves at most 0.16% to gain (Sec. VI-A), so the finding follows largely from the problem definition, and the limitation is acknowledged only partly in Sec. IX-A.

### D4: cross_disciplinary_relevance
score: pass
RL, estimation and embedded terms are defined for a vehicle-engineering reader (SAC, PIL, MAC counts, Kalman innovation, FastGRNN), the target-side evidence is what an embedded reader expects (loop period histogram, Fig. 2; heap and image size; counters; zero late steps; Poisson interval on dropped frames, Sec. III-D), and the link-outage fallback (Sec. VI-F, Fig. 8) is a safety-relevant behaviour with its crossover reported honestly. Minor weaknesses (no mention of functional-safety practice such as ISO 26262 or of calibration effort for rule sets, and "pre-registered" used without reference to the ML and clinical-trial practice it borrows from) do not meet the warn trigger, because the paper does not propose deploying the learned controller and limits its claims "to this vehicle model, these four cycles and this class of processor" (Sec. IX-A).

### D5: writing_and_structure
score: pass
Structure is clear (gates in Table 2, results in Tables 4-8, limitations Sec. IX-C), measured and simulated are marked in every caption, and figures have units. Minor items: Table 5 and Table 6 give no interval or run count beyond "one run per cell"; Sec. VI-D mixes cycle (UDDS, HWFET) and US06 factor settings in a single "16 valid settings" table, which hides that the factor sweeps are one-at-a-time; some paragraphs (Sec. V-C to V-E) carry detail that would fit an appendix. These do not impede checking the domain claims.

## Failure Condition Checks

### F1
fired: false
No mandatory dimension (D1, D2, D3) scores block on my scores.

### F2
fired: true
Three mandatory dimensions (D1, D2, D3) score warn; the condition is two or more.

### F3
fired: false
The only high-priority dimension, D4, scores pass.

### F0
fired: false
Not every mandatory dimension scores pass.

## Review Body

### Reviewer Information
Peer Reviewer 2 (Domain). Researcher in battery-electric-vehicle energy management and eco-driving. Focus: literature coverage, domain correctness of terminology and physics, genuine incremental contribution to the EMS field, correct representation of prior work.

### Summary Assessment
The manuscript reports a processor-in-the-loop study on an ESP32-S3 at 100 Hz comparing a rule-based energy manager with a SAC policy on a longitudinal BMW i3 model, with acceptance gates fixed in advance. Its main finding is negative: after correcting a power-limit fault in the plant, the learned policy used less energy in 1 of 16 settings and 0.94% more on average, a forecast gave nothing, and the useful results are a two-state Kalman speed estimator (9.44 to 0.24 Wh/km at ten times the noise floor) and a bias-aware sensor-fault detector. As an engineering record this is honest and unusually well labelled (measured against simulated), and the withdrawal of the earlier 8.28% gain is exactly what a reader should want to see. From a domain view the contribution to the EMS field is real but narrow: the energy manager here has no authority over speed, so the DP bound (0.01 to 0.16%) shows in advance that there is almost nothing to learn, and the negative result should not be read as evidence about learned EMS in general. The literature base is thin for BEV eco-driving, predictive and ECMS/MPC control, and the baseline for the estimator is not characterised. Several procedural statements in the abstract (one revised criterion, two failed gates, pre-registered) understate the post-hoc steps found in the body. The paper is technically sound enough for IEEE Access, which weighs soundness over novelty, but needs a revision on literature positioning, interval reporting for the main table, and a precise account of what was pre-registered. Recommendation: Major Revision (borderline with Minor).

### Strengths
S1: Plant artefact found, explained and withdrawn. Sec. IV-E and Fig. 4 show that the battery power ceiling was applied only to the billed power, so a lower ceiling cut billed energy without reducing delivered torque; a fixed-ceiling sweep with no controller reproduces it (5 kW ceiling: 8.05 Wh/km before, 156.15 after). This is a domain-relevant lesson for anyone evaluating learned EMS on a simulator.
S2: Correct framing of the control problem. Sec. VI-A states what the manager decides and that it cannot change the speed reference; Sec. VI-A and IX-A back the conclusion with an offline DP bound on four cycles (rules within 0.01 to 0.16%). This is the right benchmark for a "does learning help" question.
S3: Comparable energy scale. Charging shed cabin heat back (Sec. VI-B) avoids the common error of crediting a controller that simply switches the heater off; the paper reports that every trained arm looks better on raw Wh/km than on the comparable scale.
S4: Measured against simulated discipline and on-target costs. Table 2, Fig. 2, Sec. III-B/D report timing on the target, with the failure of G3 (9 dropped frames in 59,650 loops) reported, together with Poisson intervals over five repeats (8.8 per run, 6.4 to 11.8).
S5: Closed-loop value of estimators and monitors. The finding that classification accuracy offline did not predict closed-loop benefit (Sec. VII-E, Fig. 11) is a useful domain result.

### Weaknesses

#### W1: Related work is thin for BEV eco-driving, predictive and classical benchmarks
Severity: MAJOR
Location: Sec. II-A to II-D, Table 1; Sec. VIII.
Problem: The learned-EMS review (Sec. II-B) cites three hybrid-vehicle works and one BEV/ultracapacitor work. Sec. VIII is an eco-driving study (DP speed planning, corridor against traffic, student policy) but cites only Bellman [19]; the optimal-control eco-driving literature, look-ahead RL EMS with velocity prediction and HIL validation, and RL evaluation-reliability work are absent. Table 1 has six prior works with "not stated" cells, so the claim that none states a loop timing (Sec. I) rests on a small sample.
Fix: Add a short BEV-specific review (eco-driving, predictive EMS with velocity forecasting, ECMS/MPC for BEV thermal and auxiliary load) and widen Table 1 to include look-ahead RL-EMS works with HIL validation; state how the sample was chosen. Suggested references are in the Missing References section.

#### W2: Headline comparison has no intervals and the exclusion rule was set after the data
Severity: MAJOR
Location: Table 5, Fig. 7, Sec. VI-D; Sec. III-E.
Problem: Table 5 gives one run per cell per controller. Sec. III-E states that seeds replay the noise draw and do not make independent repeats; the rule arm differs by 0.16% between two identical campaigns (Sec. VI-D). Differences of +0.03 to +0.82% on 13 settings are therefore within spread, and "1 of 16" depends on a -0.02% result. The delay axis was cut from three to one level by a tracking threshold "fixed after these runs were seen".
Fix: Report, for the rule arm and for the learned arm, a repeat count and an interval per cell (for example 5 plant-parameter or driver perturbations, not only noise seeds), and report the aggregate as a median with an interval across settings, instead of a mean pulled by two outliers (+5.71, +4.45). State the exclusion rule as post hoc in the abstract and in Table 5's caption, and show the excluded delay cells.

#### W3: Procedural claims in the abstract and title understate post-hoc steps
Severity: MAJOR
Location: Abstract; Sec. III-C; Sec. VI-D; Sec. VII-B, VII-D.
Problem: The abstract states that the one criterion revised afterwards is reported and that two acceptance gates fail. The body also reports a post-hoc exclusion rule (Sec. VI-D), a failed registered clean-tracking bound (0.0193 against 0.0104 m/s, Sec. VII-B), and detector criteria that are not met (Sec. VII-D). "Pre-registered" in the title implies an external registry; the text only says gates were written before each experiment.
Fix: Replace "pre-registered" by "pre-specified" or document where and when gates were recorded; add a table of all criteria (gate, source section, status: met, failed, altered) so the count in the abstract matches the body.

#### W4: Plant fidelity limits what the energy numbers can mean
Severity: MAJOR
Location: Sec. IV-B to IV-D; Table 3; Fig. 3.
Problem: The fitted c_rr is 2.2 times a published Leaf coastdown value, and the paper itself says the lumped coefficients "reproduce logged power, and none measures the quantity it is named after"; the rotational factor e = 0.1706 is high for a one-ratio EV drivetrain; one of seven validation trips fails G2; the envelope is winter only (-3.3 to 10.2 C); the transfer to a second vehicle covers 2.5 of 3.5 points of energy error. Regeneration headroom and ceiling binding, which decide the learned-versus-rule result, depend on exactly these quantities.
Fix: Add a sensitivity study of the headline result to c_rr, e, regeneration ceiling and drivetrain efficiency (for example +/-30%), and state that the energy figures are model-relative. Note in the limitations that cabin-comfort loss from heater shedding is not modelled.

#### W5: Negative result is conditioned on a very small action space, and the learned baseline is a single design
Severity: MINOR
Location: Sec. VI-A, VI-B, IX-A, IX-C.
Problem: With the speed loop fixed and three outputs, the DP bound is at most 0.16%, so a learned policy cannot win by construction; the paper concedes this partly but the title and abstract speak of "learned versus rule-based energy management" in general. The learned arm is one SAC configuration (8-64-64-3, 200,000 steps, one reward) with no comparison to another algorithm or to a tuned rule variant (Sec. IX-C).
Fix: Qualify title or abstract ("when the manager cannot change the speed"), and add one more learned or classical (ECMS-style or MPC) arm or state that the question is open.

#### W6: Estimator baseline and noise model not characterised
Severity: MINOR
Location: Sec. VII-A, VII-B, Table 6, Fig. 9.
Problem: The Kalman estimator is compared with a "baseline speed loop" that takes the noisy reading into the PID; no simple filter (low-pass, moving average) is included, so the 9.44 to 0.24 Wh/km gain does not show what a Kalman filter adds over trivial smoothing. Noise is seeded white noise scaled by a "stated floor".
Fix: Add a low-pass or alpha-beta arm and a coloured or quantised noise case; state the noise floor value in m/s.

### Detailed Comments

#### Title and Abstract
The title is accurate on platform and method, but "Learned Versus Rule-Based Energy Management" is wider than the tested scope, and "pre-registered" is stronger than the body supports (W3, W5). The abstract is complete and its numbers match the body (36 runs, 2,282,832 steps, 16.6%, 36.46 ms, 9.44 to 0.24, 120 of 120).

#### Introduction and Literature Review
Motivation is clear and the three questions follow from the starting study [4]. The classic anchors are present (DP [19], PMP [20], ECMS [21], [22]). Gaps: BEV eco-driving, look-ahead RL EMS, evaluation reliability, and citations for XGBoost and LSTM.

#### Method and Terminology
Terminology is generally correct (PIL versus HIL, regeneration blend, comparable energy scale). The WLTC class 3b cycle is introduced in Sec. VI-A as "WLTC3B" without definition; "energy manager" should be explicitly said to differ from a hybrid power-split manager at first use (Sec. I).

#### Results
Tables 2, 4, 5, 6, 7 are readable. Table 5 and Fig. 7 lack intervals. In Table 5 the learned policy has 0.17 to 0.50 m/s tracking RMSE on US06 settings against 0.02 to 0.10 for the rules; this is a larger and more consistent effect than the energy difference and deserves one sentence explaining why tracking, not energy, is where the learned arm loses.

#### Discussion and Conclusion
Sec. IX-B (what the method caught) is valuable. The conclusion that "classical estimation and hand-written rules survived measurement" should be limited to the tested plant and to the baseline used (W6). Future work is sensible; the physical accelerometer is the right next step.

#### References
Format is consistent. Recency: five items from 2025 to 2026 plus 2018 to 2022 RL works; thin on 2021 to 2026 EMS literature specific to BEV.

### Missing References (existence confirmed by search)
- A. Sciarretta, G. De Nunzio and L. L. Ojeda, "Optimal ecodriving control: Energy-efficient driving of road vehicles as an optimal control problem," IEEE Control Systems, vol. 35, no. 5, pp. 71-90, 2015, doi: 10.1109/MCS.2015.2449688. Needed for Sec. VIII.
- T. Liu, X. Hu, S. E. Li and D. Cao, "Reinforcement learning optimized look-ahead energy management of a parallel hybrid electric vehicle," IEEE/ASME Transactions on Mechatronics, vol. 22, no. 4, pp. 1497-1507, Aug. 2017, doi: 10.1109/TMECH.2017.2707338. Look-ahead RL EMS with velocity prediction and hardware-in-the-loop validation; relevant to Table 1 and to the forecast ablation (Sec. V, VI-C).
- R. Agarwal, M. Schwarzer, P. S. Castro, A. Courville and M. G. Bellemare, "Deep reinforcement learning at the edge of the statistical precipice," Advances in Neural Information Processing Systems 34 (NeurIPS 2021), arXiv:2108.13264. Interval estimates and robust aggregates for few-run RL comparisons; relevant to W2.
- Not confirmed by search and so listed by name only: standard citations for XGBoost (Chen and Guestrin, 2016) and LSTM (Hochreiter and Schmidhuber, 1997), to be checked by the authors.

### Questions for Authors
1. Which noise or filtering does the "baseline speed loop" apply to the speed reading in Sec. VII-A, and how does the Kalman estimator compare with a fixed low-pass filter at the same noise levels?
2. How much of the +0.03 to +0.82% spread in Table 5 survives a repeat with independent plant perturbations, given that the identical rule campaigns differ by 0.16%?
3. Where and when were the five gates and the Sec. VII criteria recorded before the experiments, and which criteria, besides the plant criterion, were altered after results were seen (the 1 m/s exclusion in Sec. VI-D)?
4. Does the learned-versus-rule result change if the energy manager were allowed to modify the speed reference within a band, as in Sec. VIII?

### Minor Issues
- Sec. VI-A: define WLTC class 3b at first use; the text uses "WLTC3B" and, in the abstract of the related study, WLTP is not used; keep one name.
- Sec. I, last paragraph of contributions: the Transformer latency (36.46 ms of a 40 ms budget) is 91% of budget (Table 4 says 91, Sec. V-D says 91%, Table 4 LSTM 88%); state in the abstract that this is the vendor build.
- Table 5: add run count and interval columns; mark the two excluded delay settings in the caption.
- Table 1: define "not stated" as "not reported in the source" and add the date the sources were checked.
- Fig. 5 and Fig. 6: axis units are present; the legend text in Fig. 5 is small and near the 8 pt limit.
- Sec. V-A: cite XGBoost and LSTM at first use.
- Sec. VII-A: give the "stated floor" in m/s.

### Dimension Scores (rubric reference; the contract's failure conditions govern the decision)
| Dimension | Score | Descriptor | Notes |
|---|---|---|---|
| Originality (20%) | 62 | Adequate | Negative-result PIL study with a withdrawn artefact; narrow scope |
| Methodological Rigor (25%) | 68 | Adequate | W2, W4 |
| Evidence Sufficiency (25%) | 70 | Adequate | Many sources for engineering context, thin BEV eco-driving and RL-reliability |
| Argument Coherence (15%) | 74 | Adequate | W3 |
| Writing Quality (15%) | 80 | Strong | Clear, well labelled |
| Literature Integration (optional) | 66 | Adequate | W1 |
| Weighted average | about 70 | Minor/Major boundary | Contract rule F2 gives Major |

### Recommendation
Major Revision. Confidence: 4 (mostly within my expertise; I did not judge the microcontroller timing methods in depth).

## Editorial Decision
Derived from the fired condition F2 (severity 70, highest among fired conditions): editorial_decision=major_revision.
