# Night plan — 2026-10-09, against GOAL.md (15 criteria)

Branch: `feature/sensor-arch` (GOAL.md names it; no night branch is cut and nothing is pushed, criterion 13).

| id | task | criterion | status |
|---|---|---|---|
| t01 | commit the anchor, plan, briefing skeleton | 14 | done |
| t02 | A3: a blended fallback speed while flagged (fixed weight; weight from the monitor; weight from the GRU), val and test, beside A0 and A2 monitor | 3 | running in background |
| t03 | A4 gate: measure the clean tracking gap left after estimation; record run/skip | 4 | pending |
| t04 | B7 in C (`control.c`) with a Python parity test | 5, 6 | done |
| t05 | rule monitor and block features in C with a parity test | 5, 6 | done |
| t06 | firmware arms for B7 and B7+monitor; host-side fault injection; board campaign; restore the actor image | 7 | built and smoke-tested; campaign pending |
| t07 | P6: route task and its criteria (written before any run), classical planner | 8 | pending |
| t08 | P6: learned terminal cost, student policy, matched comparison on test | 8 | pending |
| t09 | P7 gate: record run/skip from the P6 result | 9 | pending |
| t10 | write-ups: estimator-and-board, energy-planning, plan-status | 10, 11 | pending |
| t11 | acceptance sweep, handoff, memory | 1, 2, 12-15 | pending |
