# Work that is waiting on the board

**Raised:** 2026-09-02, when no board was attached.
**Updated:** 2026-09-02, when one was.

The ESP32-S3 is now connected on `/dev/cu.usbmodem1101`, MAC
`1c:db:d4:46:24:e8`, the same part recorded in `docs/hardware-inventory.md`.

Items 1 and 4 have been run and are kept here as a record of how they closed.
Items 2 and 3 are outstanding and neither is waiting on the board. Item 2 is
waiting on the parked decision about what should ship, and item 3 waits on
item 2.

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

The tail was run too, at a 5 s outage, and the crossover is real: worst case
7.386 m/s with the handling on against 7.949 m/s with it off, against a
prediction of 6.881 and 8.024. Claim C5 is now carried by measurement in both
halves.

What is not measured is where between 1 s and 5 s the crossover sits. Only
those two durations were run, so no crossover duration may be quoted. Running
2 s and 3 s would bracket it, at about three minutes a build.

## 2. The full stack on the device

Also week 9. The board is no longer one of the two blockers, so this is now
waiting on one thing: the parked decision about what should ship at all. The
measured costs that decision turns on are already in hand, actor 19.3 KB and
0.121 ms, quantised forecaster 20.2 KB and 36.46 ms, so no further measurement
will settle it. Someone has to choose.

## 3. The PIL campaign

Week 10 onward. The board is here; item 2 is not settled, and this cannot
start until it is.

## 4. Anything the toolchain change forces to be re-measured -- DONE

**Settled and run on 2026-09-02.** The supervisor chose to port to the Arduino
ESP32 core. `scripts/arduino_build.sh` builds it, and G1, G3, G5 and the SAC
actor on chip were all re-measured against that build.

No verdict changed. G1 agrees with the IDF build to four significant figures,
G5 moves 3.9%, G3 still fails on the same criterion with an identical jitter
distribution and `ctrl_late` still 0, and the actor is 1.7% slower with the
same weight checksum. `docs/week10-arduino-port.md`.

Left open by that campaign, and stated so it is not mistaken for finished:

- Supply current was not re-measured. The Arduino core links WiFi and
  Bluetooth in and cannot be told not to. Nothing starts them, but the design
  spec's radio constraint covers current draw as well as timing, and only
  timing was checked.
- G3's dropped-frame count went from 3 to 9 in 59,650 loops. That is two
  single samples of a rare event and does not establish a rate. Five or more
  runs per toolchain would.
- Ablation A4 and the week 7 fallback campaign were measured on the IDF build
  the same day and have not been repeated on the Arduino one. The control
  task's timing is unchanged, so there is no reason to expect movement, but
  that is a reason to expect, not a measurement.
