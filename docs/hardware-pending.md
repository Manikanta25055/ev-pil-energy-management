# Work that is waiting on the board

**Raised:** 2026-09-02. **Status:** deferred, not attempted.

No ESP32-S3 is attached. `arduino-cli board list` shows only Bluetooth
serial ports, and there is no `/dev/cu.usbmodem*`. Everything below needs the
board plugged in and is left undone rather than estimated or simulated.

Nothing in this file has been measured. No number here may be cited until the
run that produces it has happened.

---

## 1. Ablation A4, deadline-miss handling on vs off

Scheduled for week 9 by the spec's schedule table; backs claim C5, whose
wording is "control-quality cost of a miss".

The handling-**on** half is already measured, on hardware, in week 7:
`docs/week7-fallback.md` and `docs/week7-fallback.json`. Every counter moved by
exactly the amount its injection schedule implied, and `ctrl_late` stayed at 0
throughout.

The handling-**off** half has not been run. What it needs:

```bash
./scripts/idf.sh -DFAULT_INJECT=1 -DFALLBACK_ENABLED=0 build
./scripts/idf.sh -p /dev/cu.usbmodem1101 flash
PYTHONPATH="src:." python3 scripts/run_fallback.py --out-json docs/week9-a4.json
```

**The build half is done and passes.** `-DFALLBACK_ENABLED=0` compiled clean on
2026-09-02 (exit 0, `evpil_fw.bin` 0x32d50 bytes, 80% of the app partition
free), which is what the week 7 note meant by keeping the ablation a rebuild of
the measured firmware rather than a later reconstruction of it. Only the
measurement is outstanding.

**The harness is now written and scores this build correctly**, added
2026-09-02 as `--fallback-off`. Without that flag the script would mark the
ablation as a failure of the firmware, because its normal-build expectations
require two counters to move that the ablation compiles out.

The expectations are fixed now, before the run, which is this project's
convention and matters more than usual here: under A4 a counter reading zero is
the ablation working, and a harness whose expectations were adjusted after
seeing the run could not tell that apart from the firmware breaking.

| Counter | Inside `#if FALLBACK_ENABLED`? | Expected under A4 |
|---|---|---|
| `ctrl_fallback_steps` | yes | **exactly 0**, the branch is compiled out |
| `limp_steps` | yes | **exactly 0**, the branch is compiled out |
| `ems_fallback_steps` | no | unchanged, >= 5 |
| `infer_deadline_misses` | no | unchanged, >= 5. A4 removes the handling of a missed deadline, not its detection |
| `stale_steps` | no | unchanged, >= 50. Tracked outside the guard on purpose, so the ablation does not compare a mode that can limp against one that cannot tell it should |
| `ctrl_late` | no | **exactly 0 in both modes.** The fallback path is not allowed to cost the loop its own deadline. If A4 moves this, that is the finding |

Which two counters are guarded is not restated in Python by hand:
`tests/firmware/test_a4_expectations.py` parses the `#if` nesting out of
`tasks.c` and fails if the firmware ever guards a different set. Seven tests,
all passing, none needing the board.

The quantity the ablation exists to produce is the control-quality cost, and
the harness now captures it. Week 7 measured torque going 226.18 Nm to
**0.00 Nm** during the silent window and staying there -- the limp ramp doing
its job. With the ramp compiled out the PID spends that window integrating
against a speed measurement it cannot refresh, so the cost should appear as
windup during the window and a transient when the host answers again. The
script now records torque for `RECOVERY_WINDOW_S` = 2.0 s **after** the window
closes as well as during it, because that is where the recovery transient
lands, and writes both traces to `docs/week9-a4.json`.

What is still missing is only the run.

## 2. The full stack on the device

Also week 9. Blocked twice over: on the board, and on the parked decision about
what should ship at all. The measured costs that decision turns on are already
in hand -- actor 19.3 KB and 0.121 ms, quantised forecaster 20.2 KB and
36.46 ms -- so this is waiting on the choice, not on more measurement.

## 3. The PIL campaign

Week 10 onward. Needs the board and needs item 2 settled first.

## 4. Anything the toolchain change forces to be re-measured

If the firmware moves from ESP-IDF to the Arduino ESP32 core (see the open
question in `docs/toolchain-arduino-cli.md`), then G1, G3 and G5 were all
measured against a build that no longer exists and have to be run again on the
board before the paper can cite them. That is a re-measurement campaign, not a
port detail, and it is the main reason the port is not something to start
without deciding it explicitly.
