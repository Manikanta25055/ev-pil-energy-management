# Work that is waiting on the board

**Raised:** 2026-09-02, when no board was attached.
**Updated:** 2026-09-02, when one was.

The ESP32-S3 is now connected on `/dev/cu.usbmodem1101`, MAC
`1c:db:d4:46:24:e8`, the same part recorded in `docs/hardware-inventory.md`.

Items 1, 2 and 4 have been run and are kept here as a record of how they
closed. Nothing in this file is waiting on hardware or on a decision any more.

What is left is item 3, the PIL campaign itself, which is work rather than a
blocker.

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

**Bracketed on 2026-09-11.** The closed-loop campaign was run at 1, 2, 3, 4
and 5 s on the Arduino build with the SAC actor in the loop, every length
afresh because the firmware had changed since the IDF runs. The worst case
goes to the ablation at 1 to 4 s and to the handling at 5 s, so the crossover
is between 4 and 5 s, as fine as a whole-second sweep resolves. No figure
inside that interval is measured or may be quoted. `docs/week9-a4.md` section
10. The counter campaign was repeated on the same build and reproduced: the
guarded counters read 0 under the ablation and the torque ramps out with the
handling in and holds flat without it.

## 2. The full stack on the device -- DONE

**Decided and run on 2026-09-02.** The supervisor chose to ship the SAC actor
without the forecaster. Results in `docs/week10-deployment.md`, data in
`docs/week10-fullstack.json`.

The firmware had never actually run either model: `ems_task` produced the rule
action on both of its branches and `infer_task` ran a dummy load. Making the
decision real needed the state frame extended with `t_batt_c` (the policy
observes pack temperature and nothing on the chip can derive it), the action
decode bounds exported with the weights, two new diagnostic counters, and the
actor wired into `ems_task` with the rules behind it.

Measured over 10 minutes: the actor answered 5,965 of 5,965 outer steps, the
rules never took over, `ctrl_late` stayed at 0, and the jitter distribution did
not move. Worst inference 825 us, which is a cold start rather than contention:
the figure was identical after one minute and after ten, over 565 inferences
and then 5,965. Steady-state cost is the bench's 0.123 ms.

Open, and stated so it is not mistaken for finished: `infer_task` still runs
its dummy load, which stands in for a forecaster that is no longer being
deployed. Core 1 is carrying a phantom and the deployed stack has more headroom
than these numbers show. It was left in place because that load is also the
vehicle for `-DFAULT_INJECT=1`, which is how week 7's overrun path and ablation
A4 were measured; removing it changes the conditions those results were taken
under.

## 3. The PIL campaign

Week 10 onward. **No longer blocked.** The board is attached, the toolchain is
settled, and item 2 is done, so this is the next piece of work rather than a
waiting one.

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
- G3's dropped-frame count went from 3 to 9 in 59,650 loops, two single
  samples. **Arduino half done 2026-09-11:** five 10-minute runs on the
  shipped image gave 16, 4, 6, 9, 9, pooled 8.8 per run, 95% interval 6.4 to
  11.8, `ctrl_late` 0 throughout. The IDF repeats were deferred by the user,
  so the toolchain comparison is still open.
- **DONE 2026-09-11.** Ablation A4 (counters and the closed-loop sweep), the
  week 7 fallback campaign and the watchdog were all repeated on the Arduino
  build. Every one reproduces; `docs/week10-arduino-port.md` section 4 has the
  figures.
