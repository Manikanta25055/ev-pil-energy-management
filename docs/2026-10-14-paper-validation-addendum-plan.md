# Paper validation add-on plan

Revision 4, 14 October 2026. Status: accepted for bounded execution after three `gpt-5.6-terra` subagent audits, corrective rechecks and a final independent primary-agent review of the entire plan. New add-on experiments have not been run. The initial audit verdict was REVISE; a successful plan review does not establish experimental results.

## Purpose and preservation rules

The user requires a supporting add-on. Its central account remains the historical 8.28% plant-model artefact, its diagnosis and correction, and the bounded comparison of learned and classical control, with A, B and C below providing verification that readers can reproduce and use to assess the reported conclusions.

Preserve the existing title in `paper/sections/00-front.json`, the section order and headings, and the five-item contribution structure. Keep forecasting, estimation and simulated planning in their existing supporting roles. Add no controller, estimator, testing-framework or planner-deployment contribution. Qualify unsupported wording wherever it occurs, including the abstract and conclusion, through replacements within the current structure.

Allow at most 600 net additional main-text words, preferably fewer through replacement. Use at most one compact main-text validation table; replace or extend an existing figure only when needed. Detailed equations, fixtures and diagnostic distributions belong in supplementary evidence. If these limits cannot be met, reduce optional work rather than expand the manuscript.

## Agent handoff and execution constraints

Inspect the live branch, working tree, running processes and `.claude/night/round2.log` before work. At this dated handoff, branch `night/2026-09-21-pil-campaign-and-final-report` included B1 commit `0f05954`; B1 completed at 17:26 IST and B2 repeats were running. Verify current state instead of treating this snapshot as a live status.

Do not start simulations, tests, builds, rendering or another serial campaign while the board campaign runs. Do not call `.claude/night/await_board.sh`, which starts an older campaign. Preserve `docs/2026-10-14-measurement-plan.md` and its B1/B2 rules. Read existing summaries and reuse completed analysis before scheduling any repeated work. Ask before pushing.

Existing host evidence and limits are in `paper/UPDATE-R2B.md`. The simulated panel decision in `paper/reviews/2026-10-14/editorial-decision.md` is an internal review aid, not a journal decision. Full systematic-review screening remains incomplete; no field-wide novelty conclusion follows from this plan.

This plan governs the add-on and supersedes conflicting planning assumptions in older handoffs; it does not overwrite the registered measurement rules. In particular, `paper/UPDATE-R2B.md` calls the H2 count result a failure despite its passing primary count, assumes healthy channels and calls the flagged fraction driving time. Use the qualified interpretation below when editing those claims, and keep the registered criterion separate from descriptive concerns about usability.

## Required checks and bounded outputs

| Track | Required check | Existing paper location | Evidence added |
|---|---|---|---|
| A: physical consistency | Inventory existing coverage and verify the historical binding-limit regression against independent equations and corrected controls. Add only a missing short invariant check. | `03-plant.md`, existing checks subsection | A reproducible connection between the actual artefact and checks that expose it. |
| B: sensor evidence | Verify and report completed B1; retain the existing H2 replay and its limitations. | `06-estimation.md` | The requested low-pass comparator and an accurate account of what logged replay establishes. |
| C: planning interpretation | Audit information access and distinguish planned time, simulated cycle duration and achieved distance crossing. | `07-planning-discussion-conclusion.md` | A bounded interpretation of simulated headroom without an unsupported learned-planner advantage. |

The existing B2 repeat analysis takes priority over new A/C runs because it directly supports the corrected headline comparison. All three tracks remain in scope as checks; they do not each require a new experimental study.

## A. Supplementary physical verification

First map the five paths to the existing tests: discharge-power limits, discharge-current limits, regenerative charge/SOC limits, auxiliary accounting and energy integration. `tests/plant/test_plant.py` and `tests/plant/test_regen.py` already cover many of these. Record that coverage rather than presenting it as newly discovered evidence.

Retain the historical billing-without-actuation fault as the known positive case. Its source is `82ca2fe^:src/evpil/plant/plant.py`, loaded by `scripts/run_plant_correction.py`; the existing before/after sweep is `docs/week11-plant-correction.json`. Pair it with corrected binding-limit and nonbinding controls. Reuse existing tests and outputs where sufficient; the full correction script also runs actor comparisons, which need not be repeated for this check. Any missing check must have an independently written oracle that does not call the production helper being checked; specify valid-domain assumptions, numerical tolerance and timestep refinement before its run. New failures require diagnosis and revalidation of affected results.

Keep the energy quantities distinct:

- Net terminal energy is the signed integral of terminal voltage times current. This is the `Result.energy_wh` and campaign-report convention.
- Gross draw integrates only positive terminal power. `PlantState.energy_wh` intentionally uses this convention; its difference from net energy is not a defect.
- Service-adjusted energy adds shed auxiliary energy to net terminal energy. Report that adjustment explicitly.
- Machine-side regenerative power and terminal battery charging are different ports; auxiliary demand and conversion losses must be accounted for before comparing them.

For a clean regeneration boundary check, verify the declared electrical-equivalent split, charge/SOC limits and terminal-port accounting under valid positive voltage/resistance and nonnegative auxiliary demand. Do not force an unreachable post-solve charge clamp and call the resulting case a live fault. The methods auditor's tentative charge-clamp defect was withdrawn after checking the actual equations.

Stop after coverage and clean controls are documented. A four-mutation study, new independent plant, generalized defect-detection rate or claim of systematic simulator-testing novelty is outside this add-on. General simulator testing has precedent, including [Zhang et al.](https://doi.org/10.1002/stvr.1892); this remains a verification supplement to the actual case.

## B. Completed measurements and constrained replay

Read `docs/2026-10-14-lowpass-pil-summary.json` and the six accepted B1 arm/block files. Verify twelve accepted runs, compiled arm identities and the preserved disturbed-run/rerun record. Do not rerun B1 just to regenerate its analysis.

Group B1 by seed-offset blocks: floor/severe seeds are 100/102 and 200/202. The same condition's seed is shared across arms, but floor and severe runs are not the same noise draw. For each arm and block report severe minus its own floor energy alongside both absolute energies, tracking error, peak current and dropped frames, so that own-floor normalization cannot hide worse clean tracking or higher clean energy. Keep negative differences signed. Two block contrasts support descriptive spread, not a population superiority or equivalence claim. Preserve the original rule crediting filtering generally if low-pass recovers at least as much as Kalman.

For B2, export the twelve declared axis/level IDs from `.claude/night/round2_board.sh` and `scripts/run_pil_campaign.py::select_runs` with actual seed IDs and firmware provenance. This is the existing twelve-condition selection, not a factorial crossing of all axis levels. Preserve its per-condition aggregation and exact Wilcoxon decision rule; repeated samples and nominal replicates are not additional independent conditions.

Join the twelve selected IDs to `docs/week11-pil-corrected.json` and the four repeat files `docs/2026-10-14-pil-repeats-{rule,actor}-s{100,200}.json`. Require one accepted rule/actor pair per condition and offset 0/100/200, identical physical settings and matching actual seeds within each pair. For nominal US06, the selected ID is `driving_condition/aggressive_mixed`, whose actual seeds are 2/102/202; keep the four extra original nominal rows in the historical descriptive summary rather than adding them to this three-draw primary analysis. Reused original noise seeds are not independent repetitions.

For each pair compute `d_pct = 100 * (actor_equivalent_wh_per_km / rule_equivalent_wh_per_km - 1)`, then take its three-offset mean for each condition. Preserve the registered verdict: two-sided p below 0.05 and positive median means learned used more; otherwise no measurable difference, which does not mean equivalence. Record the nominal-row mapping as a final-review bookkeeping clarification in the post-hoc decisions table. If any pair is missing or invalid, retain the gap and withhold the planned twelve-condition verdict; do not silently shrink or impute the panel.

Verify the statistics implementation before the final calculation. The current `scripts/paper_table5_stats.py` ranks equal magnitudes by row order and doubles a negative-rank tail, which is not a general two-sided implementation for either sign. Use average ranks for equal absolute differences, discard exact zero differences, and enumerate all sign assignments of the nonzero ranks using `T = min(W_plus, W_minus)`; all-zero differences give p = 1. Rank before display rounding, report the nonzero count and validate both sign directions and tied/zero examples. These requirements implement the registered exact test, including its edge cases; see the [SciPy Wilcoxon reference](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.wilcoxon.html). Interpret the test on this fixed scenario panel under its sign/symmetry assumptions, not as a fleet-population result.

H2 already reports host replay of 70 logged trips at their native 10-Hz sample rate: 30 counted alarms over 30.409 h, or 0.987/h, after the fixed standstill exclusion. That numerically meets the registered count rule; it does not establish a population false-alarm rate below 1/h. The roughly 59% flagged share covers recorded time, including standstill. Call it an alarm rate on assumed-healthy logged channels, with a false-alarm interpretation conditional on that assumption. Independent speed truth and health labels are absent, while replay supplies zero torque and grade. The interpolated 100-Hz result is a synthetic diagnostic, not target or native-rate validation; its 16.18 alarms/h fails the count rule.

The existing flagged share is a trip-duration-weighted mean of sample proportions; do not present it as an exact timestamp-integrated occupancy. Source: `docs/2026-10-14-bias-aware-logged-replay.json` and `scripts/replay_b7_logged.py`. Retain its detector settings, trip list and standstill exclusion. Extra episode replay is disabled by default.

Episode diagnostics are optional supplementary analysis if needed to interpret flagged time. Freeze the definition before replay: consecutive flagged intervals measured from timestamps; flag clearing is an observed state transition, not verified recovery from a real fault. Report all recorded time and moving-time diagnostics separately without changing the original denominator. Include all-event and criterion-count totals. Mark trip-end episodes right-censored, report their number, and do not substitute their observed duration for a completed recovery time. Use trip-level summaries; no detector retuning or new health labels.

## C. Host-only planning and information audit

Keep this section simulated and illustrative. A classical 400-m horizon is not an equal-preview control. `planner.py::plan_receding` calls the network at the 300-m horizon endpoint; `learned.py::node_features` reads speed limits another 400 m beyond that point, reaching up to 700 m from the current decision. Its next-stop feature is capped at 1000 m from the endpoint, potentially conveying stop information out to 1300 m. The terminal-cost and student arms also use a route-global `drivable()` feasibility mask that the plain short classical arm does not apply identically. A 700-m horizon alone would still not establish equal information.

Create a supplementary information-access table for the five existing arms: tracked cycle, full-route DP, classical 300 m, learned terminal cost and student. Record feature locations, stop information, feasibility preprocessing, arrival-price calibration and execution platform. The full-route reference solves its own planning approximation; it is not a certified optimum for the full physical plant.

The existing evaluator's `arrival_s` is `planned_time_s`, not achieved target-distance crossing time. Keep planned time, reference-cycle duration and achieved distance-crossing time separately. Audit final distance beside energy. Label `route.violations()` as planned-node-profile diagnostics; it does not establish actual closed-loop speed-limit or stop compliance.

Where traces are absent, allow at most eight host replays: four existing planner arms on US06/HWFET at their stored arm-specific `price_on_time_w`, with no retraining or new bisection search. This cap excludes the tracked-cycle reference. Use these replays for planner diagnostics only; do not compute new endpoint-normalized gains against the reference from its old full-run scalar values.

Freeze the `befecb8` tree and record full tree/blob IDs plus source, parameter, cycle, checkpoint and generated-profile hashes. That tree contains the table and both networks together, whereas the JSON's embedded `fe48fb3` commit predates those files; original profile traces and checkpoint hashes were not recorded. Run planners directly at stored prices, bypassing `meet_arrival`. Declare numerical reproduction tolerances before execution. If the existing table metrics match, label the result a frozen-snapshot reproduction; otherwise label it a new frozen reconstruction and do not use it to revise historical savings. Missing verifiable sources, weights or prices stop this replay branch at the information table and limitation.

For distance-crossing diagnostics, use the production interval convention: `distance += abs(pre_step_v_mps) * dt_s`, with trace times marking interval starts. Within crossing interval k, let f be the remaining distance divided by that interval's distance; report `k*dt + f*dt` and include fraction f of that interval's terminal energy and auxiliary adjustment. Do not substitute trapezoidal integration. Verify reconstructed final distance and full-run energy against `Result` first.

Keep original full-run energies separately. Profiles that never reach the exact endpoint remain visible as non-crossing, not omitted or assigned their planned arrival time; report the existing endpoint-distance tolerance independently. Crossing alone excludes terminal stopping/dwell and is not journey completion. Do not compare it directly with the arrival tolerance or use crossing-truncated energy as a replacement for complete-task energy. Preserve planned stop/dwell checks and tracking diagnostics, and state that realized route compliance is unestablished where it was not evaluated. Similar planned arrival tolerance alone does not establish superiority at matched time.

If timing or information cannot be matched with existing profiles, state the limitation and remove the isolated learned-benefit interpretation. Do not redesign the planner to rescue it. A classical 300/400-m sensitivity or the former forty-profile fixed-price grid is optional, supplemental and explicitly unmatched-information evidence; neither is required for completion. Freeze any such extension separately before execution and report every requested cell, including failures.

Neither extension runs under the default execution scope. The forty-profile grid is deferred; it is unnecessary for the remaining interpretation claims. Preserve the existing corridor evidence in `docs/week14-corridor-planner.json`, but describe an empty road as an optimistic scenario and the corridor as a recorded-drive constraint surrogate. Neither establishes a certified physical upper bound or validated traffic behavior, and different planner constructions cannot be treated as nested feasible sets.

No C planner port, route-preview protocol, new board benchmark or online feasibility claim belongs to this add-on. Learned terminal-cost planning has precedent, including [Yeom](https://doi.org/10.1016/j.egyr.2022.10.040); its presence does not justify another contribution in this paper.

## Claim corrections and completion criteria

Replace unsupported DP-bound wording in the abstract, introduction, plant/EMS sections, discussion and conclusion with an approximate feasible-policy reference evaluated through the full plant. An unexpectedly better controller result is an audit trigger; it is not proof of a physically impossible outcome. Qualify the current contribution item without adding a new item or changing the paper's subject.

Execution order:

1. Verify live campaign state; reuse completed H1-H3 and B1 evidence and finish B2 under its existing rules.
2. Freeze new A fixtures and B/C diagnostic definitions, source hashes and separate output paths. Record prior exposure to existing trips/routes and post-review choices.
3. After the board campaign ends, complete only missing A checks and required C rescoring sequentially. Run optional diagnostics only when a specific remaining claim needs them.
4. Reconcile each claim with its actual result. Preserve negative and inconclusive outcomes and label host simulation, logged host replay, target computation and closed-loop PIL separately.
5. Edit within existing paper sections, run checks appropriate to any code changes, rebuild once, inspect the changed pages and verify the title, ordered headings, contribution count and text budget.

Completion is a claim-evidence checklist: the historical fault is reproducible and corrected controls reconcile; B1/B2 follow their fixed rules; H2 remains conditional logged-channel evidence; planning states its actual information and timing limits; and no supporting result is promoted into a new central contribution. Outcome-dependent claims await experiments. No acceptance, positive gain or generalization guarantee is part of this plan.

## Terra audit disposition

Three Terra subagents separately audited structure, methods and feasibility. Their initial reviews required revision. Source verification confirmed the information-access and arrival-scoring problems and the scope risk of a new target port; it rejected the tentative regeneration live-defect claim under the model's valid-domain assumptions.

This revision removes the required mutation study, new planner port and mandatory forty-profile study, corrects the 400-m equal-preview assumption, distinguishes net/gross energy, and gives all three tracks a bounded role in the existing paper. The structure reviewer accepted Revision 2; the methods and feasibility reviewers accepted Revision 3 after its provenance, reference-arm and distance-crossing corrections, identifying no remaining must-fix plan defect in those rechecks. The manuscript and active firmware have not been edited by this plan audit.

## Final primary-agent review and execution checklist

The primary agent independently read the whole plan and checked the historical correction, plant tests and energy ports, B1 records, registered B2 rule and runner selection, H2 replay code, both DP approximations, planning features, evaluator and route semantics. Revision 4 closes the remaining handoff gaps: exact artifact locations, nominal-row bookkeeping, statistical edge cases and optional-study boundaries. At the final review, HEAD was `0f05954502319e198de42dfd61e7dfb355807d51` on the stated branch, B2 rule offset 200 was active, and the manuscript sources matched the pre-audit hashes. These remain dated observations.

The scientific purpose is to make the reported artefact and corrected comparisons reproducible, distinguish generic filtering from estimator-specific benefit, and prevent planning gains from being attributed to learning when information or task completion differs. A supports the diagnosis; B strengthens the existing measured estimation finding; C narrows an illustrative claim. None creates a sixth contribution.

The plan review is closed for this revision. Execution is complete only when the following checks have recorded results or explicit limitations:

- A: link the historical failing case, current coverage and independent clean-control residuals, with assumptions and tolerances. Reuse adequate existing evidence.
- B: reconcile twelve B1 runs and the B2 twelve-condition paired manifest, retain disturbed runs, apply the unchanged verdict rule, and correct H2's criterion/label wording.
- C: publish the information table and timing/constraint caveats; attach the eight frozen-price diagnostics if provenance permits, otherwise document the hard-stop limitation.
- Paper: map each changed claim to its artifact and existing section; preserve the exact title, ordered headings and five contributions, and verify the 600-word net cap against a saved pre-edit source snapshot.
- Verification: after the campaign, validate only changed code and newly calculated results, run prose lint before/after, build the final manuscript and inspect changed pages. The frozen plan is not a substitute for checking execution.

Do not reopen a blanket literature or plan audit for unchanged assumptions. Reopen only the affected check if an input changes, a reproduction gate fails, a new physical defect appears, or a proposed edit exceeds the scope limits. Literature-screening completion remains a separate unfinished task; this add-on review is not its certification. No remaining planning blocker was identified by the final primary-agent review.
