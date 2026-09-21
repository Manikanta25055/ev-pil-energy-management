# PLAN — night/2026-09-21-pil-campaign-and-final-report

Lane: python. Tier-0 verify: none present (no Justfile/Makefile/CI), so the
Python lane chain applies: `compileall` → `pytest` (ruff/mypy not configured,
so skipped, and not installed).

Board commands take `--port /dev/cu.usbmodem101`; `scripts/arduino_build.sh`
takes the port from `EVPIL_PORT`.

| id | task | criterion | status |
|----|------|-----------|--------|
| t01 | A4 at 0.2/0.5/10 s, handling ON | 3 | **done** (1e87260) |
| t02 | A4 at 0.2/0.5/10 s, handling OFF | 3 | **done** (0c91182) — criterion 3 PASSES |
| t03 | `src/evpil/control/scenarios.py` + tests | 2 | **done** (d2596f8) |
| t04 | `scripts/run_pil_campaign.py` + offline tests | 2 | **done** (feb3557, 1be30f0) |
| t05a | PIL campaign, actor arm, 18 runs | 2 | **running** — started 14:15 |
| t05b | PIL campaign, rule arm, 18 runs | 2 | pending — build verified to compile |
| t05c | merge the two arms into `docs/week10-pil-campaign.json` | 2 | pending |
| t06 | `scripts/plot_pil.py` figure + `docs/week10-pil-campaign.md` | 5 | script **done** (ed33d44); figure and note need data |
| t07 | `scripts/build_report.py` PIL section | 5 | **done** (ed33d44); renders once data exists |
| t08 | `tests/test_report_pil_parity.py` | 6 | **done** (ed33d44); runs for real once data exists |
| t09 | close-out: `hardware-pending.md`, `week9-a4.md`, spec open items | 5 | A4 half **done** (7a53c4e); rest needs the campaign |
| t10 | full suite + acceptance sweep | 4, 8 | pending |
| t11 | email the report, write the receipt | 7 | pending |

## The rule-arm build procedure, verified 2026-09-21 by a compile-only run

The controller is chosen at compile time on the presence of
`firmware/main/sac_actor_weights.h`. Nothing under `firmware/` is edited: the
generated header is copied to the scratchpad, removed for the build, and put
back immediately afterwards, and `git status firmware/` is checked clean.

```
cp firmware/main/sac_actor_weights.h "$SCRATCH/sac_actor_weights.h.bak"
rm -f firmware/main/sac_actor_weights.h
EVPIL_ARDUINO_DIR="$HOME/.cache/evpil-arduino-rule" EVPIL_PORT=/dev/cu.usbmodem101 \
    ./scripts/arduino_build.sh --flash -DFAULT_INJECT=0 -DFALLBACK_ENABLED=1
cp "$SCRATCH/sac_actor_weights.h.bak" firmware/main/sac_actor_weights.h
git status --porcelain firmware/     # must be empty
```

A separate `EVPIL_ARDUINO_DIR` keeps the two arms' object caches apart, so a
stale actor object cannot be linked into the rule image. The compile-only dry
run gave 292,699 bytes against the actor image's 314,464, a 21.8 KB
difference that matches the omitted weights.

`check_arm()` in the campaign script is the check that does not rely on any of
this being done correctly: it stops the campaign if `actor_steps` disagrees
with `--controller`.

## Rules carried from GOAL.md that bear on sequencing

- One run per configuration. A run that gives an unwelcome number is the
  result, not a reason to re-run.
- Never rely on a cached build switch. Pass `-DFALLBACK_ENABLED=` explicitly
  in both directions.
- The A4 sweep may not mix firmware images; nothing under `firmware/` is
  edited at any point.

## Housekeeping owed at acceptance

- `docs/week10-pil-{actor,rule}.json` are per-arm intermediates. They are not in
  the blast radius and criterion 8 requires an empty `git status --porcelain`,
  so they are moved to the scratchpad once merged. The merge is a pure
  concatenation, so `docs/week10-pil-campaign.json` holds every run verbatim and
  nothing is lost.
- `.claude/night/*.log` likewise: untracked, moved or removed before the sweep.
- `reports/EV-PIL-status-report.docx` is regenerated from the merged campaign
  and committed last, after the parity test passes against it.
