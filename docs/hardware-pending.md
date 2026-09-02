# Work that is waiting on the board

**Raised:** 2026-09-02, when no board was attached.
**Updated:** 2026-09-02, when one was.

The ESP32-S3 is now connected on `/dev/cu.usbmodem1101`, MAC
`1c:db:d4:46:24:e8`, the same part recorded in `docs/hardware-inventory.md`.
Item 1 has been run and is kept here as a record of how it closed. Items 2 to 4
are still outstanding, and none of the three is waiting on the board any more.
Two are waiting on a decision and one on the item before it.

Sections still marked outstanding contain no measurements. No number in them
may be cited until the run that produces it has happened.

---

## 1. Ablation A4, deadline-miss handling on vs off -- DONE

**Run on 2026-09-02.** Results in `docs/week9-a4.md`. Nothing in this section
is outstanding any more; it is kept because the way it closed is worth the
record.

Two campaigns were needed, not one.

The campaign this file described ran and passed. Every counter expectation
written in advance held: the two guarded counters read exactly zero in the
ablation and moved in the baseline, `ctrl_late` stayed at 0 in both builds, and
the torque command held flat at 226 Nm through the outage instead of ramping to
zero. Data in `docs/week9-a4.json` and `docs/week9-a4-baseline.json`. The
baseline was re-run rather than compared against week 7, because week 7 predates
the recovery window and never recorded it.

That campaign could not settle the prediction. `run_fallback.py` inherits
`run_g3.py:plant_state` for its state frames, a closed-form function of the
step index, so the torque the board commands never reaches the plant that
answers it. With the loop open no tracking error can accumulate, and peak speed
error, which is the quantity the prediction is staked on, is not observable at
all.

`scripts/run_a4_closedloop.py` was written to close it: the validated plant,
stepped with the torque the board just sent, against a drive-cycle reference,
eight onsets swept across US06. Result at a 1.0 s outage, median peak error
0.292 m/s with the handling on against 0.125 m/s with it off. The prediction's
direction holds and its factor of twelve comes out as a factor of 2.3. Its
claim that battery current cannot separate the two modes is refuted, by a
scoping defect in `predict_a4.py` that section 6 of the results note sets out.

Still not measured, and now the only part of C5 that is not: the tail. The
prediction puts the crossover at a 5 s outage, where the handling is supposed
to earn its cost back. `run_a4_closedloop.py --blackout-s 5.0` is the run, with
onsets re-chosen so the outage and its recovery fit inside the cycle.

## 2. The full stack on the device

Also week 9. The board is no longer one of the two blockers, so this is now
waiting on one thing: the parked decision about what should ship at all. The
measured costs that decision turns on are already in hand, actor 19.3 KB and
0.121 ms, quantised forecaster 20.2 KB and 36.46 ms, so no further measurement
will settle it. Someone has to choose.

## 3. The PIL campaign

Week 10 onward. The board is here; item 2 is not settled, and this cannot
start until it is.

## 4. Anything the toolchain change forces to be re-measured

If the firmware moves from ESP-IDF to the Arduino ESP32 core (see the open
question in `docs/toolchain-arduino-cli.md`), then G1, G3 and G5 were all
measured against a build that no longer exists and have to be run again on the
board before the paper can cite them. That is a re-measurement campaign, not a
port detail, and it is the main reason the port is not something to start
without deciding it explicitly.
