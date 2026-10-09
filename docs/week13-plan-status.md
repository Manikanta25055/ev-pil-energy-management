# Where the model-advancement plan stands

**As of 2026-10-09.** The plan is `docs/2026-10-07-model-advancement-research.md`
(an untracked file in the main checkout; it was not edited). This is the
status of each stage of its section 13. Work is on branch
`feature/sensor-arch`, not merged and not pushed.

| Stage | What the plan asked for | State | Record |
|---|---|---|---|
| P0 | Close the running campaigns | done before this work | `docs/week12-speed-arms.md` |
| P1 | Acceleration provenance, realistic cases, a stronger classical baseline, frozen criteria | done, SIMULATED | `week13-sensor-architectures.md` sections 2 to 4 |
| P2 | Tiny GRU, then FastGRNN (architecture A2) | done, SIMULATED. Neither beats the rule monitor in the loop | same, sections 5 to 8 |
| P3 | Learned component in the estimator (A3) | done, SIMULATED | `week13-estimator-and-board.md` |
| P3 | Bounded learned torque correction (A4) | declined at its gate, with the measurement | `week13-a4-decision.json` |
| P4 | Post-action review by Jev (A1) | **blocked: Jev is not purchased.** The architecture itself was run with every other reviewer, at 70 ms to 1 s | `week13-sensor-architectures.md` section 7 |
| P5 | A1 variants (event-triggered, cached, outage), A5, A6 | done, SIMULATED, with the non-Jev reviewers. The Jev rows are empty | same |
| P5 (port) | Eligible candidates in C, parity, board campaign | B7 and the rule monitor are in C and match Python step for step; board campaign in `week13-estimator-and-board.md` | `week13-b7-pil.json` |
| P6 | Classical speed planner, learned terminal cost, student (A8) | done, SIMULATED | `week13-energy-planning.md` |
| P7 | Remote planning with buffering (A7) | declined at its gate, with the measurement | `week13-a7-decision.json` |

## What is blocked on a purchase

Jev, and with it every row of the plan that names Jev: A1 with Jev in the
reviewer's seat, the fan-out and cached-advice variants as Jev implements
them, A5 with Jev as the slow reviewer, and a Jev adviser for the planner.
Laya, Kev and Nimble were not downloaded: the plan puts them after Jev and
only where a question is left for them.

Nothing was estimated in Jev's place. The reviewer slot
(`evpil.control.supervisor.Reviewer`) takes any object with `review(snapshot)`
returning four probabilities; a Jev adapter is one class.

What the non-Jev rows say a hosted reviewer has to do to earn its seat:
diagnose no worse than the 16-state GRU, answer inside about half a second,
and bring information that twelve numbers per 100 ms do not carry. And one
thing they say it cannot fix: a better diagnosis did not make a better
supervisor, because the speeds the loop falls back on drift.

## Not done

- Everything in the section above.
- Any learned component on the board: none passed the registered criteria.
- Speed planning on the board, and planning with other traffic.
- Repeats with other training seeds, for the reviewers and for the planner
  networks.
- The 70-page report and the supervisor note do not yet carry any of week 13.
