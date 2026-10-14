## Dimension Scores

### D1: methodology_rigor
score: warn
Strong points: every result is labelled measured or simulated (Sec. III intro); Table 2 reports gate criteria beside outcomes, including two failures; 59,650-loop timing record (Fig. 2); host/firmware parity test (2.12e-06, Sec. III-E). Triggers of the Phase 1 warn pattern are present: the central comparison is one run per cell (Table 5, Fig. 7) with no interval on the 16-setting average ("no interval is attached", Sec. VI); one SAC policy (seed 3, chosen by lowest validation energy, Sec. VI-B) represents the whole learned arm; the delay axis was dropped by a rule "fixed after these runs were seen" (Sec. VI-D); the plant fails gate G2 on one of seven trips and is validated on winter trips only (Sec. IV-A). None of this reaches the block pattern, because the paper discloses each item and no headline verdict rests on an undisclosed artefact. Detailed statistics are left to the methodology reviewer.

### D2: domain_accuracy
score: warn
PIL is separated from HIL correctly and repeatedly (Sec. I, III-A, IX-C), the comparable-energy scale charges shed cabin heat back (Sec. VI-B), and the power-limit bookkeeping fault is found and explained physically (Sec. IV-E, Fig. 4). Warn triggers present: the fitted rolling coefficient 0.01947 is 2.2 times a published Leaf value and the authors state that the lumped coefficients "absorb" other losses (Sec. IV-C), so the plant that decides every comparison is only partly physical; the validated envelope is winter only (-3.3 to 10.2 C), yet the campaigns drive UDDS, HWFET and US06 and the ambient used is not stated in the main text; related work on the learned-controller side is almost wholly hybrid-vehicle (Sec. II-B, refs [6], [7], [8]) while the study is a battery EV with a fixed speed trace; battery-EV thermal/cabin energy management and eco-driving are thinly cited. No block-level error was found.

### D3: argumentative_coherence
score: warn
The core negative claim (learned policy does not beat rules, Sec. VI-D, IX-A) follows from Table 5 and from the dynamic-programming headroom bound (0.01% to 0.16%, Sec. VI-A), and the paper withdraws its own earlier 8.28% gain (Sec. VI-E). Warn triggers present: the title and abstract promise a general learned-versus-rule verdict, yet the headroom bound shows the question is almost decided before any policy is trained; the abstract says "one criterion revised afterwards" while the body also records a post-hoc exclusion rule (Sec. VI-D) and a detector redesign after the first detector failed (Sec. VII-C, D); the abstract's "Two acceptance gates fail" omits the failed tracking criterion (Sec. VII-B), the unmet detector criteria (551 and 533 of 560, Sec. VII-D) and G5 "not closed in full" (Sec. V-D); the abstract's positive detector result rests on software-injected faults and simulated drift (Sec. IX-C), which the abstract does not say. No fallacy undermines the central thesis, so not block.

### D4: cross_disciplinary_relevance
score: pass
Terms that matter to adjacent readers are defined where they first matter (PIL versus HIL, MEASURED versus SIMULATED, comparable energy scale, gate wording), and the plant-artefact lesson applies beyond EVs to any simulation-trained RL controller. Limits are stated plainly (Sec. IX-A closing sentence, IX-C). Caveat, not a score driver: relevance to automotive-grade controllers is asserted by "this class of processor" but an ESP32-S3 is not automotive-grade and no mapping of the 20 ms compute budget or 300 KB model cap to a production ECU class is given (Sec. III-B, Table 2).

### D5: writing_and_structure
score: warn
Prose is plain, numbers are specific, captions give run counts and measured/simulated status (Tables 4 to 8, Figs. 3, 7, 8). Warn triggers present: the manuscript carries four studies (power forecasting and distillation, Sec. V; rule versus SAC, Sec. VI; estimation and fault detection, Sec. VII; speed planning, Sec. VIII) of which the first and last are weakly tied to the title; headline numbers (1 of 16, 0.94%, 8.28%) recur in abstract, Sec. I, VI, IX and X; Table 2 gives no verdict for G5; "Mixed" in Table 5 is not defined in the text; the 36-run figure in the abstract includes the two excluded delay cells (Table 5 holds 32 runs).

## Failure Condition Checks

### F1 (severity 90): any mandatory dimension scores block
fired: false
D1, D2 and D3 are warn; none is block.

### F2 (severity 70): two or more mandatory dimensions score warn or worse
fired: true
D1, D2 and D3 are all warn.

### F3 (severity 60): any high-priority dimension scores block
fired: false
D4 is pass.

### F0 (severity 10): every mandatory dimension scores pass
fired: false
Three mandatory dimensions are warn.

## Review Body

# Peer Review Report

## Manuscript Information
- **Title**: Learned Versus Rule-Based Energy Management for Electric Vehicles on a Microcontroller: A Processor-in-the-Loop Study With Pre-Registered Acceptance Gates
- **Manuscript ID**: not assigned (mock manuscript)
- **Review Date**: 2026-10-14
- **Review Round**: Round 1

## Reviewer Information

### Reviewer Role
EIC (Associate Editor, IEEE Access, vehicular technology and EV powertrain control)

### Reviewer Identity
Associate Editor handling EV energy management and embedded control validation (HIL/PIL).

### Review Focus
Journal fit, originality and significance, whether the title, abstract and stated contributions match the evidence, whether the framing is the strongest the evidence allows, and readership relevance. Detailed statistics are deferred to the methodology reviewer.

## Overall Assessment

### Recommendation
**Major Revision**

### Confidence Score
4

### Novelty rating
5 out of 10. Single most original contribution: the audited demonstration that an apparent 8.28% energy gain for a learned policy came from a vehicle-model fault (a battery-power ceiling applied to the bill but not to delivered torque), found from three oddities in campaign tables, reproduced by a controller-free sweep (Fig. 4), corrected, and withdrawn in the paper itself (Sec. IV-E, VI-E). The remaining pieces are individually routine: a Kalman speed filter, a residual fault detector, a Transformer forecaster and a dynamic-programming bound.

### Summary Assessment
The paper compares a hand-written rule-based energy manager with a Soft Actor-Critic policy on an ESP32-S3 at 100 Hz, in a processor-in-the-loop arrangement with a simulated BMW i3-derived vehicle, under acceptance gates written before each experiment. After a plant fault is corrected, the learned policy uses less energy in 1 of 16 settings, 0.94% more on average, and tracks worse on US06 (Table 5). A dynamic-programming bound puts the available gain at 0.16% or less (Sec. VI-A). A forecaster, a Kalman speed estimator, fault detectors, learned reviewers and a speed planner are also assessed.

Journal fit is good: IEEE Access weighs technical soundness, measured on-target evidence and honest reporting of negative results, and this manuscript does that better than most. The weaknesses are in framing and scope. The title promises a general learned-versus-rule verdict that the evidence decides only for one battery-EV configuration where the headroom is almost nil. The manuscript carries four loosely connected studies. The "pre-registered" label is stronger than the record shown. The positive results in the abstract rest on simulated faults and on a weak comparator. These are fixable by reframing and trimming, hence Major Revision rather than Reject.

## Strengths

### S1: Candid withdrawal of an earlier result
Sec. VI-E and IV-E report that an apparent 8.28% gain (up to 21.6% at driver aggressiveness 1.5) was an artefact, give the diagnostic path, and show with Fig. 4 that a 5 kW ceiling billed 8.05 Wh/km for the full 12.89 km before the fix. The test "a limit that does not bind leaves the outputs unchanged" is reusable by other groups.

### S2: Explicit gates with failures reported
Table 2 lists criteria fixed in advance next to results, and keeps failures (G2 on one of seven trips, G3 frame criterion) in the abstract and Sec. IX-C. The MEASURED/SIMULATED label (Sec. III) is applied through the tables and captions.

### S3: Measured on-target timing and cost
Fig. 2 and Sec. III-D give 59,650 loops with 25 microsecond 99th-percentile deviation, five pooled repeats, and drops attributed to the host. Table 4 and Sec. V-D show a 64% gap between an estimated (22.28 ms) and a measured (36.46 ms) Transformer latency, which is a useful warning for the embedded-ML readership.

### S4: Structural explanation, not only a score
Sec. VI-A and IX-A bound the possible gain with an offline dynamic-programming optimum within 0.01% to 0.16% of the rules on four cycles, and explain why (speed fixed by the inner loop, discharge ceiling only removes power the loop needs, heating priced at its saving). This turns a null result into a mechanism.

### S5: Provenance and parity discipline
Compile-time controller selection confirmed through a diagnostic counter, seeded cells, and a step-by-step parity test between Python and C (2.12e-06, Sec. III-B, III-E) address common sources of silent error in PIL work.

## Weaknesses

### W1: Title and abstract claim a broader comparison than the evidence decides
**Severity**: MAJOR
**Problem**: The title and abstract present "Learned Versus Rule-Based Energy Management for Electric Vehicles". Sec. VI-A and IX-A show that in this setting (speed fixed by the inner loop, energy manager outputs three scalars, battery EV) the optimum is within 0.01% to 0.16% of the rules, so a learned policy "has almost nothing to win" before any training. The learned-controller literature cited in Sec. II-B ([6], [7], [8]) is mostly hybrid-vehicle, where headroom is large, so the result does not answer those claims. The headroom bound appears only on p. 10 and p. 16; the abstract does not state it.
**Why it matters**: A reader of the title would expect a general finding; the paper supports a narrower, still useful one. The most valuable results (the headroom bound and the artefact audit) are not the ones the title advertises.
**Suggestion**: Lead the abstract and introduction with the headroom bound and the artefact audit; qualify the title (for example battery EV, fixed speed trace, 100 Hz microcontroller); state in the contributions that the learned arm is one SAC design (already conceded in Sec. IX-C).

### W2: Four studies in one manuscript dilute the contribution
**Severity**: MAJOR
**Problem**: Sec. V (forecasting, physics-informed training, cost, distillation; about 2.5 pages) ends in a null effect on the controller (Sec. VI-C); Sec. VIII (speed planning) is fully simulated, not ported, and uses a traffic corridor around one recorded drive (Fig. 12); Sec. VII mixes a measured Kalman result with simulated reviewers and a simulated fused estimator. The abstract interleaves MEASURED and SIMULATED results within one paragraph, and the four contributions in Sec. I include a forecaster accuracy-versus-cost comparison whose outcome is "changed nothing".
**Why it matters**: IEEE Access reviewers can accept breadth, but here breadth blurs which result carries the paper and pushes length to 18 pages with repeated headline numbers.
**Suggestion**: Keep Sec. III, IV, VI and the measured part of VII as the core. Compress Sec. V to the pieces that explain the Sec. VI ablation (G4/G5, latency estimate versus measurement). Move Sec. VIII and the fused estimator to future work or a companion paper. Separate measured and simulated results in the abstract.

### W3: "Pre-registered" in the title is stronger than the record shown
**Severity**: MAJOR
**Problem**: Sec. III-C says gates were "written ... before the experiment each one governs", but the manuscript gives no registry, timestamp or version-control reference. It records one revised criterion (G2 split into three parts, Sec. IV-C), an exclusion of two delay settings by a rule "fixed after these runs were seen" (Sec. VI-D), and a second detector built after the first failed on logged trips (Sec. VII-C, D). The abstract mentions only the single revised criterion.
**Why it matters**: A reader weighing the pre-registration claim needs the deviations in one place. As written the claim reads as more than the evidence shows, and the title carries it.
**Suggestion**: Add a table of every deviation from the pre-specified plan (what, when, why, effect on the verdict), cite commit hashes or dated files that fix each gate, and either keep "pre-registered" with that support or use "pre-specified".

### W4: Positive results in the abstract lean on simulated drift and a weak comparator
**Severity**: MAJOR
**Problem**: The bias-aware detector's "120 of 120 ... no false alarm in one hour" (abstract, Table 7) is measured on the target but on software-injected faults and a simulated drift; Sec. VII-C shows the first detector failing on 70 logged trips (flagged 99% of the time, standing gap about 0.22 m/s), and no logged-trip result is given for the bias-aware version. The detector also missed the registered criteria in simulation (551 and 533 of 560, Sec. VII-D), a point absent from the abstract. One clean hour is short against the earlier detector's one false alarm in 1.26 h. The Kalman result (9.44 to 0.24 Wh/km at 10x noise, Table 6) is compared with the baseline loop acting on the raw reading; no simple low-pass or alpha-beta filter comparator is reported.
**Why it matters**: These are presented as the usable outcomes of the study ("the gains came from estimation instead"). A Kalman filter beating an unfiltered reading is expected and adds little; a detector validated only on the failure mode it was designed against may not transfer.
**Suggestion**: Add a low-pass filter baseline to Table 6; run the bias-aware detector on the 70 logged trips or say plainly in the abstract that it was not; give a false-alarm exposure large enough to support a rate; list the unmet detector criteria in the abstract's failure sentence.

### W5: Reproducibility affordances and readership relevance are incomplete
**Severity**: MINOR
**Problem**: No code, data or firmware availability statement was found in the manuscript, although the testbed is listed as the first contribution (Sec. I). The PIL host is a non-real-time laptop with 8.8 dropped frames per run and a failed frame criterion (Sec. III-D). The target is an ESP32-S3 development board running an Arduino core with unused radio stacks (Sec. III-B), and the paper does not relate its budgets (20 ms compute, 300 KB, 40 ms inference) to an automotive-class controller. References total 33, concentrated on hybrid-vehicle RL; battery-EV thermal/cabin energy management and eco-driving or model-predictive speed planning (relevant to Sec. VIII) are thinly covered.
**Why it matters**: IEEE Access emphasises reproducibility, and a testbed contribution without a release is hard to credit. Automotive readers will ask whether the 36 ms and 29.82 MMAC/s figures carry to production hardware.
**Suggestion**: Add a data and code availability statement; state what in the testbed is released; add a short paragraph mapping the budgets to an automotive-class MCU; widen the battery-EV and planning references.

## Detailed Comments

### Title & Abstract
The title is long and over-promises on scope (W1, W3). The abstract is dense and honest about the main negative result, but mixes measured and simulated numbers, quotes the vendor-build latency (36.46 ms) although the shipped image is the Arduino build (35.03 ms, Sec. III-B), and omits the unmet detector criteria and the software-injected nature of faults.

### Introduction
The framing as a follow-up to one prior study [4] (Sec. I, paragraphs 2 and 3) narrows the apparent audience. The three questions are clear and are answered in the conclusion. The introduction states the contributions as four items; only the first two are tied to the title.

### Literature Review
Table 1 is a useful positioning device, filled only where sources state the point. The related work is solid on hybrid RL and embedded inference but thin on battery-EV energy management. See W5.

### Methodology / Research Design
Detailed statistics are for the methodology reviewer. From a design-fit standpoint, the gate structure, the compile-time arm selection and the parity tests are good practice. The plant validation (Sec. IV-C, G2 fail at B08, winter-only envelope) limits what any comparison on it can claim, as the authors say.

### Results / Findings
Table 5 and Fig. 7 present the central comparison clearly. Table 2 lacks a G5 verdict. Fig. 4 and Fig. 2 are effective. Fig. 5 labels are crowded.

### Discussion
Sec. IX-A (why the rules held) is the strongest part of the manuscript and should move forward. Sec. IX-B ("what the method caught") is a valuable list of four findings and supports the artefact-audit framing.

### Conclusion
Largely matches the evidence and states the limits; the closing recommendation (a physical accelerometer) follows from the simulated-drift limitation. The conclusion should also name the one-policy limitation, which currently sits only in Sec. IX-C.

### References
33 entries with DOIs where available. Entries [12], [15] and [33] lack dates or links; [3] and [4] are recent and fit the stated starting point.

## Questions for Authors

1. Table 5 holds 16 rows, but six (Mixed, No delay, Flat, SOC 0.85, Noise 1x, Driver 1.0) coincide with the US06 baseline setting, with rule-arm energy from 190.73 to 191.41 Wh/km. Are these seeded replicates of one condition (Sec. III-E)? If so, the independent conditions number about 11, not 16, and "1 of 16" should be restated.
2. What ambient temperature and auxiliary load were used in the UDDS, HWFET and US06 campaigns, given the plant is validated on winter trips only (Sec. IV-A)? Does the headroom bound hold at other temperatures?
3. What evidence (dated files, commit hashes) shows each gate predates its experiment, and can all deviations be tabulated (W3)?
4. How does the Kalman estimator compare with a simple low-pass filter in the same loop, and has the bias-aware detector been run on the 70 logged trips?
5. Could a second learning algorithm, or a policy given a larger action space (for example a speed-reference correction), be tested to show whether the null result is tied to the three-scalar action design?

## Minor Issues

### Language / Grammar
- The abstract and Sec. I repeat "1 of 16 settings, 0.94% more" in near-identical wording; cut one.

### Citation Format
- Refs [12], [15], [33] need dates or retrieval links.

### Figures and Tables
- Table 2: add a verdict for G5 (text says "not closed in full", Sec. V-D).
- Table 5: define "Mixed"; mark which rows are baseline-valued replicates.
- Fig. 5: crowded callouts; consider a table inset.
- State the numeric sensor-noise floor in the main text (Sec. VI-D and Fig. 9 refer to "a stated floor").
- Abstract: "36 runs" includes the two excluded delay cells.

### Layout
- 18 pages with repeated headline numbers; see W2.

## Dimension Scores (rubric, 0-100)

| Dimension | Score | Descriptor | Notes |
|---|---|---|---|
| Originality (20%) | 58 | Weak/Adequate boundary | One original audit result; other components are standard (novelty 5/10) |
| Methodological Rigor (25%) | 68 | Adequate | Transparent gates and timing; one-run cells, single learned policy |
| Evidence Sufficiency (25%) | 62 | Adequate | Main claim supported; positive claims rest on simulated faults; 33 references |
| Argument Coherence (15%) | 62 | Adequate | Core claim holds; title, abstract and gate narrative overreach (W1, W3) |
| Writing Quality (15%) | 70 | Adequate | Plain and specific; repetitive and long |
| **Weighted Average** | **64.6** | **Major/Minor boundary** | Contract rule F2 selects Major Revision |

## Editorial Decision

Action: editorial_decision=major_revision (F2, severity 70, is the highest fired condition; F1 and F3 did not fire).

Recommendation: Major Revision, confidence 4.

Required revisions: reframe the title and abstract around the headroom bound and the artefact audit (W1); cut or relocate Sec. V detail and Sec. VIII (W2); document the pre-specification record and every deviation (W3); add a simple-filter comparator and logged-trip detector evidence, and align the abstract's positive claims with their simulated basis (W4); add an availability statement and relate budgets to an automotive-class controller (W5).
