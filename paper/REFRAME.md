# Reframe brief, round 2 (read after BRIEF.md; this file wins where they differ)

The mock manuscript went through a simulated five-reviewer panel on 2026-10-14.
Decision: Major Revision. The panel's reports are in `paper/reviews/2026-10-14/`
(`editorial-decision.md` first). This round rewrites the paper around a new
centre and applies every correction the panel asked for. No new experiments in
this round; a measurement round may follow and will only update numbers.

BRIEF.md still governs: sources (Section 4), internal-code renaming (Section 4
table), honesty rules (5), prose rules (6), output format (7), figures (8),
references (9), claims file (10), hard limits (11). Read all of it.

## 1. New title

An 8% Learned Energy Saving That Was a Plant-Model Artefact: Processor-in-the-Loop
Evaluation of Rule-Based and Learned Electric-Vehicle Energy Management on a
Microcontroller

## 2. The story now (every section must fit this)

1. **The incident.** In a processor-in-the-loop (PIL) campaign, a Soft
   Actor-Critic (SAC) energy manager on an ESP32-S3 appeared to use 8.28% less
   energy than a rule-based manager, in 14 of 16 settings, up to 21.6% at driver
   aggression 1.5. The gain grew with demand and vanished on UDDS and HWFET. It
   was a vehicle-model artefact: the model billed battery power capped at the
   policy's ceiling but computed acceleration from uncapped torque, so the
   policy learned to set a low ceiling and draw power above it, unbilled. A
   controller-free sweep showed it: a constant 5 kW ceiling billed 8.05 Wh/km
   for the full US06 cycle (SIMULATED).
2. **How it was found, honestly.** The plant validation gate (G2) did not catch
   it: G2 compared the model with logged trips and never exercised the
   power-ceiling path. The audit was triggered by anomalies in the campaign
   tables (the gain grew with demand, vanished on gentle cycles, and exceeded
   what the rules' distance from optimal allowed). Say this plainly. The paper's
   method contribution is the set of checks that would have caught it before
   the campaign: (a) a billing-against-motion consistency sweep with no
   controller in the loop; (b) a learner must not beat the offline
   dynamic-programming (DP) optimum computed on the same plant; (c) every
   actuator limit must act on motion, not only on the energy bill.
3. **Why no honest gain was available.** With the speed profile fixed by the
   tracking loop and three actuation numbers, a DP bound puts the rules within
   0.01% to 0.16% of the optimum. The corrected campaign agrees: the learned
   policy uses more energy in 11 of 12 distinct conditions (numbers in Section
   4 below). When speed is free, a classical DP speed planner finds 5% to 10%
   (SIMULATED), which is where a learned method could matter: future work.
4. **Where the measured gain was.** In the speed loop, not the energy manager:
   a two-state Kalman speed estimator cut the energy lost at ten times the
   sensor-noise floor from 9.44 to 0.24 Wh/km (MEASURED), with the caveats
   below. Learned reviewers classified faults better offline and controlled
   worse in the loop (SIMULATED): offline accuracy did not predict closed-loop
   benefit, a second instance of the paper's theme.
5. **Cost next to accuracy.** Every learned component is reported with its
   on-target cost; the forecaster's measured latency was 64% above its estimate.
   The Transformer forecaster is a supporting result, shortened.
6. **Takeaway.** The contribution is the audited case, the checks it implies,
   the headroom bound that explains the null result, and the measured costs,
   not a new controller. The claim is bounded to this task: one vehicle model,
   one board, one learned algorithm, speed fixed by the tracking loop.

Tone toward Tangi et al. [@tangi2025]: unchanged from BRIEF.md; keep it as the
group's starting point, respectfully, in one paragraph of the Introduction.

## 3. Section map, owners, budgets (body words)

| File | Heading | Owner | Words |
|---|---|---|---|
| 01-intro-related.md | I. INTRODUCTION; II. RELATED WORK | W1 | 850 + 850 |
| 02-platform.md | III. EXPERIMENTAL PLATFORM AND METHOD | W2 | 1000-1150 |
| 03-plant.md | IV. VEHICLE MODEL AND THE POWER-LIMIT ARTEFACT | W3 | 1400-1600 |
| 04-ems.md | V. ENERGY MANAGEMENT AFTER THE CORRECTION | W4 | 1400-1600 |
| 05-forecast.md | VI. ON-DEVICE FORECASTING: ACCURACY AGAINST COST | W5 | 600-750 |
| 06-estimation.md | VII. SPEED ESTIMATION AND SENSOR-FAULT DETECTION | W6 | 1300-1450 |
| 07-planning-discussion-conclusion.md | VIII. SPEED PLANNING; IX. DISCUSSION AND LIMITATIONS; X. CONCLUSION | W7 | 350 + 850 + 220 |

The files already contain the previous draft (04-ems.md was 05-ems.md and
05-forecast.md was 04-forecast.md; claims files renamed to match). Start from
your file: keep what is correct, rewrite what the new story or the panel
requires. Section ids stay as they are (`sec:intro`, `sec:related`,
`sec:platform`, `sec:plant`, `sec:ems`, `sec:forecast`, `sec:estimation`,
`sec:planning`, `sec:discussion`, `sec:conclusion`), so cross-references keep
working. Figure and table ids keep their section prefix.

Abstract, index terms, title block and back matter (including the availability
statement) are the lead's. Do not write them.

## 4. Numbers new in this round

`docs/paper-table5-stats.json` (made by `scripts/paper_table5_stats.py` from
`docs/week11-pil-corrected.json`):

- 16 valid settings contain 5 runs of the nominal US06 condition (Mixed, No
  delay, Flat, Noise 1x, Driver 1.0; SOC 0.55 is NOT one). So 12 distinct
  conditions.
- Learned minus rule energy, comparable scale, per condition: 11 of 12
  positive; median +0.31% (bootstrap 95% CI 0.17 to 0.76); mean +1.11% (0.27 to
  2.27); exact Wilcoxon signed-rank p = 0.001, sign test p = 0.006 (two-sided).
- Over the 16 settings: mean +0.94% (keep this canonical figure), median +0.35%.
- Nominal US06 repeats: rule arm 190.73 to 191.41 Wh/km (range 0.36%); learned
  191.43 to 191.98 (0.29%); paired difference +0.40% mean, SD 0.22, 95%
  t-interval 0.13 to 0.67 (n = 5).
- The single setting where the learned policy is lower (uphill, -0.02%) is
  inside the 0.36% repeat range.
- Dropped frames against the energy difference: r = -0.03 (no relation).

Cite this file for these numbers in your claims file.

## 5. Corrections the panel required, by owner

Every item must be visibly handled in the text. Tick each in your claims file
under a heading "Panel items", saying where and how.

W1 (Introduction, Related Work)
- R1: the Introduction states the bounded task early: speed fixed by the
  tracking loop, three actuation numbers, headroom at most 0.16%.
- Contributions list rewritten to the new story (artefact case and audit
  checks; headroom bound; corrected comparison with paired statistics;
  measured estimation gain and offline-versus-loop finding; on-device costs).
- S2: Related work must cover battery-EV energy management and eco-driving,
  not only hybrids; add simulator artefacts / specification gaming /
  sim-to-real; add RL statistical reporting. Three references were confirmed
  by a reviewer and may be added after you confirm them yourself with
  WebSearch: Sciarretta, De Nunzio, Ojeda, "Optimal ecodriving control",
  IEEE Control Systems Magazine 35(5) 71-90, 2015, doi 10.1109/MCS.2015.2449688;
  Liu, Hu, Li, Cao, "Reinforcement learning optimized look-ahead energy
  management of a parallel hybrid electric vehicle", IEEE/ASME Trans.
  Mechatronics 22(4) 1497-1507, 2017, doi 10.1109/TMECH.2017.2707338; Agarwal
  et al., "Deep reinforcement learning at the edge of the statistical
  precipice", NeurIPS 2021. Add a specification-gaming or reward-hacking
  reference (for example Amodei et al. 2016 "Concrete problems in AI safety",
  or Krakovna et al. on specification gaming) only if verified. Cite XGBoost
  (Chen and Guestrin, KDD 2016) and LSTM (Hochreiter and Schmidhuber 1997) if
  the paper names them anywhere. Aim for 8 to 14 new verified references in
  total; write them to `01-refs.json`.
- Drop "pre-registered" wording; use "acceptance gates fixed before each
  experiment".

W2 (Platform and Method)
- R3: replace the gate table with one table of every criterion fixed in
  advance and its outcome, including those outside G1 to G5 (the estimator's
  clean-tracking bound, 0.0193 against 0.0104 m/s, failed; the bias-aware
  detector's registered simulated criteria, 551 and 533 of 560, not met), and a
  second short list or table of every rule or revision made after results were
  seen (the G2 split; the 1 m/s tracking exclusion of the delay settings; the
  16-dropped-frame re-run rule; the second detector designed after the first
  failed). Check `git log` (read-only) for when gate and criteria files were
  committed; if dated records exist, say "recorded with dates in the version
  history before the experiment"; if not, do not claim it.
- Define "arm" (controller under test), "cell"/"setting", and "comparable
  energy scale" for an outside reader.
- S6: dropped frames per run against energy difference: r = -0.03 (Section 4).
- Note that seeds replay only the noise draw (keep if already stated).
- State the hardware is a general-purpose microcontroller, not an
  automotive-qualified part, in one sentence (W7 develops it).

W3 (Vehicle Model and the Power-Limit Artefact)
- The artefact becomes the centre of this section, not its last subsection:
  the earlier campaign result, the mechanism (billed against delivered power),
  the controller-free sweep (Fig. @fig:plant-correction), how it was found
  (anomalies, not G2), the fix, and the audit checks it implies (story item 2).
- R7: a firm limitations paragraph on plant fidelity: rolling coefficient 2.2
  times a published coastdown value, rotational factor, regeneration ceiling,
  drivetrain efficiency, winter-only validation envelope, G2 failure on 1 of 7
  trips, 13.4% to 16.9% median energy error on transfer. Say what this does
  and does not threaten: absolute Wh/km, not the paired ranking on the same
  plant; but no sensitivity study was run (unless the measurement round adds
  one).

W4 (Energy Management After the Correction)
- Order: control structure and rules; headroom bound first (DP, 0.01% to
  0.16%); the learned policy; the corrected campaign; link outage.
- R2: report the replicate structure and the paired statistics (Section 4);
  restate "1 of 16" as part of it; median and mean; the uphill exception
  inside the repeat range. Update Table @tab:ems-campaign (mark the five
  nominal repeats) and remake Fig. @fig:ems-campaign to show the paired
  differences with the repeat range as a band (read `docs/paper-table5-stats.json`).
- R5: the forecast ablation removes two observation channels computed from the
  reference speed (mean and maximum of the next 3 s of reference-implied
  traction power), not the Transformer of Section @sec:forecast, which never
  ran inside the energy-management loop. Say so in one plain sentence.
- R8: a table of SAC hyperparameters and reward weights, and how the rule
  constants were set (from `src/evpil/`, `scripts/train_*`, configs and docs;
  read, do not run). If a value cannot be found, list it as a gap.
- S5: US06 was held out of training, but it was the cycle of the earlier
  campaign that led to the model fix, so it was not unseen by the authors; the
  learned tracking deficit appears on US06-based settings (0.17 to 0.50 m/s)
  and not on UDDS or HWFET (0.004 and 0.016 m/s).
- The earlier-campaign subsection shrinks to a pointer to Section @sec:plant.
- Safety wording in the outage subsection: describe the behaviour; no safety
  claim (S3).

W5 (On-Device Forecasting: Accuracy Against Cost)
- Cut to 600-750 words. Keep: task and leakage safeguards, the ladder table,
  latency estimate against measurement (22.28 ms estimate, 36.46 ms measured,
  64% above; 35.03 ms on the Arduino core), quantisation cost, and one figure.
  Drop or compress physics-informed training and distillation to a sentence
  each unless the result is needed elsewhere.
- State that the energy manager did not use this forecaster (Section @sec:ems).

W6 (Speed Estimation and Sensor-Fault Detection)
- R4: the bias-aware detector paragraph says: faults injected in software, a
  simulated accelerometer channel, 40 faults times 3 noise draws, the one
  clean hour (a zero count in one hour bounds the false-alarm rate below about
  3 per hour at 95%), the registered simulated criteria not met (551 and 533
  of 560), and whether it was replayed on the 70 logged trips (it was not,
  unless the measurement round adds it; then say so).
- S4: the Kalman estimator is compared only against the raw-reading baseline
  loop; say no low-pass filter baseline was run (unless the measurement round
  adds it). The 0.24 Wh/km figure is against the second-seed floor; the two
  floor runs differ by 0.19 Wh/km for the baseline, so state that the residual
  loss is within run-to-run spread.
- The failed clean-tracking criterion stays reported as failed.
- S3: one sentence of scope: the detector and fallback are evaluated as
  monitoring functions; no ISO 26262 or SOTIF claim is made. Discuss the
  outage-hold reversal at 4 to 5 s if it is in your section, or leave to W4.
- Rewrite the GRU sentence (offline: "recognised a real fault in 99% of blocks
  with a flag raised and 88% with none, against 94% and 1% for the monitor")
  so it reads clearly.

W7 (Planning, Discussion, Conclusion)
- Planning stays short and SIMULATED; frame it as the headroom that appears
  when speed is free, the place where a learned method could be tested next.
- Discussion: (a) why the rules held (headroom); (b) the audit checks as a
  reusable procedure, including the honest note that anomalies, not the gates,
  triggered the audit (DA point); (c) what transfers: S7, timing and memory on
  the ESP32-S3 against automotive-class microcontrollers (operation counts and
  weight memory port; jitter against a non-real-time host and the radio stacks
  of the Arduino image do not); (d) safety scope (S3); (e) limitations: one
  vehicle model, one board, one learned algorithm and one reward design, one
  run per cell except the nominal repeats, plant fidelity, simulated faults.
- S8: state the audit test "a learner must not beat the offline optimum on the
  same plant" as a check others can apply.
- Conclusion: 200-220 words, no new numbers beyond the abstract's.

## 6. Minor items (owner in brackets)

- Define the "Mixed" row in Table 5 [W4].
- "36 runs" includes the 4 excluded delay runs: say "36 runs, 32 of them in
  the valid set" where the count appears [W2, W4].
- Blank space on page 11 is a layout matter for the lead.

## 7. Process for every writer

1. Read BRIEF.md, this file, `paper/reviews/2026-10-14/editorial-decision.md`,
   and the panel reports relevant to your section.
2. Invoke the human-academic-prose skill: read
   `~/.claude/skills/human-academic-prose/SKILL.md`, then
   `reference/wordlists.md` and `reference/evidence.md` in that folder.
3. Run `python3 ~/.claude/tools/prose_lint.py "paper/sections/<file>.md"` and
   `python3 paper/measure.py` BEFORE editing; record both.
4. Rewrite. Every number from a source file; MEASURED or SIMULATED on each
   result; failures reported as failures.
5. Lint and measure again. Fix all HIGH and MED. Your section's sentence-length
   SD must be at least 8.6 words and must not drop below its value before your
   edit.
6. Update your claims file: numbers table, mismatches, gaps, Panel items, and
   before/after lint and SD.
7. Final message to the lead, under 200 words: files written, word count,
   lint and SD before/after, panel items done, gaps.
