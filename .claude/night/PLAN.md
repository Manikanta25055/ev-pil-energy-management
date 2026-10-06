# Plan — close out the corrected campaign (GOAL.md of 2026-10-07)

Pre-flight deviations, accepted with the operator awake at 00:58:
- Working tree is not clean: it holds the Codex agent's in-flight files, which
  its finisher will commit. Not mine to stash or commit early.
- No new branch. The finisher commits to the current one, and switching
  branches under it would break it. This run stays on
  `night/2026-09-21-pil-campaign-and-final-report`.
- No push (GOAL.md OUT OF SCOPE), so step 7's push is skipped every increment.

| id | task | criterion | status |
|----|------|-----------|--------|
| t01 | Wait for the board chain: actor arm, re-runs, merge to 36, A4 sweep. Re-run only what failed or was disturbed | 1, 2 | done: both VERIFY commands pass at 02:03 |
| t02 | `scripts/check_rule_arm.py` and `docs/week11-rule-arm-check.json`: rule arm, corrected campaign against the repeat campaign, cell by cell, from the saved JSON | 6 | done (94d2729) |
| t03 | Wait for the finisher; on `blocked`, fix only the reported failure | 3, 7 | done: finisher blocked at render; its remaining steps finished by hand |
| t04 | Look at every rendered page of both documents; fix and rebuild if needed; set `visual_review_pending` false | 4 | done: 66 + 2 pages viewed, manifest written |
| t05 | Sections 7 and 8 of `docs/week11-plant-correction.md` from the final data | 5, 6 | done |
| t06 | Merge `feature/decision-model` if all four conditions hold; else `MERGE-BLOCKED.md` | 12 | done: merged ef96306, all four conditions held |
| t07 | Full suite on the final tree; commit what is left | 7, 9 | done: 538 passed |
| t08 | Memory and handoff; acceptance sweep; stop caffeinate | 8, 10, 11 | done |

## Deferred findings
- Text inside the report's figures is under 8 pt at the printed width (drawn 13 in wide, placed at 6.4 in). Every figure, old and new. Serves no criterion; not fixed.
- The supervisor note is set in Calibri 11 by its generator, not the Times New Roman 12 the project uses for reports. The Codex agent's choice; left.
- The image on the board was built before the merge. Defaults are unchanged so the behaviour is the same, but the binary is not the merged source's.
- Microsoft Word was left running: it refused `quit` and `close` over AppleScript.
- `.worktrees/decision-model` and the branch `feature/decision-model` still exist after the merge.
