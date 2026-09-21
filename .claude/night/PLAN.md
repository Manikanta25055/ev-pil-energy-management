# PLAN — night/2026-09-21-pil-campaign-and-final-report

Lane: python. Tier-0 verify: none present (no Justfile/Makefile/CI), so the
Python lane chain applies: `compileall` → `pytest` (ruff/mypy not configured,
so skipped, and not installed).

Board commands take `--port /dev/cu.usbmodem101`; `scripts/arduino_build.sh`
takes the port from `EVPIL_PORT`.

Hardware tasks are ordered first. They are the only ones that cannot be redone
without the board, and the machine is on battery (see briefing section 1).

| id | task | criterion | status |
|----|------|-----------|--------|
| t01 | A4 at 0.2/0.5/10 s, handling ON — build `-DFAULT_INJECT=0 -DFALLBACK_ENABLED=1`, 3 runs | 3 | pending |
| t02 | A4 at 0.2/0.5/10 s, handling OFF — build `-DFAULT_INJECT=0 -DFALLBACK_ENABLED=0`, 3 runs | 3 | pending |
| t03 | `src/evpil/control/scenarios.py` — the six spec-6.5 axes as data, plus tests | 2 | pending |
| t04 | `scripts/run_pil_campaign.py` + offline tests against a fake link | 2 | pending |
| t05 | PIL campaign on the board, 36 runs, committed after each scenario axis | 2 | pending |
| t06 | `scripts/plot_pil.py` + `docs/week10-pil-campaign.md` | 5 | pending |
| t07 | `scripts/build_report.py` — PIL section and the new A4 rows | 5 | pending |
| t08 | `tests/test_report_pil_parity.py` — docx figures vs JSON | 6 | pending |
| t09 | close-out: `docs/hardware-pending.md`, `docs/week9-a4.md`, spec open items | 5 | pending |
| t10 | full suite + acceptance sweep | 4, 8 | pending |
| t11 | email the report, write the receipt | 7 | pending |

Rules carried from GOAL.md that bear on sequencing:

- One run per configuration. A run that gives an unwelcome number is the
  result, not a reason to re-run.
- Never rely on a cached build switch. Pass `-DFALLBACK_ENABLED=` explicitly in
  both directions.
- The A4 sweep may not mix firmware images. t01 and t02 are the same source at
  two switch settings; nothing under `firmware/` is edited between them.
