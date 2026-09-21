# Ablation A4, measured on hardware

**Date:** 2026-09-02
**Firmware:** `firmware/main/tasks.c`, built four ways
**Scripts:** `scripts/run_fallback.py` (counters),
`scripts/run_a4_closedloop.py` (control quality)
**Data:** `docs/week9-a4.json`, `docs/week9-a4-baseline.json`,
`docs/week9-a4-closed-on.json`, `docs/week9-a4-closed-off.json`,
`docs/week9-a4-closed-on-5s.json`, `docs/week9-a4-closed-off-5s.json`;
the Arduino-build sweep, 2026-09-11: `docs/week9-a4-arduino-{on,off}-{1,2,3,4,5}s.json`
**Prediction it is scored against:** `docs/week9-a4-prediction.md`

The board arrived. Ablation A4 has now been run, and so has its baseline.

Two campaigns, because the first one could not answer the question. The
counter campaign confirms that the handling is compiled out and that the limp
ramp runs on silicon, and every expectation written before the run holds. It
cannot say what the handling costs in control quality, because the harness it
inherits from G3 never closes the loop. Section 4 is that finding. Section 5 is
the closed-loop campaign written to replace it, and the answer.

Headline, at a 1.0 s outage: the prediction called the direction correctly and
the size badly. Switching the handling off tracks better, 0.125 m/s against
0.292 m/s at the median, a factor of 2.3 where a factor of twelve was
predicted. The prediction's claim that the two modes cannot be separated on
battery current is refuted, and section 6 shows the defect in its own code that
produced it.

Headline, at a 5 s outage: the crossover the handling exists for is real and
lands close to where the prediction put it. The worst case goes to the
handling, 7.386 m/s against 7.949 m/s, predicted 6.881 against 8.024. Section 7.
A4 is therefore not null, and it is not a verdict against the limp path
either.

---

## 1. What was run

Both halves were flashed and measured in one session, on one board, through
one harness. That pairing is new. Week 7 measured the handling-on build before
`RECOVERY_WINDOW_S` existed, so `docs/week7-fallback.json` carries no record of
what the torque command did after the outage closed, which is the window the
prediction cares about most.

| | handling on | handling off (A4) |
|---|---|---|
| Build | `-DFAULT_INJECT=1 -DFALLBACK_ENABLED=1` | `-DFAULT_INJECT=1 -DFALLBACK_ENABLED=0` |
| `evpil_fw.bin` | 0x32e20 | 0x32d90 |
| Output | `docs/week9-a4-baseline.json` | `docs/week9-a4.json` |

The ablation build is 144 bytes smaller. Two guarded branches leaving the image
is what that difference is.

One trap is worth recording because it nearly cost a run. `FALLBACK_ENABLED`
persists in `firmware/build/CMakeCache.txt`, and `main/CMakeLists.txt` tests it
with `if(DEFINED ...)`, which a cache entry satisfies. Rebuilding the baseline
with `-DFAULT_INJECT=1` alone therefore leaves the ablation switched on, and
the build log is the only place that says so. The baseline here passes
`-DFALLBACK_ENABLED=1` explicitly, and the build log line
`evpil: FALLBACK_ENABLED=1` was checked before it was flashed.

Board: ESP32-S3 QFN56 rev v0.2, MAC `1c:db:d4:46:24:e8`, on
`/dev/cu.usbmodem1101`. Same part as the week 7 and week 8 campaigns, on a
different USB enumeration.

## 2. The counters

Deltas over a 50 s run, 1.0 s of host silence injected at 8.0 s, an outer-loop
stall at 20.0 s and an inference overrun at 40.0 s.

| Counter | Guarded? | Expected under A4 | On | Off | |
|---|---|---|---|---|---|
| `ctrl_fallback_steps` | yes | exactly 0 | 180 | **0** | ok |
| `limp_steps` | yes | exactly 0 | 95 | **0** | ok |
| `ems_fallback_steps` | no | >= 5 | 20 | 20 | ok |
| `infer_deadline_misses` | no | >= 5 | 20 | 20 | ok |
| `stale_steps` | no | >= 50 | 102 | 102 | ok |
| `ctrl_late` | no | exactly 0 both modes | 0 | **0** | ok |
| `loop_count` | | | 4950 | 4950 | |

Every expectation holds. The two guarded counters read zero in the ablation and
move in the baseline, which is the ablation doing its job rather than the
firmware failing, and the pre-registered table is what lets those two readings
be told apart.

`ctrl_late` staying at zero in both builds settles the second of the
prediction's three falsification conditions. The fallback path does not cost
the control loop its own deadline, and neither does removing it, so the
comparison is between two loops that both met their timing.

Against week 7, `limp_steps` came in at 95 rather than 96 and `stale_steps` at
102 rather than 101. One step of jitter in where a 1.0 s host silence lands
against a 10 ms control period. Nothing turns on it.

## 3. What the torque command did

The mechanism the ablation removes is visible in the actuation stream, and it
is visible in the direction the firmware comment claims.

| | handling on | handling off (A4) |
|---|---|---|
| Command entering the outage | 226.07 Nm | 226.09 Nm |
| Command at the end of the 1.0 s window | **0.00 Nm** | **226.07 Nm** |
| Range across the window | 226.07 to 0.00 | 226.07 to 226.18 |

With the handling in, torque ramps out at 10 Nm per step and reaches zero
inside the window. With it compiled out, the loop holds its last command flat
for the whole second. That is the ablation working on silicon, and it is the
first direct confirmation that `LIMP_RAMP_NM` behaves on the board the way
`predict_a4.py` models it on the host.

## 4. The open loop cannot answer the question, and did not

The prediction's sharpest claim about the handling's cost is that it makes the
return harder: after limping to zero the loop has to catch up. Over the 2 s
after the host started answering, the two builds measured this way recover
identically, to within 0.11 Nm of peak, and the handling-on build climbs from
0 Nm back to 226 Nm in a single 10 ms step with no overshoot.

That is not a refutation. It is the harness reporting on a loop that was never
closed.

`scripts/run_g3.py:plant_state` is a closed-form function of the step index,
and `run_fallback.py` feeds it straight into the state frame, so the torque the
device commands never reaches the plant that answers it. Two consequences
follow:

1. **No tracking error can accumulate.** Torque going to zero for a second does
   not slow the simulated vehicle, because nothing connects the two. When the
   host answers again the speed is exactly where the closed form says it should
   be, so there is nothing to catch up to.
2. **The step index freezes during the silence.** `step` advances only when the
   host sends a frame, so the reference pauses along with the outage instead of
   running on ahead of the controller.

The G3 note explains why `plant_state` is closed-form, and the reasoning was
right for G3: replaying a real trip would add host-side work that varies per
step and would appear in the timing as jitter the loop did not cause. A4 is a
control-quality measurement borrowing a link-timing harness, and the property
that made the harness good for the first purpose disqualifies it for the
second.

So sections 2 and 3 stand as measured, and the prediction's headline number is
not among the things they settle. `scripts/run_a4_closedloop.py` closes the
loop, and section 5 is what it found.

## 5. The loop closed, and the prediction scored

`scripts/run_a4_closedloop.py` runs the same blackout against the same two
builds, with the validated plant from `docs/g2-plant-validation.md` stepped by
the torque, regen blend, power limit and auxiliary derate the board just sent.
The reference is a drive cycle. The board keeps sending actuation at 100 Hz
through the outage, so the plant keeps moving and the cycle keeps running on,
which is what a vehicle does when its link drops.

Built with `FAULT_INJECT=0`, so the host blackout is the only fault. Eight
onsets swept across US06, 1.0 s of silence each, 15 s lead-in, 2 s recovery,
the same windows `predict_a4.py` uses. The onset is swept rather than placed
once for the reason the prediction gives: a single onset can be chosen to
flatter either mode. Worst pre-blackout error across all sixteen runs was
0.127 m/s, so the loop was settled before every blackout.

**Data:** `docs/week9-a4-closed-on.json`, `docs/week9-a4-closed-off.json`.

| Onset, s | v_ref, m/s | On, peak err | Off, peak err | On, I recovery | Off, I recovery |
|---|---|---|---|---|---|
| 16.0 | 14.44 | 0.992 | **0.725** | 255.7 | **146.8** |
| 98.9 | 29.83 | 0.343 | **0.034** | 127.0 | **35.6** |
| 181.7 | 24.64 | **0.043** | 0.164 | **68.5** | 77.5 |
| 264.6 | 27.77 | 0.463 | **0.364** | 246.7 | **216.6** |
| 347.4 | 29.70 | 0.142 | **0.086** | 90.6 | **77.2** |
| 430.3 | 30.52 | 0.242 | **0.051** | 111.8 | **66.0** |
| 513.1 | 4.76 | 1.318 | **0.315** | 53.5 | 55.3 |
| 596.0 | 0.00 | 0.0017 | 0.0017 | 4.4 | 4.4 |
| **median** | | 0.292 | **0.125** | 101.2 | **71.6** |
| **worst** | | 1.318 | **0.725** | 255.7 | **216.6** |

![Ablation A4 measured](figures/week9-a4-measured.png)

*Paired bars, same eight onsets against each build. Drawn by
`scripts/plot_a4_measured.py`. Its companion `scripts/plot_a4.py` draws the
prediction, in the same two colours.*

Six of the eight onsets go to the ablation, one to the handling, and the last
is a standstill where the vehicle is stopped and neither mode does anything.

**The prediction's direction holds.** Switching the deadline-miss handling off
tracks better at a 1.0 s outage: median peak error 0.125 m/s against
0.292 m/s. That settles the condition the prediction staked itself on, and it
settles it the way the prediction said, against the obvious reading. Holding
the last command through a short outage is a better guess than ramping torque
to zero.

**The magnitude does not.** Predicted, the gap at 1.0 s was a factor of twelve,
0.031 m/s off against 0.363 m/s on. Measured, it is a factor of 2.3. The
handling-on half came in close to prediction, 0.292 against 0.363. Almost all
of the error is in the other half: holding a stale command was predicted to
cost 0.031 m/s and cost 0.125 m/s, four times worse. A deterministic, noiseless
host plant flatters the mode whose whole strategy is to freeze and wait, and
degrades nothing for the mode that ramps to a fixed value. The prediction's own
last caveat said the measured spread should come out wider than the swept-onset
spread, and it did.

## 6. The prediction was wrong about current, for a reason in its own code

Section 3 of `docs/week9-a4-prediction.md` says peak battery current is the
same in both modes to within 0.3 A, 158.9 A against 159.2 A, and concludes that
the electrical stress argument does not separate them and should not be used
to. On the board they separate clearly: peak recovery current 101.2 A with the
handling on against 71.6 A with it off at the median, and 255.7 A against
216.6 A at the worst.

The disagreement is not simulation against hardware. It is a scoping defect in
the prediction, visible by reading it. `predict_a4.py` updates `peak_i_a` on
every step from `k_start`, so its statistic covers the lead-in as well as the
event. The lead-in is fifteen seconds of drive cycle, identical in both modes
by construction, and on an aggressive cycle it contains the largest currents in
the run. That the two modes came out 0.3 A apart is a measurement of the
lead-in, not of the blackout. The closed-loop numbers above are scoped to the
recovery window on purpose, and the harness says so where it does it.

The measured lead-in peaks bear this out: 155.5 A with the handling on against
155.7 A with it off, a 0.2 A gap on the segment where the two modes are doing
the same thing, which is the gap the prediction reported for the whole run.

So at a 1.0 s outage the handling costs tracking, and it costs recovery current
too. Both are supposed to be the price of bounding the tail. Section 7 goes and
tests the tail.

## 7. The tail, at a 5 s outage

The reason the handling is in the firmware is the worst case, and the
prediction puts the crossover at a 5 s outage. Same campaign, same eight
onsets, `--blackout-s 5.0`.

**Data:** `docs/week9-a4-closed-on-5s.json`,
`docs/week9-a4-closed-off-5s.json`. Worst pre-blackout error 0.283 m/s.

| Onset, s | v_ref, m/s | On, peak err | Off, peak err | On, I recovery | Off, I recovery |
|---|---|---|---|---|---|
| 16.0 | 14.44 | 5.247 | **4.158** | 332.4 | **206.5** |
| 98.3 | 30.27 | 1.461 | **0.442** | 127.0 | **95.2** |
| 180.6 | 25.01 | **0.411** | 1.480 | 264.8 | **102.1** |
| 262.9 | 27.85 | 1.602 | **0.210** | 332.2 | **76.9** |
| 345.2 | 30.14 | **1.220** | 1.714 | 332.0 | 332.0 |
| 427.4 | 30.83 | 1.109 | **0.149** | 332.2 | **64.5** |
| 509.7 | 11.34 | 7.386 | **4.473** | 126.8 | **110.0** |
| 592.0 | 2.75 | **2.105** | 7.949 | **22.0** | 126.6 |
| **median** | | **1.532** | 1.597 | 298.4 | **106.0** |
| **worst** | | **7.386** | 7.949 | 332.4 | 332.0 |

![Ablation A4 measured at 5 s](figures/week9-a4-measured-5s.png)

**The crossover is real and it lands where the prediction put it.** At 5 s the
worst case goes to the handling, 7.386 m/s against 7.949 m/s. Predicted, that
row read 6.881 against 8.024. Both the direction and the size come out close,
which is the prediction's strongest showing anywhere in this ablation.

The mechanism is legible in one row. At onset 592.0 the cycle is winding down
to a stop, v_ref 2.75 m/s and falling. Holding a stale command there means
driving 5 s of torque into a vehicle that should be braking, and the ablation
records a 7.949 m/s excursion against the handling's 2.105. That single row is
the whole safety argument: not that limping tracks well, but that it fails
small when holding fails large.

**The median advantage has already gone by 5 s, earlier than predicted.**
Measured, the two modes are a near tie at the median, 1.532 on against 1.597
off, a 4% gap. Predicted, the median at 5 s was still a wide win for the
ablation, 1.764 against 0.636. So the ordinary-case cost of the handling, real
and reproducible at 1.0 s, has been paid back by 5 s rather than persisting to
10 s as the prediction has it. Per onset the ablation still wins five of eight;
what changed is that the three it loses, it loses badly.

Recovery current goes the other way and goes there hard. At the median the
handling draws 298.4 A against 106.0 A, and it saturates at 332 A on four of
the eight onsets. Ramping torque to zero for five seconds and then catching up
is expensive, and at this duration that cost is the handling's largest.

## 8. Where A4 stands

| Question | Status |
|---|---|
| Do the guarded branches leave the image? | **Measured.** 144 bytes, both counters zero |
| Does the limp ramp run on the board? | **Measured.** 226 Nm to 0.00 Nm across the window |
| Does either build miss its own deadline? | **Measured.** `ctrl_late` 0 in all six campaigns |
| Tracking cost at a 1.0 s outage | **Measured.** 0.292 on against 0.125 off, median |
| Recovery current at a 1.0 s outage | **Measured.** 101.2 on against 71.6 off, median |
| Does the handling buy the tail back? | **Measured.** Yes at 5 s, worst case 7.386 on against 7.949 off |
| Where exactly the crossover sits | **Bracketed, 2026-09-11.** Worst case between 4 and 5 s, on the Arduino build with the actor in the loop. Section 10 |

Claim C5 is carried by measurement in both halves. A miss is detected, handled
and counted rather than silently absorbed, and the degradation is quantified at
two outage durations, including the one where the handling stops being a cost
and starts being the reason it exists.

## 9. What is left

*Superseded by section 10 for the crossover.* The original text said two
durations could show the crossover exists but not locate it, and that running
2 s and 3 s would bracket it. That was done on 2026-09-11, on the Arduino
build.

The prediction's 10 s row is still untested, and its 0.2 s and 0.5 s rows are
below anything measured here.

## 10. The sweep, on the Arduino build with the actor in the loop

**Date:** 2026-09-11. **Data:** `docs/week9-a4-arduino-{on,off}-{1,2,3,4,5}s.json`.
**Figure:** `docs/figures/week9-a4-arduino-sweep.png`, drawn by
`scripts/plot_a4_sweep.py`.

Two things changed since sections 5 and 7, and both are why this is a new
campaign rather than two points added to the old one. The firmware is now
built by `scripts/arduino_build.sh` rather than the IDF, and, more important,
the SAC actor now drives the outer loop (week 10). Sections 5 and 7 ran with
the rule action on both branches of `ems_task`. So every duration was run
on the current image, 1 s and 5 s included, and **the IDF points are not
mixed with these on any axis.** The 4 s pair was added last, after the G3
repeats, to halve the bracket the first four lengths left.

Builds: `-DFAULT_INJECT=0 -DFALLBACK_ENABLED=1` and `-DFAULT_INJECT=0
-DFALLBACK_ENABLED=0`, both switches passed explicitly each time. Same eight
onsets per duration in both builds, 15 s lead-in, 2 s recovery. Every run
passed its counter checks and `ctrl_late` was 0 in all ten. Worst
pre-blackout error across all runs 0.283 m/s.

| Outage | Median on | Median off | Worst on | Worst off | Onsets won (off / on / tie) |
|---|---|---|---|---|---|
| 1 s | 0.289 | **0.122** | 1.089 | **0.714** | 6 / 1 / 1 |
| 2 s | 0.562 | 0.563 | 3.229 | **1.600** | 5 / 2 / 1 |
| 3 s | 0.820 | 0.831 | 5.188 | **2.469** | 6 / 2 / 0 |
| 4 s | **1.102** | 1.410 | 6.668 | **3.732** | 5 / 3 / 0 |
| 5 s | 1.533 | **1.361** | **7.394** | 7.948 | 5 / 3 / 0 |

Peak absolute speed error, m/s. A tie is a difference under 0.005 m/s, which
only the standstill onsets reach.

**The worst-case crossover lies between 4 and 5 s.** The ablation still has
the smaller worst case at 4 s, 3.732 m/s against 6.668, and the handling has
it at 5 s, 7.394 against 7.948. That is as fine as a whole-second sweep
resolves, and nothing inside it is measured: do not quote a crossover
duration, or any interpolated figure.

The swap is abrupt. At 4 s the ablation's worst case is still about half the
handling's; one second later it is 7% worse. The stopping row carries it: at
the onset near 593 s, where the cycle is braking to a halt, holding a stale
command costs 3.472 m/s at 4 s and 7.948 m/s at 5 s, while the handling's
figure there stays small (0.696 and 2.163).

The 5 s mechanism is the same row as section 7, onset 592.0 s, v_ref 2.75 m/s
and falling: 7.948 m/s with a stale command held against 2.163 with the
handling. The 1 s and 5 s tracking numbers with the handling on reproduce the
IDF ones closely (5 s median 1.533 against 1.532, worst 7.394 against 7.386),
so the actor did not move the limp path's tracking.

**The median does not settle, and should not be read.** A tie at 2 and 3 s,
the handling ahead at 4 s (1.102 against 1.410), the ablation ahead at 5 s
(1.361 against 1.533). With eight onsets per point the median is decided by
which onset lands in the middle, and these swings are noise around a small
gap. Section 7's IDF figure at 5 s was a near tie (1.597 off against 1.532
on). What holds on both campaigns is that the median gap is small from 2 s on
and the worst case is where the modes separate.

**Recovery current no longer saturates, and the reason is before the outage,
not in it.** With the handling on, the median recovery current at 5 s is
137.9 A against 298.4 A in section 7, and no onset reaches the 332 A ceiling
where four did. The lead-in shows why this is not an A4 effect. At onset
16.0 s the lead-in peak is 105.6 A on this image against 134.2 A on the IDF
one, and the lead-in is identical in both handling modes by construction. So
the current is being bounded by the outer loop, and the only thing that
changed in the outer loop is that the actor now sets the power limit and
regen blend. That is consistent with the actor commanding a tighter power
limit than the rule manager did; it is not proven, because `p_limit_w` is
consumed by the plant but not logged in the result files. The handling still
costs recovery current at every duration (median on above off at all four),
which is what section 6 found.

**The counter campaign reproduces on this build.** `run_fallback.py` against
`-DFAULT_INJECT=1` with the handling on and off, same day, same board.

| Counter | on, IDF | on, Arduino | off, IDF | off, Arduino |
|---|---|---|---|---|
| `ctrl_fallback_steps` | 180 | 180 | 0 | 0 |
| `limp_steps` | 96 | 94 | 0 | 0 |
| `ems_fallback_steps` | 20 | 20 | 20 | 20 |
| `infer_deadline_misses` | 20 | 20 | 20 | 20 |
| `stale_steps` | 101 | 107 | 102 | 108 |
| `ctrl_late` | 0 | 0 | 0 | 0 |
| Torque through the 1 s silence | 226.18 to 0.00 Nm | 226.18 to 0.00 Nm | flat at 226.07 Nm | flat at 226.07 Nm |

Data: `docs/week7-fallback-arduino.json` (on; the IDF "on" column is
`docs/week7-fallback.json`), `docs/week9-a4-arduino-counters.json` (off). Every
expectation written before the IDF run holds unchanged on this build.

What this section does not establish: a crossover duration, anything below
1 s or above 5 s, and whether the medians' sign at any length is stable. The last
would need repeat runs per duration, which were not done.

## 11. The three lengths the prediction tabulated and the board had never run

**Measured 2026-09-21**, same Arduino image as section 10, actor in the loop,
eight onsets per length, `-DFAULT_INJECT=0` and the fallback switch passed
explicitly in both directions. The sweep in section 10 stopped at 1 s and 5 s
because those were the lengths the earlier campaigns had used; the prediction
file tabulates 0.2 s, 0.5 s and 10 s as well, and none had been run on
hardware. They have now, so the measurement covers the whole predicted range.

| Outage | on, median | off, median | on, worst | off, worst | outages won, off / on / tie |
|---|---|---|---|---|---|
| 0.2 s | 0.037 | 0.026 | 0.096 | 0.150 | 4 / 3 / 1 |
| 0.5 s | 0.135 | 0.062 | 0.571 | 0.365 | 6 / 1 / 1 |
| 10 s | 3.579 | 4.470 | 13.216 | 24.704 | 4 / 4 / 0 |

Peak absolute speed error in m/s over the outage and the 2 s after it.

**The ten-second row is the strongest evidence the handling has anywhere.**
Worst case 13.216 m/s with it against 24.704 without, where at 5 s the two were
7.394 and 7.948. The individual outages split evenly, four each, which is the
point: the ablation wins the ordinary ones narrowly and loses the bad ones by a
wide margin. Its two worst are 24.704 m/s at the 505.4 s onset and 13.213 at
16.0 s, both places where `v_ref` is low and falling — the same mechanism
section 7 identified at 5 s, a stale torque command driving a vehicle that
should be braking. The handling's worst, 13.216 m/s at the 587.0 s onset, is
the same size as the ablation's *second* worst. Limping fails small; holding
fails large, and the gap widens with the outage.

**The 0.2 s row reverses the ordering and is not being called a crossover.**
The shipped firmware has the smaller worst case, 0.096 m/s against 0.150. Both
are tiny, the difference is 0.054 m/s, and each is whichever single onset of
eight happened to be worst. Section 10's rule applies unchanged: at eight
onsets these are not separable. The 4-to-5 s bracket is carried by an
identifiable row; this is not, and nothing here revises the bracket.

At 0.5 s the ordering is the familiar one — the ablation ahead on both median
and worst — so the handling's cost in ordinary tracking is already present at
half a second.

Recovery current at 10 s is the one figure that does *not* separate the modes:
126.7 A on against 127.0 A off at the median. Section 10 found the actor image
holding current down relative to the IDF runs, and at this duration the two
modes land on top of each other, which is consistent with the limit being set
by the outer loop rather than by the handling.

Data: `docs/week9-a4-arduino-{on,off}-{0.2,0.5,10}s.json`.

What this section does not establish: any crossover duration, the stability of
any median's sign, and anything about outages longer than 10 s.
