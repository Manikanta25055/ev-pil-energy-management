# A3, the A4 gate, and B7 on the board

**Run 2026-10-09, 04:51 to 08:20.** Branch `feature/sensor-arch`. Plan
stages P3 and P5 (`docs/2026-10-07-model-advancement-research.md`).
Sections 1 and 2 are SIMULATED on the laptop. Section 4 is MEASURED on the
board. Each says which.

## 1. A3: a better speed while the flag is up (SIMULATED)

**Data:** `docs/week13-a3-val.json`, `docs/week13-a3-test.json`
(`scripts/run_arch_study.py --a3`). The registered evaluation, 560 named
faults per row, clean cycles run for every row.

Week 13's first finding was that a reviewer which diagnoses well still
supervises badly, because the two speeds the loop can fall back on while a
sensor is flagged both drift: the dead-reckoned speed with the acceleration
channel's error, the model's prediction with whatever the model has wrong.
A3 puts the learned part inside the estimate instead of around it. While
flagged, the loop controls on a weighted mix of the two speeds. The weight
on the model is a constant, or it is a reviewer's probability that the
acceleration channel is degraded.

Validation (HWFET):

| Row | Caught in 0.5 s | Early releases | Flags stuck at 8 s | Worst peak error, m/s | Median peak error, worst case, m/s | Clean false alarms (floor + 10x) |
|---|---|---|---|---|---|---|
| A0, B7 alone (dead reckoning) | 551 | 212 | 14 | 3.74 | 0.56 | 0 + 0 |
| A2 monitor (switches between the two) | 551 | 115 | 10 | 1.24 | 0.24 | 0 + 0 |
| A3 fixed half-and-half | 551 | 215 | 1 | 5.96 | 0.39 | 0 + 0 |
| A3 fixed half-and-half, monitor holds and releases | 551 | 115 | 10 | 2.25 | 0.32 | 0 + 0 |
| A3 weight from the monitor | 551 | 115 | 10 | 1.24 | 0.24 | 0 + 0 |
| A3 weight from the GRU | 551 | 160 | 6 | 8.31 | 0.42 | 2 + 2 |
| A3 weight from FastGRNN | 551 | 48 | 0 | 2.49 | 0.28 | 2 + 0 |

Test (US06):

| Row | Caught in 0.5 s | Early releases | Flags stuck at 8 s | Worst peak error, m/s | Median peak error, worst case, m/s | Clean false alarms (floor + 10x) |
|---|---|---|---|---|---|---|
| A0, B7 alone (dead reckoning) | 533 | 188 | 32 | 5.10 | 0.58 | 0 + 0 |
| A2 monitor (switches between the two) | 533 | 122 | 5 | 1.41 | 0.47 | 0 + 0 |
| A3 fixed half-and-half | 533 | 195 | 2 | 7.95 | 0.48 | 0 + 0 |
| A3 fixed half-and-half, monitor holds and releases | 533 | 122 | 6 | 2.16 | 0.44 | 0 + 0 |
| A3 weight from the monitor | 533 | 122 | 4 | 1.41 | 0.47 | 0 + 0 |
| A3 weight from the GRU | 532 | 127 | 6 | 10.92 | 0.48 | 1 + 2 |
| A3 weight from FastGRNN | 533 | 59 | 1 | 12.85 | 0.38 | 4 + 1 |

**A3 did not produce a better fallback speed.** No mix beats the monitor's
plain switch on the worst case, on either split. A fixed half-and-half mix
is worse than either speed alone at its worst (5.96 and 7.95 m/s). A learned
weight leaves the same 8 to 13 m/s worst cases the learned reviewers had
with the switch. The one row that looked better on validation, FastGRNN's
weight (2.49 m/s, 48 early releases, no stuck flag), is the worst row on
test (12.85 m/s).

The A0 and A2 rows repeat the numbers of `docs/week13-arch-{val,test}.json`
to the last digit, which they should: the simulation is deterministic and
the blend is off by default.

What was not tried: an estimator that fuses the two speeds with their
uncertainties (a filter over both, not a mix of their outputs). The mixes
here weight two estimates that are each already wrong in their own way.

## 2. The A4 gate (SIMULATED evidence)

`docs/week13-a4-decision.json`. A4 is a bounded learned torque correction
around the PID, to be run only if a tracking error remains that estimation
does not explain. None was measured: the worst clean tracking RMSE with B7,
over every acceleration case, both noise levels and the heavier car, is
0.041 m/s against a bound of 0.1. The large errors are all while a flag is
up, and are errors of the speed the loop is given. A4 was not run.

## 3. B7 and the rule monitor in C

`firmware/main/control.c` (`control_b7_step`, `control_supervisor_step`),
selected by `-DSPEED_KALMAN=5` (B7) and `=6` (B7 with the monitor on the
chip, architecture A2). `tests/control/test_b7_c_parity.py` and
`test_monitor_c_parity.py` drive the C and the Python with the same 4,000
samples, four faults in them, at the noise floor and at ten times it, and
compare the estimate, the dead-reckoned speed, the offset estimate, the
flag, and what the monitor did to B7, on every step. Nine tests pass. The
thresholds in the header are tied to the Python ones by test.

One difference was found and removed on the way. Python keeps "seconds
flagged" as a running sum of 0.01 in double precision; in single precision
on the chip the same sum crosses 0.5 one step later. The C counts steps.

## 4. Injected faults on the board (MEASURED)

**Data:** `docs/week13-b7-pil.json`, from
`docs/week13-b7-pil-{b6,b7,b7mon}.json` (`scripts/run_b7_pil.py`,
`scripts/report_b7_pil.py`). ESP32-S3 on `/dev/cu.usbmodem101`, Arduino
build, rule energy manager in every image, `-DFAULT_INJECT=0
-DFALLBACK_ENABLED=1`. One run per cell.

No fault had been injected on the board before. Three images, 42 cells
each, from the registered test split: US06, the five named faults at two
onsets, under the white and the wander acceleration cases, at the noise
floor and ten times it (40 runs of 43 s), and the clean cycle under both
acceleration cases (2 runs of 600 s). The laptop simulates the car and
corrupts the two sensor channels; the estimator and the detector run on the
chip. Every run reported the estimator its arm needs and zero policy steps.

| | B6 | B7 | B7 + rule monitor |
|---|---|---|---|
| Faults flagged within 0.5 s | 33 of 40 | **40 of 40** | **40 of 40** |
| Worst delay, s | 5.18 | 0.32 | 0.32 |
| Median delay, s | 0.05 | 0.13 | 0.135 |
| Alarms before any fault | 220 | 0 | 0 |
| Flag dropped during the fault (up under 80% of it) | 2 | 16 | 10 |
| Still flagged in the run's last second | 21 | 0 | 0 |
| Worst tracking error through a fault, m/s | 1.93 | 0.67 | 0.61 |
| Median, m/s | 0.79 | 0.25 | 0.20 |
| False alarms on the two clean cycles (0.33 h) | 162 | **0** | **0** |
| Clean tracking RMSE, wander case, m/s | 3.48 | 0.013 | 0.013 |
| Clean energy, wander case, Wh/km | 205.9 | 190.6 | 190.6 |
| Late control steps | 0 | 0 | 0 |
| Worst control computation, us (of 10,000) | 72 | 74 | 78 |
| Image: flash / static RAM, bytes | 295,623 / 22,124 | 296,427 / 23,132 | 297,531 / 23,132 |

**On the chip, with a wandering acceleration channel, B6 does what the
simulation said it would**: 162 false alarms in one clean ten-minute cycle,
39% of the two clean cycles spent flagged, tracking error of 3.5 m/s RMS and
8% more energy with nothing wrong with the sensor. Under white acceleration
noise it is clean, as in week 12.

**B7 catches every injected fault within 0.32 s and raises nothing on a
healthy sensor**, for 2 us more computation than B6, 804 bytes of flash and
1,008 of RAM. The monitor on top costs 4 us and 1,104 bytes of flash more.

**The monitor's effect on the board is small and in the direction the
simulation gave**: fewer flags dropped during a fault (10 against 16), a
lower median tracking error (0.20 against 0.25 m/s), worst case 0.61
against 0.67. With 40 runs per arm and one run per cell, the worst-case
difference is not established.

The two B7 arms show the same clean tracking RMSE in the wander case to
every digit. Neither raised a flag and neither dropped a frame in that
cell, so both computed the same estimate on the same samples.

The same 40 cases through the simulation
(`docs/week13-b7-pil-sim.json`, different noise draws):

| | B6 | B7 | B7 + rule monitor |
|---|---|---|---|
| Flagged within 0.5 s, simulated | 24 | 38 | 38 |
| on the board | 33 | 40 | 40 |
| Worst tracking error, simulated, m/s | 2.22 | 0.73 | 0.67 |
| on the board | 1.93 | 0.67 | 0.61 |
| Median, simulated | 0.72 | 0.23 | 0.25 |
| on the board | 0.79 | 0.25 | 0.20 |

The board is no worse than the simulation on any line. The two faults the
simulation flags late are half-metre offsets at ten times the noise, B7's
known weak case; on the board's noise draws those eight runs were flagged
in 0.22 to 0.32 s.

### How the board numbers were taken, and how far to trust them

- The board reports its detector in a DIAG frame every 500 ms. The delay of
  an alarm comes from the control-loop count at which it was raised, good to
  a few steps (tens of milliseconds). Whether the flag is up is known only
  per 500 ms, so "dropped during the fault" and "still flagged" are coarser
  than the simulation's.
- No cell lost more than 10 frames; the week-12 limit for taking a cell
  again is 16. None was taken again.
- Each cell has one noise seed and was run once.
- The acceleration error is the simulated wander, not a real accelerometer.
- The board was left holding the normal actor image, built from the main
  checkout, and reported policy steps when asked.

## 5. What this adds up to

B7 is the result to keep from the sensor work: it replaces B6, it is in C,
it matches the Python step for step, and on the chip it met the detection
and false-alarm criteria on the cases run. It has still not passed the
registered criteria in simulation, where it is late on a few half-metre
offsets at ten times the noise.

Nothing learned earned a place on the board. The rule monitor did, weakly.

## 6. Not done

- Jev: not purchased. No row of this file is a Jev row.
- A real accelerometer. Everything about the acceleration channel's error
  is simulated from what the logged trips showed.
- The other four acceleration cases, the heavier car and drift faults on
  the board; repeats with other seeds.
- An estimator that fuses the two fallback speeds by their uncertainty.
- The learned reviewers on the board: not eligible, and not flashed.
- The 70-page report and the supervisor note do not carry any of this yet.
