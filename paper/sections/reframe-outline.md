# Reframed paper: revised outline

Draft for review, not committed. The paper's centre moves from "learned against rule-based energy management" to "a learned gain that came from the vehicle model, and the checks that exposed it". Forecasting and planning become one supporting section.

## Proposed title

Primary: **When a Learned Energy Manager Beats the Optimum: Exposing and Withdrawing a Simulator Artefact in a Processor-in-the-Loop Study on a Microcontroller**

Plainer alternative: **Validating Learned Energy Management Against Its Own Vehicle Model: A Withdrawn 8.28% Gain in a Processor-in-the-Loop Study**

## Why the story changes

Every safeguard the current draft leads with (pre-written gates, board repetition, timing measurement, MEASURED/SIMULATED labels) was in place when the 8.28% gain was reported, and none of them could see the fault. The record shows why, from the code:

- Gate G2 replays logged trips with the ceiling set to 1e9 W, so it never binds (`scripts/identify_params.py:347`).
- The dynamic program held the ceiling at motor maximum (`src/evpil/control/dp.py:145`), on the stated reasoning that a ceiling could only starve the speed loop (`docs/week7-control.md` §1).
- The plant test before the fix asserted that billed power met the limit exactly, not that motion was reduced (`tests/plant/test_plant.py`, `test_discharge_power_limit_is_enforced`, at `82ca2fe^`). The trajectory-invariance test ran with a 300 kW ceiling that never binds (`tests/control/test_sim.py`).
- The repeat campaign reproduced the artefact: 14 of 16 again, mean −8.29%, and energy within 0.18% on average across 32 settings, 0.71% at worst (computed here from `docs/week10-pil-campaign*.json`).
- Instrumented firmware then measured the ceiling (rules 123 kW average, learned 72 kW) and appeared to confirm the peak-shaving story (status report §27).

What caught it was the contradiction with a bound: the policy finished below the precomputed DP optimum at equal tracking (176.4 against 190.39 Wh/km on US06). Two more signs pointed the same way: the gain grew with demand and vanished where no ceiling can bind. A controller-free sweep of fixed ceilings then reproduced the effect (5 kW: 8.05 Wh/km over the full 12.888 km). That sequence is the method the paper can now offer, and it is stronger than "we pre-registered gates".

## Section plan

Word targets are for the body text. The current total body is about 12,000 words; the plan comes to about 9,800.

| # | Section (id) | Words | Source today | What changes |
|---|---|---|---|---|
| I | Introduction (`sec:intro`) | 1,100–1,250 | 01-intro-related.md | Rewritten, draft attached (about 1,250 words; the forecasting and planning sentences can go if it must shrink). Opens on the artefact, not on Tangi et al. |
| II | Related Work (`sec:related`) | 600–700 | 01-intro-related.md | Cut "Data-driven range prediction" to one paragraph. Add a short subsection, "Validity of Learned Controllers in Simulation": reward hacking [@amodei2016], seed sensitivity [@henderson2018], deployment gaps [@dulac2021]. Keep the positioning table and add a column: "plant audited against the controller's commands". |
| III | Platform and Method (`sec:platform`) | 900–1,000 | 02-platform.md | Mostly kept. Add one paragraph saying what each gate covers and what it cannot cover, so Section V can refer back. Fix the overstatement flagged in audit B: the delay-axis validity rule was set after those runs. |
| IV | Vehicle Model and Data (`sec:plant`) | 800–900 | 03-plant.md | Keep the model, G2 and VED transfer. Move "A Fault in the Power Limit" out to Section V. |
| V | **An Apparent Gain and Its Withdrawal** (`sec:artefact`) | 1,300–1,500 | new; draws on 05-ems "An Apparent Gain", 03-plant fault subsection, week11-plant-correction.md, status report §26–28 | The new centre. (A) The original result: 14 of 16, 8.28%, up to 21.6% at aggression 1.5. (B) What it survived: the repeat campaign (0.18% agreement), the ceiling telemetry, the gates. Table: each safeguard, what it tests, and whether it could see this fault. (C) The bound contradiction and the two pattern signs. (D) The controller-free ceiling sweep, with fig-plant-correction moved here. (E) The fix, the four new plant tests, and the rule-arm non-interference check (+0.07%, 95% interval −0.03 to +0.17). |
| VI | **Checks for Learned Controllers on Simulated Plants** (`sec:checks`) | 500–600 | new; generalises Section V | The procedure stated for reuse: compute an independent bound before learning, and treat a result past it as a model fault until shown otherwise; sweep every command channel the policy controls with no controller in the loop and require each saving to carry a physical cost; assert conservation (traction ≤ battery supply) as a test; check that a fix leaves non-binding arms bit-identical; keep unverified mechanisms labelled as inferred. Say plainly which of these were done here and which are proposed (see gaps). |
| VII | Corrected Comparison (`sec:ems`) | 900–1,000 | 05-ems.md | Retraining (154.86 ± 0.51 against 153.90, SIMULATED). Board campaign: 1 of 16, +0.94%, worse tracking (MEASURED). Forecast ablation folded in as one paragraph. Link-outage sweep cut to two sentences or moved to an appendix. |
| VIII | Where the Energy Went: Speed Estimation and Fault Detection (`sec:estimation`) | 1,000–1,200 | 06-estimation.md | Trimmed by about a third. Keep Kalman (9.44 to 0.24 Wh/km) and the bias-aware detector (120 of 120). The acceleration-residual detector and fused estimator go to one paragraph each, failures kept. |
| IX | Supporting Results: Forecasting and Planning (`sec:supporting`) | 600–700 | 04-forecast.md, 07 planning part | Forecasting: ladder headline (Transformer 16.6% over persistence, linear regression 87% of the benefit at 1.2% of estimated compute), 36.46 ms of 40 ms on target, 8-bit costs 0.95%. Planning: 10.4% and 5.1% within 25 m, student 0.0%, all SIMULATED. Physics-loss and distillation studies go to a sentence each. |
| X | Discussion and Limitations (`sec:discussion`) | 700–800 | 07 discussion | "Why the rules held" stays. "What the method caught" now leads with the artefact and adds the other three catches (compute estimate 64% low, same-seed false alarm, rule monitor) as further cases of the same pattern. Limitations unchanged. |
| XI | Conclusion (`sec:conclusion`) | 200–250 | 07 conclusion | Rewritten around the withdrawal. |

## Figures

- Keep: fig-plant-correction (moves to V), fig-ems-campaign (VII), fig-estimation main figure (VIII), fig-planning-corridor (IX).
- New, suggested for V: a paired dot plot of the 16 settings, learned minus rules, for the original campaign, its repeat and the corrected campaign, from `docs/week10-pil-campaign.json`, `docs/week10-pil-campaign-repeat.json` and `docs/week11-pil-corrected.json`. It shows in one panel that the result reproduced and still was not real.
- Drop or move to supplementary: the forecast ladder and distillation figures, if the page budget is tight.

## Abstract and introduction

Drafts are in `abstract.txt` (drop into the `abstract` field of `paper/sections/00-front.json`) and `01-intro.md` (replaces the Introduction part of `paper/sections/01-intro-related.md`; Related Work below it is left alone until Section II is revised). The one new reference is in `refs-addition.json`.

## Gaps and decisions for the author

- The checks in Section VI are partly proposed. Only the ceiling was swept with no controller in the loop. The regeneration blend and auxiliary derate were covered by the trajectory-invariance test, but no record shows that each one's energy saving was checked for a physical cost. The pack current limit had the same fault and was fixed in the same commit. Either run a controller-free sweep of those two channels before submission, or present the full sweep as a recommendation.
- Whether the pre-correction DP should have found the lever: it held the ceiling at maximum by design, so it could not. The draft says this directly. It is a design choice, not an oversight, and it is also why the bound worked as a check.
- Title: the primary title is sharper. The plainer one is safer for IEEE Access.
- Tangi et al. moves from the second paragraph to the third. Their three open questions are kept, in the same neutral terms the brief requires.
