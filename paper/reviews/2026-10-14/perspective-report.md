## Dimension Scores

### D1: methodology_rigor
score: warn
Justification: The design is strong in places. Gates were fixed before the experiments and the one revision (G2, Section III.C and IV.C) is disclosed. Provenance, a firmware-versus-NumPy parity test (2.12e-06, Section III.E), a compile-time controller switch confirmed by a diagnostic counter (Section III.B), and a plant-artefact audit (Section IV.E) are all stated. Deployment cost accompanies the accuracy results (0.121 ms, 19.3 KB for the policy, Section VI.B; Table 4 for forecasters). The warn comes from four gaps. (1) Table 5 and Table 6 are one run per cell per controller, and the text says "no interval is attached" to the 16-setting average (Section VI.D); the only noise yardstick is a 0.16% spread between two rule-arm campaigns. (2) The headline fault-detection result (Table 7, 120 of 120) is three noise draws over the same registered cases, so the 24 runs per fault type are not independent trials, and the clean-driving false-alarm evidence is one hour (Section VII.D). (3) The manuscript has no code, data or checkpoint availability statement, although reproducibility is a stated aim. (4) The simulator, not the board, supplies every fault and every plant response, and its own validation failed one gate (G2, trip B08 at 2.45 pp against 2.00 pp) and has no real-vehicle check. No single item invalidates the study, so the dimension is not a block.

### D2: domain_accuracy
score: pass
Justification: PIL is correctly distinguished from HIL (Section III.A, IX.C), and every result is labelled measured or simulated (Section III opening; Tables 5-7, Figs. 7-9, 11). The rule baseline is not a strawman: it is compared with a dynamic-programming optimum on four cycles and sits within 0.01% to 0.16% of it (Section IX.A), which is the right evidence that a weakly tuned baseline is not driving the verdict, and it answers the Henderson et al. [10] concern the authors cite. Energy is ranked on a comparable scale with shed heat charged back (Section VI.A). Related work (Table 1, Section II) is limited to cells "the source states", which is a fair rule. Minor gaps (no cited work on specification gaming, no automotive embedded-ML deployment studies) are covered under D4 and in Minor Issues.

### D3: argumentative_coherence
score: pass
Justification: Abstract, Section VI, Section IX and Section X give the same verdict (1 of 16 settings, +0.94%, 8.28% gain withdrawn). Claims are limited by explicit scope sentences ("these statements hold for this vehicle model, these four cycles and this class of processor, and no further", Section IX.A). The artefact mechanism was tested (fixed-ceiling sweep with no controller, Fig. 4) rather than only inferred, and the earlier "peak shaving" explanation is retracted as wrong (Section IV.E). The reversed rule-monitor result is reported honestly (Section VII.E, IX.B). Two softer points are listed as W3 and W4: the abstract's 120 of 120 sits next to a detector that did not meet its own registered simulated criteria (Section VII.D), and the 0.94% mean is driven by two settings (Table 5).

### D4: cross_disciplinary_relevance
score: warn
Justification: The paper is unusually readable to an outsider on the core lesson (a simulator fault produced an 8.28% "win"), and Section IX.B says what the method caught. The warn is for three omissions that matter to an automotive-safety reader and an ML-reproducibility reader. (1) The speed-sensor fault detector, link-outage handling ("The handling is there for safety", Section VI.F) and watchdog (Section III.B) use safety vocabulary, but nowhere does the manuscript state that no safety case, hazard analysis or integrity level is claimed, or what fault model a 0.5 s detection window addresses. (2) The artefact is a textbook case of a learner exploiting a specification gap, yet specification gaming, reward hacking and sim-to-real are not named or cited beyond [10] and [11], so the wider-ML reader is not told the lesson transfers. (3) Transfer of the ESP32-S3 timing figures (Table 2, Fig. 2; 25 microsecond jitter on a general-purpose-OS host) to automotive-grade microcontrollers is not discussed. Not a block: no unsupported safety claim is made, and the limitations paragraph (Section IX.C) is candid.

### D5: writing_and_structure
score: pass
Justification: Structure follows IEEE Access conventions, the gates table (Table 2) is scannable, the measured/simulated label appears in captions, and the figures carry units, log axes and stated run counts (Figs. 2, 4, 7, 8, 9). Weak spots are minor: project vocabulary such as "arm", "cell", "settings" and "valid set" is used before definition for a non-specialist; the "Mixed" row of Table 5 is not defined in the text; Section VI.D packs the campaign design into one dense paragraph; Table 1 mixes a "not stated" convention that a reader must infer.

## Failure Condition Checks

### F1
fired: false
No mandatory dimension (D1, D2, D3) scored block.

### F2
fired: false
Only one mandatory dimension (D1) scored warn; two or more are required.

### F3
fired: false
The only high-priority dimension (D4) scored warn, not block.

### F0
fired: false
D1 scored warn, so not every mandatory dimension scored pass. Accept is not triggered.

## Review Body

# Peer Review Report

## Manuscript Information
- Title: Learned Versus Rule-Based Energy Management for Electric Vehicles on a Microcontroller: A Processor-in-the-Loop Study With Pre-Registered Acceptance Gates
- Manuscript ID: not provided (mock manuscript)
- Review Date: 2026-10-14
- Review Round: Round 1

## Reviewer Information

### Reviewer Role
Peer Reviewer 3 (Perspective)

### Reviewer Identity
Embedded-systems and TinyML engineer with an automotive functional-safety background (ISO 26262, SOTIF) and an interest in ML reproducibility (sim-to-real gaps, specification gaming, benchmark artefacts). I am an outsider to hybrid-vehicle energy-management theory and may miss conventions of that field.

### Review Focus
What the results mean for practitioners who deploy learned controllers on cheap microcontrollers, what the fault-detection results do and do not support for a safety argument, and what the wider ML community can take from a simulator artefact and a negative result.

## Overall Assessment

### Recommendation
Minor Revision (borderline Major Revision on the safety framing and the uncertainty reporting).

### Confidence Score
4

### Summary Assessment
The paper compares a hand-written rule-based energy manager with a Soft Actor-Critic policy on an ESP32-S3 in a processor-in-the-loop setup at 100 Hz, using acceptance gates fixed before each experiment. Its main finding is negative: after a fault in the vehicle model is corrected, the learned policy beats the rules in 1 of 16 settings and uses 0.94% more energy on average (Table 5). The 8.28% gain seen earlier is traced to a power limit that capped billed energy without reducing torque (Section IV.E, Fig. 4) and is withdrawn. A two-state Kalman speed estimator and a bias-aware detector are the positive results. From my angle this is a useful and unusually honest paper. Its value to practitioners is a worked example of an audit that caught a simulator artefact, plus on-device cost figures next to accuracy. Its main weaknesses are single-run cells without intervals in the main comparison, a headline fault-detection figure that rests on one fault model and one clean hour, and safety vocabulary that is not bounded by a statement of scope. I recommend minor revision, because the fixes are text and reporting changes, not new experiments, except for the interval work in W1.

## Strengths

### S1: A simulator artefact is found, explained by measurement, and withdrawn in print
Section IV.E and Fig. 4 show that a 5 kW ceiling billed 8.05 Wh/km over the full 12.888 km before the fix and 156.15 Wh/km over 4.453 km after, and that a fixed-ceiling sweep with no controller in the loop reproduced the effect. The authors also say that their first explanation (peak shaving) "was wrong". This is the clearest lesson in the paper for ML readers, and the three "oddities" that triggered the search (learner below the offline optimum; gain grows with demand; gain vanishes on UDDS and HWFET) are a reusable checklist.

### S2: Strong baseline control and a ceiling argument
Section IX.A shows an offline dynamic-programming optimum within 0.01% to 0.16% of the rules on four cycles (e.g. 190.47 against 190.39 Wh/km on US06). This explains why the learned policy has "at most 0.16% to gain" and makes the negative result informative rather than a statement about a weak baseline.

### S3: Cost is reported next to accuracy and the estimate-versus-measurement gap is shown
Table 4 and Section V.D report that the Transformer latency estimate (22.28 ms) was 64% below the measured 36.46 ms, with the softmax and layer-normalisation cost identified. Table 2 (G5) and the policy figures (0.121 ms, 19.3 KB, worst 0.84 ms) let a firmware engineer judge feasibility. Reporting that G5 "is not closed in full" because the converted model was not run on target is the right level of candour.

### S4: Measured and simulated claims are separated throughout
Every table and figure caption carries the label, and Section IX.C states that the setup is PIL, "so nothing here is a hardware-in-the-loop result". The abstract also reports which gates fail (G2, G3) and that the earlier detector was "not usable as tuned" (Section VII.C).

### S5: Provenance and parity testing
Section III.E (seed policy, parity test, weight checksum) and III.B (the diagnostic counter that confirms which controller ran) address the commonest silent failure in comparison studies, where the arm labelled "learned" is not the arm that ran.

## Weaknesses

### W1: The central comparison has no uncertainty on the 16 settings
Severity: MAJOR
Location: Section VI.D, Table 5, Fig. 7; abstract ("0.94% more on average").
Problem: Each cell is one run per controller with a fixed noise seed (Table 5 caption: "one run per cell per controller"), and the text states "no interval is attached to their average". The only calibration of run-to-run spread is 0.16% from two identical rule-arm campaigns (Section IV.E), and the policy-seed spread of 0.51 and 0.82 Wh/km (Section VI.B) was measured on HWFET in simulation, not on the 16 target settings. The mean of 0.94% is driven by two settings (+5.71% downhill, +4.45% at 10x noise); the other 13 lie between 0.03% and 0.82%.
Why it matters: With one deployed seed and one run per cell, a reader cannot tell whether "1 of 16" would be 0, 1 or 3 on a repeat. Readers outside the field will take the headline as a population statement.
Suggestion: Report the median (about 0.3%) beside the mean, and add a paired interval over settings. Better, repeat the 16 cells with the five trained seeds or with several noise seeds (Section III.E notes repeat offsets exist) and report the share of repeats in which each cell flips sign. If the board time is not available, state that the 1 of 16 is a single draw and word the abstract accordingly.

### W2: Safety-related wording is not bounded by a statement of scope
Severity: MAJOR
Location: Section VI.F ("The handling is there for safety"); Section VII (detector, fused fallback); Section III.B (watchdog); abstract and Section X ("caught 120 of 120 ... no false alarm").
Problem: The paper describes a stale-command ramp to zero after 50 ms, a sensor-fault detector with a 0.5 s window, and a fallback speed. None of this is placed in a safety frame. There is no statement that no safety case, hazard analysis, integrity level or fault-injection campaign on a real vehicle is claimed; no discussion of what failure of the detector itself would do; and no mention that the learned policy runs inside a rule-based envelope or what happens if its output is out of range. The outage results in Fig. 8 (worst speed error 13.3 m/s at 10 s with the handling on; crossover at 4 to 5 s) show the fallback is not monotonic in benefit, which a safety reader will want discussed.
Why it matters: Readers from automotive safety will otherwise read the words "for safety" and "caught 120 of 120" as a dependability claim. The paper does not intend one, so the fix is cheap.
Suggestion: Add a short paragraph in Section IX.C stating that the detector and fallback are research prototypes with no claim of ISO 26262 or SOTIF compliance, listing the assumed fault model (single speed-sensor channel, injected in software), and stating the open items (detector self-monitoring, behaviour when the accelerometer is also faulty, the 4-to-5 s crossover). A one-sentence statement of how the learned policy would be bounded in a deployed system (output clamping by the rule layer, as the watchdog and ramp suggest) would also help.

### W3: The 120 of 120 result is presented more strongly than its basis allows
Severity: MAJOR
Location: Abstract; Table 7; Section VII.D; Section X.
Problem: (a) The 120 faults are 5 fault types times 8 onsets times 3 noise seeds on the same registered cases (Table 7 caption), so they are repeats of 40 fault events, not 120 independent ones. (b) The false-alarm evidence is "one hour of clean driving", whereas the earlier detector produced one alarm in 1.26 h (Section VII.C); zero in 1 h therefore does not distinguish the two rates with any confidence. (c) In simulation the bias-aware detector "does not pass the registered criteria" on validation and test (551 and 533 of 560; 9 late detections and 27 late detections, Section VII.D), and the abstract does not say so, although it lists G2 and G3 as the failed gates. (d) The detector's reference is tuned on a logged-acceleration drift (0.11 m/s^2) that was itself the reason the first detector failed on 70 logged trips (Section VII.C); the manuscript does not report the bias-aware detector's false-alarm share on those same 70 logged trips.
Why it matters: This is the result most likely to be quoted by a practitioner, and the abstract wording sits between a demonstrated result and a registered pass.
Suggestion: In the abstract and Section X say "40 injected fault events, repeated over three noise draws" and add an interval (for example, an upper bound on the miss rate over 40 events and a false-alarm rate bound over the clean hours). State that the registered criteria were not met in simulation. Report the bias-aware detector on the 70 logged no-fault trips, which are the only real-acceleration data you have; if that was done, point to it; if not, say so in Section IX.C.

### W4: The ML-reproducibility lesson is left implicit and the literature that frames it is not cited
Severity: MINOR
Location: Section II.B, II.C, IX.B.
Problem: Section IX.B lists "four findings" caught by the method, and Section IV.E documents a learner exploiting a gap in the simulator specification. The manuscript does not connect this to the specification-gaming and sim-to-real literature (for example, the catalogue of specification-gaming examples maintained by Krakovna et al., and the sim-to-real transfer survey literature in robotics). Only Henderson et al. [10] and Dulac-Arnold et al. [11] are cited on this theme.
Why it matters: The most transferable result of the paper is not about EV energy management; it is that an agent finding a surprisingly good result is a signal to audit the plant. Naming it would let ML readers find the paper.
Suggestion: Add two or three sentences in Section IX.B and two references on specification gaming and sim-to-real. State the generic test that would have caught the fault early: "the learner must not beat the offline optimum on a cycle where the optimum is computed with the same plant" (you already compute this in IX.A).

### W5: Transfer of the timing and cost results beyond a single hobby-class board is not discussed
Severity: MINOR
Location: Section III.B, III.D, Fig. 2, IX.C.
Problem: The 25 microsecond 99th-percentile jitter and zero late steps are measured on an ESP32-S3 on the Arduino core, with radio stacks present but not started and supply current "not re-measured on this image". The dropped frames (8.8 per run, 95% interval 6.4 to 11.8) are attributed to the host's general-purpose operating system. Limitations (IX.C) lists one board but not the gap between this board and automotive-grade, lockstep or ASIL-capable microcontrollers.
Why it matters: Practitioners will want to know which claims port (integer MACs per second, memory footprint) and which do not (jitter under a real-time OS with other bus traffic, interrupt load from CAN).
Suggestion: Add two sentences to Section IX.C listing what is expected to transfer (operation counts, weight memory) and what is not (jitter, flash and cache behaviour, interrupt load), and say that a pass of G3's timing part on a bare-metal host link would be a stronger test than a non-real-time host.

## Detailed Comments

### Title & Abstract
The title is accurate and the abstract is quantitative. The abstract is long and packs eight numeric results; reorder so that the headline negative result and the two failed gates come first (they do) and cut one secondary item (the Transformer 36.46 ms detail). Qualify 120 of 120 as in W3.

### Introduction
The motivation is clear and the three questions inherited from [4] are explicit. Phrases such as "baseline that has not been left weak" are well supported later. The contributions list (four bullets) matches the sections.

### Literature Review / Theoretical Framework
Table 1 is a good device because cells are filled only where the source states the point. A reader outside the field would benefit from one added sentence on why PIL is an earlier, cheaper step than HIL and what it cannot show. See W4 for missing literature on specification gaming.

### Methodology / Research Design
The gate concept is the paper's main methodological contribution; it would help to say who fixed the gates and where the record sits (a dated file, repository tag), since "pre-registered" is a strong word for a single-author mock manuscript. Section III.C says G2 was revised once, with original thresholds kept and one new threshold added, which is the right disclosure. See W1 for interval reporting.

### Results / Findings
Table 5 and Fig. 7 are clear. The "Mixed" row of Table 5 is not defined in the text. Fig. 7(b) shows that the learned policy tracks speed 5 to 60 times worse on RMSE on US06 (0.17 to 0.50 m/s against 0.010 to 0.098 m/s); the text notes this but the abstract only says "worse on the aggressive US06 cycle". A practitioner would care that this is a comfort and drivability cost, and a short remark would help.

### Discussion
Section IX.A (why the rules held) is persuasive. Section IX.B correctly lists what the method caught. The statement "classical estimation and hand-written rules survived measurement" (Section X) is fair for these conditions but it rests on one vehicle model and one SAC design (acknowledged in IX.C).

### Conclusion
Calibrated, and the next step (a physical accelerometer) follows from the evidence. The statement of two positive results should carry the W3 qualification.

### References
33 references, mostly journal and conference items with DOIs. Reference [15] and [12] are web resources without access dates. No specification-gaming reference.

## Questions for Authors

1. Table 5 is one run per cell. How many of the 16 cells keep the same sign of the difference if the noise seed, or the trained seed, is changed? If you have not run this, what do the seed spreads of Section VI.B (0.51 and 0.82 Wh/km on HWFET) imply for cells whose difference is below 0.6%?
2. For the bias-aware detector, what is the false-alarm share on the 70 logged no-fault trips that broke the first detector (Section VII.C), given its bias state learned with a 2 s time constant?
3. What would a safe-deployment envelope around the SAC policy look like in your design, that is, what is the output range clamp and which layer enforces it if the inference task stalls? Does the stale-step ramp in Section VI.F apply to the policy as well as to the host link?
4. Is the 10x sensor-noise level tied to a real wheel-speed sensor specification or to the logged data? If it is arbitrary, how should a reader weigh the 9.44 to 0.24 Wh/km result?

## Minor Issues

### Language / Grammar
- Section III opening and Table 1 caption use "measured" and "simulated" as labels; keep one style (italic or small caps) so that a reader scanning the tables sees them at once.
- "Arm", "cell", "setting" and "valid set" appear before definition (Section III.E, VI.C). Define in one sentence at first use.
- Section V.D: "The measurement was 64% above the estimate" and Section IX.B "Measured latency was 64% above the estimate" are consistent; elsewhere the abstract says 36.46 ms of a 40 ms budget. Consider stating the budget fraction (91%) in the abstract.

### Citation Format
- [12] and [15] lack access dates. [31] is the 2014 EMNLP paper for GRU; fine. Add specification-gaming and sim-to-real references (W4).

### Figures and Tables
- Table 5: define the "Mixed" setting; consider adding a column of the sign test or the interval once W1 is addressed.
- Fig. 2: log-scale counts with empty bins marked "0" are clear; add the number of loops above the tolerance in the caption (it is zero) to match the text.
- Fig. 8: the crossover shading at 4 to 5 s is helpful; note on the figure that no point was measured inside it (the text says so).
- Fig. 9 and Table 6: the second-seed row for US06 floor (190.98) is the floor used for the 9.44 Wh/km loss; make this explicit in the Table 6 caption to avoid confusion with the 190.79 row.

### Layout
- Page 11 has a large blank area between the text and Table 5; move the table up or fill with Fig. 7.
- Section VI.D is a single dense paragraph; split design and exclusion rules.

## Dimension Scores (optional rubric view)

| Dimension | Score (0-100) | Descriptor | Notes |
|-----------|--------------|------------|-------|
| Originality (20%) | 66 | Adequate | Confirmatory and negative result with a documented artefact; contribution is the method and audit more than the algorithm |
| Methodological Rigor (25%) | 68 | Adequate | Gates, parity, provenance strong; single-run cells, no intervals on main table (W1) |
| Evidence Sufficiency (25%) | 70 | Adequate | 33 references; claims mostly supported; fault-detection basis narrow (W3) |
| Argument Coherence (15%) | 80 | Strong | Consistent verdict across abstract, results and conclusion |
| Writing Quality (15%) | 78 | Strong | Clear and candid; some undefined project terms |
| Significance & Impact (R3 optional) | 70 | Adequate | Useful to practitioners and ML readers; transfer beyond one board and one plant not shown |
| **Weighted Average** | 71 | **Minor Revision** | (66x0.20)+(68x0.25)+(70x0.25)+(80x0.15)+(78x0.15) = 71.0 |

## Editorial Decision

No failure condition fired on my scores (F1 false, F2 false, F3 false, F0 false because D1 scored warn). By the contract's precedence rule there is therefore no action to apply from my scores alone. My recommendation is Minor Revision (weighted average 71, rubric band 65-79), with the W1 to W3 items marked as required before the abstract wording is final, and with confidence 4 of 5.
