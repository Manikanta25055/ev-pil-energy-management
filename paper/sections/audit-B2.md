# Audit B2: Sections VI to IX, references, cross-section consistency

Sources opened: docs/forecast-deploy-cost.csv, forecast-ladder.json/.md, forecast-guards.md, g5-latency.md, g5-arduino.json, transformer-a1.md, a2-quantisation.json, a2-distillation.md, week12-speed-arms(.json/.md), week12-fault-arms-b6.json, week12-accel-channel-check.json, week12-b6-alarm-replay.json, week13-estimator-and-board.md, week13-sensor-architectures.md, week13-b7-pil(.json, -b6.json), week14-b7-pil-repeats.json, week14-fused-backup-traffic-repeats.md, week13-energy-planner.json, week14-corridor-planner.json, week11-a4-{on,off}-*s.json, models/reviewer/*.json, scripts/train_reviewer.py, src/evpil/control/speed_estimators.py. Previous audit-B corrections were checked for regression: none regressed (outage order, 13 vs 14 settings, A3 value, 3 stalls vs 8.8, reviewer ranges, 64% wording, all hold).

## Findings

| Location | Text | Issue | Source checked | Action |
|---|---|---|---|---|
| 06 Where/Kalman, para after Table | "At the noise floor the arms agree within 0.1%" | Table includes the second US06 floor seed: 190.98 vs 190.56 is 0.22%. The 0.1% holds only for the three cycles. | week12-speed-arms.md Sec 2 (0.10% is first-seed cells) | fixed: "within 0.1% on the three cycles and within 0.22% on the second US06 seed" |
| 06 same para | "estimator's residual loss lies within run-to-run spread" | Residual 0.24 Wh/km exceeds the 0.19 spread of the baseline's two floor runs; "within" is not literally true | week12-speed-arms.json rows | fixed: "is about the size of run-to-run spread" |
| 01-refs skalse2022 | title "Defining and characterizing reward hacking" | NeurIPS proceedings title is "Defining and Characterizing Reward Gaming" (arXiv title says Hacking) | proceedings.neurips.cc abstract page | fixed (title). Related-work wording "reward hacking" is for Amodei and the concept; sentence about Skalse remains correct |
| 01-refs wegener2021 | doi empty, "confirmed from a reference list" | DOI 10.1016/j.trc.2021.102967 resolves (302) to an Elsevier Transportation Research Part C record (PII S0968090X2100005X); several independent reference lists give the same authors, title, vol 126, article 102967 | doi.org, web search | fixed: DOI and URL added. Abstract itself not read; see decision 1 |
| 02 Table platform-gates, G5 "Pass" | Section VI says "Gate G5 is not closed in full" | Mild internal tension; g5-latency.md says neither half is the full gate | g5-latency.md Verdict | reported |
| 02 Table platform-gates, rows "A1, A3" | internal ablation codes in paper text | Brief says describe by content | BRIEF Sec 4 | reported |
| 04 Learned policy, Table ems-hyper | "deployed actor", "Actor and critic hidden layers" | "actor" is the RL network term here; brief maps actor to learned policy | BRIEF Sec 4 | reported (acceptable as technical term, lead to decide) |
| 05 | "Every fitted model passes G4, by at least 14.5%" | G4 bar is 10%; gain is at least 14.5% (minimum 14.45%) | forecast-ladder.json skill 0.1445 | reported (wording could read "with a gain of at least 14.5%") |
| 07 Planning table | Student 0.03 / 0.3 | Open point settled: 0.000282 = 0.03% on US06; HWFET 0.31%. Old "0.0" was rounding | week13-energy-planner.json | OK |
| 06 / 07 | rule monitor 0.61 vs 0.67 first run, 1.32 vs 0.83 over three draws, three alarms | Sections agree and match data | week14-b7-pil-repeats.json | OK |
| 06 / 02 | first detector false alarm | 1 on a healthy sensor in 1.26 h on target (Section III table, Section VII, Section II-style claim all match). 162 false alarms is a different run: wander channel, one clean cycle (the other clean cycle had 0) | week12-speed-arms.md Sec 6; week13-b7-pil-b6.json | OK |

## Numbers traced (all OK unless listed above)

Section VI (forecast): 30 samples/3.0 s/10 Hz, 32 samples, 55,125 and 29,252 windows, 19 and 7 trips; R2 0.4018 and -0.0044, 257 parameters; 13.219 kW, 11.897 kW; 11.308, 11.290, 11.120, 11.029 kW; 14.5, 14.6, 15.9, 16.6 %; sizes 7.5, 20.4, 17.9, 3,658 KB; 0.26 ms est, 0.6%; 35.07 and 36.46 ms, 88 and 91 %, 35.03 ms (Arduino), 19.84 and 22.28 ms est; 87% and 1.2% (derived 87.3, 1.16); XGBoost 12x memory (12.19); seed spread 0.038 to 0.174; 64%, 7.89 of 14.18 ms; 11.051 to 11.156 kW, 0.95% (recomputed 0.947), 71.7 to 20.2 KB, 3.56x; 28,894 B, 9.4%; physics loss 11.057 vs 11.052, 24.5 to 2.5%; distillation 0.20% and 0.89%, sign flips. Labels correct.

Section VII (estimation): all six noise-table cells and currents, 9.44 (4.9%), 0.24, 9.63/0.19, 0.19 spread, 62/69 us, 74 us, 0.0193 vs 0.0104, 0.011; 160 of 160, 0.21 s, 3.8 h, 1.26 h, 0.018 m/s; 70 trips, 30 h, 0.11, 0.22, 0.036, 99%; 551/533 of 560, 4.5 h and 5.8 h, nine late, 27 late; fault table (7/7/6/6/7 of 8; 24 each; worst 0.62, 0.65, 0.83, 0.72, 0.66; 33/40, 40/40, 120/120); 0.32 s; 162 false alarms; 47 of 120; 540,960 blocks, 99/88/94/1%; 1,508 and 550 parameters, 16 hidden, AdamW 3e-3; 3.7 to 1.2, 5.1 to 1.4; 9.7, 10.8, 3.0, 12.8; 70 to 1000 ms; fused 0.62 vs 3.74, 2.59, six of seven, two stuck. Rule of three (3 per hour) consistent with 1.00 clean hour.

Section VIII (planning): all 10 table cells (10.4/1.2, 9.5/0.8, 10.4/1.1, 0.03/0.3), corridor 5.1% (25 m), 9.7% (100 m), 12.6% (200 m, 12.55), HWFET -0.1 to 1.7, 0.19 s and 323 replans (week13-energy-planning.md L103), 1% arrival tolerance, 10 m steps. SIMULATED labels correct.

Section IX and X: 0.01% to 0.16%; 11 of 12; 22.28 to 36.46 ms (64%); 19.3 KB; 28,894 B; 29.82 M MAC/s; 25 us; 8.8 dropped frames; outage values 3.73/6.67 (4 s, off lower), 7.40/7.97 (5 s), 13.3/18.2 (10 s) match week11-a4 files in direction and value; 2.2x, 0.45 pp, 2.45 vs 2.00, 13.4 to 16.9%; r = -0.03; 0.17 to 0.50, 0.004 and 0.016; 8.28%, 14 of 16, 1 of 16, 0.94%, 9.44 to 0.24, 120 of 120.

## Cross-section consistency (01 to 07 and abstract)

Same value and label everywhere: 8.28% and 14 of 16 (abstract, I, III, V, IX, X); 21.6%; 1 of 16 and +0.94% (I, V, X; abstract uses the 11 of 12 framing, median 0.31%, interval 0.17 to 0.76, both consistent with V); 12 distinct conditions (II, V, IX); 0.01% to 0.16% (I, V, IX, X, abstract); 9.44 and 0.24 (I, III table, VII, X, abstract); 120 of 120 (III, VII, X); 551 and 533 of 560 (III, VII); 36.46 ms, 22.28 ms, 64% (II, VI, IX, abstract); 36 runs, 32 valid, 2,282,832 steps (II, IV, V); 0.121 ms and 19.3 KB (II 0.123 ms is the Arduino build, stated); planner 10.4%, 5% to 10% (I-level claim, VIII, IX, X); first-detector false alarm (III, VII). No contradictions found. "Pre-registered" does not appear; "fixed before each experiment" is used and Section III states the dated exceptions. No first person, no em or en dashes, no week numbers or Jev/Codex/Claude in paper text. Internal codes present: "A1, A3" (Section III table) only.

## References

44 keys in 01-refs.json (43) and 05-refs.json (2) with one overlap check: no duplicates; every [@key] in sections 01 to 07 is defined; no entry unused.

| Key | Authors, title, venue, year | Result | Action |
|---|---|---|---|
| sciarretta2015 | Sciarretta, De Nunzio, Ojeda; Optimal ecodriving control; IEEE CSM 35(5) 71-90, 2015; doi 10.1109/MCS.2015.2449688 | Confirmed (reference lists, HAL DOI record). Claim in text (optimal control framing, survey) matches title | none |
| liu2017 | Liu, Hu, Li, Cao; IEEE/ASME TMech 22(4) 1497-1507, Aug 2017; doi 10.1109/TMECH.2017.2707338 | Confirmed (Cranfield repository, CORDIS). Text claim (velocity prediction plus RL, DP comparison, HIL check) matches the abstract | none |
| agarwal2021 | Agarwal et al.; NeurIPS 34, 2021; arXiv 2108.13264 | Authors, title, venue confirmed. Pages 29304-29320 not confirmed by any source found | left blank |
| amodei2016 | Amodei, Olah, Steinhardt, Christiano, Schulman, Mane; arXiv 1606.06565, June 2016 | Confirmed. Reward hacking is one of its five problems | none |
| skalse2022 | Skalse, Howe, Krasheninnikov, Krueger; NeurIPS 35, 2022 | Confirmed; proceedings title is "Reward Gaming" (DOI 10.52202/068431-0687); pages not found | title fixed |
| lehman2020 | Lehman, Clune, Misevic et al.; Artificial Life 26(2) 274-306, 2020; doi 10.1162/artl_a_00319 | Confirmed; content matches the sentence | none |
| tobin2017 | Tobin et al.; IROS 2017; doi 10.1109/IROS.2017.8202133 | Title, authors, IEEE Xplore document 8202133 confirmed; pages (23-30) not confirmed and the entry has none | none |
| zhao2020 | Zhao, Queralta, Westerlund; IEEE SSCI 2020, 737-744; doi 10.1109/SSCI47803.2020.9308468 | Confirmed | none |
| wegener2021 | Wegener, Koch, Eisenbarth, Andert; Transp. Res. Part C 126, 102967, 2021 | Title/authors/article number from several independent reference lists; DOI resolves to a Transp. Res. Part C record; abstract not read | DOI added, kept (decision 1) |
| chen2016 | Chen, Guestrin; KDD 2016, 785-794; doi 10.1145/2939672.2939785 | Confirmed | none |
| hochreiter1997 | Hochreiter, Schmidhuber; Neural Computation 9(8) 1735-1780, 1997; doi 10.1162/neco.1997.9.8.1735 | Confirmed | none |

Other: inl2013leaf is marked "not re-verified online" in its entry (used in Section IV); not in this round's list, reported.

## Panel items

- W5: cut to 600-750 words, ladder table, estimate against measurement, quantisation, one figure, statement that the energy manager did not use the forecaster: handled.
- W6 R4: software faults, simulated accelerometer, 40 x 3 draws, one clean hour with 3 per hour bound, failed simulated criteria 551 and 533 of 560, not replayed on the 70 trips: handled. S4: no low-pass baseline stated: handled. 0.24 vs 0.19 spread: handled (sentence corrected). Clean-tracking failure retained. S3 scope sentence: handled. GRU sentence rewritten: handled.
- W7: planning framed as headroom with free speed; discussion (a) to (e); S7 transfer paragraph; S8 audit test stated; conclusion 200 to 236 words (brief says 200-220; 07-claims reports 236), numbers all within the abstract's set: handled except word count slightly over.
- R4, S1 to S8: R4 handled in VII; S1 handled by the reframe; S2 references added (sciarretta2015, liu2017, agarwal2021, amodei2016, skalse2022, lehman2020, tobin2017, zhao2020, wegener2021); S3 Section IX and VII; S4 VII; S5 V and IX; S6 r = -0.03 in II, V, IX; S7 IX; S8 IX.
- Not handled: S4 asks for a low-pass baseline or a stated reason; the text says none was run but gives no reason (acceptable, flag to lead).

## Decisions for the lead

1. wegener2021: keep with DOI (title and authors agree across several reference lists and the DOI resolves to Transportation Research Part C), or drop the one citation in Section II if a direct read of the abstract is required. Sentence only says deep RL has been applied to urban eco-driving, which the title supports.
2. Section III G5 row says Pass while Section VI says G5 is not closed in full. Suggest "Pass on latency and memory; converted model not run on target".
3. Remove "A1, A3" codes from the Section III table row (use "physics-loss ablation, forecast ablation").
4. Conclusion is 236 words against a 200-220 budget.
5. agarwal2021 and skalse2022 pages are left blank; add from the proceedings if the venue style needs them.
