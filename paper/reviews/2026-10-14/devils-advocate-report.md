## Dimension Scores

No Scoring Plan Dissent. The Phase 1 triggers were applied as committed.

### D1: methodology_rigor
Score: warn

The paper does several things well: seeded noise, parity tests (Sec. III.E), measured-versus-simulated labels, a Poisson interval on dropped frames (Sec. III.D), and an honest list of exclusions. The warn is driven by the following.

- The headline comparison is one run per cell per controller (Table 5, Fig. 7). No interval is attached to the 16 differences ("The 16 settings are different conditions, so no interval is attached to their average", Sec. VI.D). The paper itself puts the rule-arm campaign-to-campaign spread at up to 0.57% (Sec. IV.E), and 11 of the 16 differences in Table 5 lie below 0.6%.
- The 16 settings are not 16 independent conditions. 14 are US06-based, and six of them appear to be the same nominal US06 condition re-drawn under different noise seeds (Mixed, Flat, SOC 0.85, No delay, Noise 1x, Driver 1.0). Their rule-arm energies range over 190.73 to 191.41 Wh/km, and learned minus rules ranges over +0.03 to +0.55%. This is an inference from the design description, and the authors should state it.
- Training budget for the learned arm is 5 seeds x 200,000 steps, with no hyperparameter search, reward-weight tuning or learning-curve evidence reported (Sec. VI.B). At 10 Hz decisions this is about 5.6 h of driving, roughly six passes over WLTC3B plus UDDS. The tuning effort spent on the rules is not stated either. Budget parity cannot be checked.
- Two deviations are disclosed but post-hoc. The delay exclusion criterion (tracking error of 1 m/s or more) "was fixed after these runs were seen" (Sec. VI.D). The re-run rule for cells above 16 dropped frames (Sec. III.E) is looser than the zero-drop criterion of G3. Dropped frames per run were 4 to 16 (Sec. III.D), and their effect on energy is never bounded, although the compared differences are 0.03 to 0.8%.
- The manuscript has no data or code availability statement. The pre-registration is asserted but carries no timestamp, commit or external registry.

### D2: domain_accuracy
Score: warn

Strengths: the DP optimality bound (Sec. VI.A, IX.A) is the right tool for judging the baseline. The vehicle-model limits are candidly reported (Sec. IV.C-D). MEASURED and SIMULATED labels are consistent in the tables.

The warn rests on the following.

- The paper frames the question as "learned versus rule-based energy management for electric vehicles". Its positive prior work (refs [6], [7], [9]) concerns hybrid or dual-source architectures, where the optimisation problem has headroom. The tested vehicle is a single-source battery EV with three actuation knobs. The comparison therefore cannot speak to the literature it positions itself against.
- Cabin-heat shedding is charged back "at exactly the energy it saved" (Sec. VI.B). This makes shedding worthless by construction, with an unidentified cooling slope behind it (Sec. IV.B). On the raw scale the paper says every trained arm looks better, so the ranking sign depends on this metric choice.
- The vehicle model was identified on winter trips only, and the summer trips failed eligibility (Sec. IV.A). The fitted c_rr is 2.2 times the published Leaf value. The model's own energy error is 13% to 17% on VED, with arm C as the in-domain ceiling (Sec. IV.D). The paper never argues why controller rankings should be invariant to this error.
- A regenerative ceiling of 50 kW, an efficiency of 0.95 and a lower-bound R0 are assumed (Table 3). They are untested against the learned policy's ability to exploit them.
- Table 1 positions the work against six prior studies only. Nothing in the paper says why that set is representative.

### D3: argumentative_coherence
Score: warn

The core logic holds. The DP bound shows little headroom, and a learned policy with a tracking penalty to pay loses slightly (Sec. IX.A). The scope limits are stated in Sec. IX.C ("one algorithm, SAC, with one reward design; the result does not show that no learned policy could win"). The warn comes from the following.

- The negative result is largely determined by the design (M1 below).
- The 14 US06 settings carry the "tracking worse" claim, and US06 is outside the training cycles (M2).
- The ablation of "the forecast" may not test the Transformer forecaster (M3).
- The title and abstract promise pre-registered gates, but the headline comparison has none (M4).
- The claim that the method caught the plant fault is overstated (M5).

Headline sentences ("The main result is negative", "hand-written rules survived measurement") are broader than the body's own limitations paragraph.

### D4: cross_disciplinary_relevance
Score: warn

Terms are defined at first use (PIL versus HIL, Sec. III.A). On-device cost is reported next to accuracy for the forecasters (Table 4) and for the policy. The warn rests on the following.

- G5 is "not closed in full" (Sec. V.D), XGBoost has no latency, and GRU and FastGRNN costs are not reported against their accuracy.
- The pre-registration method is imported without justification or comparison to alternatives for engineering readers (M5). Its value as a method is argued from four "findings", at least one of which was not found by a gate.
- Transfer to other boards, vehicles or learning algorithms is explicitly disclaimed in Sec. IX.C. That is good practice, but the title's scope does not match.

### D5: writing_and_structure
Score: warn

Figures and tables are mostly clean and carry the labels. The warn rests on the following.

- Scope creep: Sections VII (fault detection, fused estimator) and VIII (speed planning) occupy roughly 4 of 18 pages and are not part of the title question. They dilute the headline and make the "so what" harder to find.
- The abstract says "Two acceptance gates fail", while the text reports further failed registered criteria (the Sec. VII.B tracking bound of 0.005 m/s and the detector's registered criteria in Sec. VII.D).
- The abstract says "36 runs and 2,282,832 control steps with no late step", but only 32 runs are in the valid comparison, since two excluded delay settings are included in the 36 (Sec. VI.D).
- Sec. VII.E sentence "88% with none, against 94% and 1% for the monitor" is unreadable as written.
- The detector result (120 of 120) in the abstract is not labelled measured or simulated, contrary to the paper's own rule.

## Failure Condition Checks

### F1
fired: false. No mandatory dimension scores block on my scores.

### F2
fired: true. D1, D2 and D3, all mandatory, score warn.

### F3
fired: false. D4, the only high-priority dimension, scores warn.

### F0
fired: false. Not every mandatory dimension scores pass.

## Review Body

### Strongest Counter-Argument

The paper reports a null result that its own design makes close to inevitable, and then gives that null the weight of a finding about learned energy management. The vehicle is a single-source battery EV. The energy manager has three knobs. The speed reference is locked, so it cannot save energy by driving differently. The cabin-heat lever is priced at exactly the energy it saves, so shedding is worth nothing. The rules already take all regenerative energy, and an offline dynamic-programming optimum sits within 0.01% to 0.16% of them (Sec. IX.A). A learned controller in this action space has nothing to win and only a tracking penalty to pay. The paper says this itself, and that is the whole result.

Two further weaknesses make the headline softer than it reads. First, the tracking deficit that drives the "worse" verdict is confined to US06, a cycle outside the training set (Table 5: 0.17 to 0.50 m/s on US06 against 0.004 to 0.016 m/s on HWFET and UDDS). A policy that tracks well on the cycles it saw and badly on one it did not is a generalisation failure of one agent trained for 200,000 steps with no reported tuning. It does not say learned control cannot match rules.

Second, the authors found a plant fault only because a learned result looked too good ("which should not be possible", Sec. IV.E). Faults that make learned policies look worse would not have triggered that scrutiny. The model still errs by 13% to 17% in energy on transfer (Sec. IV.D), and a reinforcement-learning agent is exactly the kind of component that finds plant exploits. The paper's trust in the corrected plant rests on a single targeted fix.

### Issue List

#### CRITICAL
None. No issue, if left unfixed, makes the narrowly stated central claim ("this SAC policy, tuned once, was not better than these rules, on this plant, four cycles and one board") unsupported. The paper states that scope in Sec. IX.C. M1 to M4 are the closest to the CRITICAL line, because they bear on the title-level claim.

#### MAJOR

| # | Dimension | Issue | Location | Fix |
|---|-----------|-------|----------|-----|
| M1 | D3 | The null is nearly determined by the design: speed reference locked, heat shedding priced to zero benefit, rules within 0.01-0.16% of the DP optimum. The comparison cannot discriminate between a good and a poor learned policy because there is no headroom, and the title and abstract do not say this. | Sec. VI.A, VI.B, IX.A; Abstract | State in the abstract and introduction that the problem has at most 0.16% headroom. Add a task variant with headroom (for example the planning task, where DP saves 10.4%, Table 8) and run the learned policy there, or reword the title to a bounded claim. |
| M2 | D1, D3 | 14 of the 16 settings are US06, outside the training set (training WLTC3B and UDDS, Sec. VI.B). The learned tracking deficit is US06-specific (Table 5). The six nominal-condition cells are replicates, not independent settings. "1 of 16" overstates independent evidence. | Table 5, Fig. 7, Sec. VI.B, VI.D | Train one arm with US06-like data and the sealed cycle held out differently. Report the number of distinct conditions, and per-cycle summaries with intervals. Explain the cause of the tracking deficit with a logged quantity (for example how often the learned ceiling falls below the demanded power). |
| M3 | D3, D2 | The ablated "forecast" appears to be two observation channels derived from the reference (mean and maximum of reference-implied traction power, Sec. VI.B), not the Transformer forecaster of Sec. V, which never ran in the loop (Fig. 1 caption). The abstract and Sec. VI.C then conclude "the forecaster ... this controller still gains nothing from it". Also, the ablation intervals are about 1.9 Wh/km wide (-0.698 to +0.982), wider than the headline gap. | Sec. V, VI.B, VI.C; Abstract | Either test the Transformer's output inside the loop, or reword to say reference preview was ablated and the forecaster was not tested in the loop. Add a power statement for the interval. |
| M4 | D3, D4 | The title and abstract stress pre-registered gates. Table 2 lists five gates (compute, plant, timing, forecaster accuracy and fit), and none states what would count as the learned policy winning or losing. The headline comparison has no registered criterion in the manuscript. The abstract ("Two acceptance gates fail") also disagrees with the text, which reports further failed registered criteria (Sec. VII.B, VII.D). | Table 2, Sec. III.C, Sec. VII | Add the criterion for the Section VI comparison and say when it was fixed, or drop "pre-registered" from the title. Reconcile the count of failed criteria, and add a registry reference, timestamp or commit. |
| M5 | D3, D4 | Sec. IX.B says the method caught four findings, but the power-ceiling fault was found "from three oddities in the campaign tables" (Sec. IV.E) because a learned result seemed too good, not by a gate (G2 part B passed on 7 of 7 trips). The audit is also one-sided: it was triggered only by an anomaly favourable to the learned policy. | Sec. IV.E, IX.B | Rephrase to credit the repeat rules and informal scrutiny, not the gates. Add a symmetric audit (for example plant perturbation tests with the learned policy, including the 50 kW regeneration ceiling, R0 and efficiency assumptions). |
| M6 | D1 | Statistics: the headline mean 0.94% is dominated by two cells (+5.71 downhill, +4.45 noise 10x). The median is about 0.3%, and 11 of the 16 differences are below the 0.57% worst-case spread. "Worse" is supported mainly on those two cells and on US06 tracking, not on a uniform energy deficit. | Table 5, Sec. IV.E, VI.D | Report median and interval, and repeat the two outlier cells with several noise seeds. |
| M7 | D1 | Dropped frames of 4 to 16 per run (Sec. III.D) and the post-hoc 16-frame re-run rule (Sec. III.E) are never connected to energy. The effect size sought is 0.03 to 0.8%. | Sec. III.D-E, Table 5 | Quantify the energy effect of dropped frames, for example by injecting extra drops in a rule-arm cell, and report the re-run counts per controller. |
| M8 | D2 | The framing and Table 1 position the work against hybrid and dual-source RL studies, while the tested vehicle is a single-source BEV with three knobs. The generalisation to "energy management for electric vehicles" is not established. | Sec. I, II.B, Table 1 | Narrow the framing, and cite non-RL baselines such as MPC or ECMS-style methods for the BEV case, not only DP. |
| M9 | D1 | No data or code availability, no training logs or reward weights, no hyperparameters for SAC, the GRU or FastGRNN. Training data and tuning for the learned reviewers are not described. | Sec. VI.B, VII.E; end matter | Add an availability statement and an appendix with hyperparameters, reward weights and learning curves. |
| M10 | D3, D1 | The bias-aware detector was designed after the earlier detector failed on logged trips (about 0.11 m/s² standing gap, Sec. VII.C). No re-test of the bias-aware design on those 70 logged trips is reported. The 120 of 120 on the target comes from software-injected faults on a simulated sensor with no such drift, and 3 draws of the same 40 faults are not 120 independent trials. | Sec. VII.C-D, Table 7 | Run the bias-aware detector on the 70 logged trips and report the flagged share. Report n as 40 distinct faults with 3 noise draws. |

#### MINOR

| # | Dimension | Issue | Location |
|---|-----------|-------|----------|
| m1 | D5 | The abstract's detector sentence is not labelled measured or simulated. | Abstract |
| m2 | D5 | "36 runs" includes 4 runs the authors excluded as invalid. The valid comparison has 32 runs. | Abstract, Sec. VI.D |
| m3 | D5 | The sentence "88% with none, against 94% and 1% for the monitor" is unreadable. | Sec. VII.E |
| m4 | D1 | Noise level is confounded with the noise seed (seeds 0, 1, 2 map to levels 1x, 3x, 10x, Sec. III.E). | Sec. III.E |
| m5 | D1 | The same nominal US06 cell shows different rule energies across Tables 5 and 6 (190.73-191.41 and 190.79-190.98 Wh/km), so a floor for single-run differences should be stated once and used consistently. | Tables 5-6 |
| m6 | D4 | G5 is reported as "Pass" in the abstract narrative but "not closed in full" in Sec. V.D, because the converted trained model was never run on the target. | Table 2, Sec. V.D |

### Ignored Alternative Explanations/Paths

1. Under-training or action-design explanation. The learned policy outputs the discharge ceiling affinely mapped to the physical range, so any noise in the ceiling output throttles the motor directly. The rules never do. The US06-only tracking deficit may be an action-parameterisation or training-distribution effect, not evidence about learned control. A constrained action space (ceiling clipped to a safe floor) would test it.
2. Headroom explanation. The paper's own DP bound implies any controller wins or loses by under 0.16%. The measured +0.94% average gap against that bound suggests the loss comes from tracking mechanics, not from energy-management quality. Both explanations predict the observed outcome, and the paper does not separate them.
3. Plant-exploit explanation. A reinforcement-learning agent that exploited one plant fault will exploit others (regeneration ceiling, efficiency, thermal assumptions). The remaining assumptions in Table 3 were not stress-tested with the learned policy.
4. Metric explanation. On raw Wh/km every trained arm appears better (Sec. VI.B). The sign of the headline depends on a 1:1 comfort-for-energy exchange rate that is not validated.
5. Learned estimation path. The conclusion says classical estimation "survived", but no learned speed estimator was compared with the Kalman filter. Only learned fault reviewers were tested, and only in simulation.

### Missing Stakeholder Perspectives

- Vehicle manufacturers and calibration engineers, who would ask about robustness over temperature, ageing and tyre or wind variation (the paper's own road-load bias spreads from -21% to +30%, Sec. IV.C).
- Embedded safety and certification engineers: the path from a PIL result with a non-real-time host to a certifiable controller is not discussed, and a host that drops 4 to 16 frames per run is a weak real-time stand-in.
- Practitioners using hybrid or dual-source vehicles, for whom the cited positive RL literature is relevant and for whom this paper offers nothing.

### Unexamined Premise

The paper assumes that a negative result against a strong, hand-written rule set on a tightly bounded problem is informative about learned controllers in general, and that its main value lies in method (gates, repeats). Neither the information content of a near-zero-headroom null nor the method's value over ordinary care is demonstrated.

### Observations (Non-Defects)

- Very candid reporting: withdrawn gain, failed gates, a failed detector, a negative estimator result, and an honest limitations paragraph (Sec. IX.C).
- The MEASURED versus SIMULATED labelling discipline is mostly consistent and is a real service to readers.
- The DP optimality check of the rules, the noise-floor reasoning for the 0.07% rule-arm difference, and the parity tests between Python and C are good practice.
- The Kalman result (9.44 to 0.24 Wh/km at 10x noise, Table 6, Fig. 9) is measured on the target, is plausible and is the most useful practical finding.
- The Transformer cost study (estimate 22.28 ms versus measured 36.46 ms, Sec. V.D) is a useful cautionary result on estimated latency.

### "So What?" Test

If the paper is right, a practitioner learns that a hand-written rule set for a single-source BEV is within 0.16% of optimal on four standard cycles, so spending effort on a learned supervisor is not worth it there. That is useful but narrow, and the paper's own DP check already shows it without any learned-policy experiment. The more transferable contributions are the measured Kalman result and the demonstration that vehicle-model faults can reverse a learning result. They are under-sold relative to the title.

### Recommendation

Major revision, confidence 4 of 5. The experimental discipline is unusually honest and the narrow claim is supported. The revisions needed are a bounded title and abstract, a registered criterion for the headline comparison, per-condition intervals, a test that separates the training-distribution and action-design explanations from "learned control loses", and a corrected account of which forecast was ablated.

## Editorial Decision

Derived from the fired condition F2 (severity 70, highest fired): editorial_decision=major_revision.
