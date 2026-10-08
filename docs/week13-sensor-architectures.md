# Sensor reliability: a realistic acceleration channel, B7, and the supervisory architectures

**Run 2026-10-08 evening to 2026-10-09 morning.** Branch `feature/sensor-arch`
(worktree `.worktrees/sensor-arch`), from `4bc4dd9`.
**Plan:** `docs/2026-10-07-model-advancement-research.md`, stages P1 and P2,
and the supervisory architectures of its section 12 with every reviewer that
exists today.

Everything here is SIMULATED on the laptop. No board run, no hosted model, no
API call. Jev is not purchased; its rows are empty, not estimated.

## 1. What was done

| Plan stage | State |
|---|---|
| P0 campaigns | closed before this work; nothing was left to run |
| P1 acceleration provenance, cases, stronger classical baseline | done: sections 2 to 4 |
| P2 tiny GRU, then FastGRNN | trained and evaluated: sections 5 to 7. Not ported to the board: no arm passed the registered criteria |
| Architectures A1, A2, A5, A6 with the non-Jev reviewers | done on validation, key rows on test: sections 6 to 8 |
| A1 with Jev itself (P4) | blocked: not purchased. The reviewer slot is ready for it |
| P3 learned estimator, P5 board campaign, P6 and P7 energy planning | not started |

## 2. The acceleration channel

The detector B6 was built against true acceleration plus white noise. On the
19 training-split i3 trips the logged acceleration and the acceleration the
speed implies differ by a slow component: median standard deviation
0.12 m/s^2 after a five-second average, forgetting itself in a median of
10.5 s. `src/evpil/control/accel_models.py` adds that to the simulated channel:

| Case | What is added to the channel |
|---|---|
| white | nothing: the week-11 assumption |
| offset | a constant 0.17 m/s^2, the worst trip's offset |
| wander | a slow random error, 0.12 m/s^2, 10.5 s |
| wander hard | the same at 0.20 m/s^2, 15 s |
| slope | gravity along a 0.03 rad sine grade, 120 s period |
| replay | a logged trip's own slow disagreement |

Replayed trips are disjoint by split: four training-split trips, four
validation-split trips, and for the test four trips no split has used. The
sealed i3 test trips were not read.

## 3. The registered evaluation

`src/evpil/control/sensor_eval.py`, fixed before any learned arm was trained.
Splits by cycle, trip and seed: train UDDS and WLTC, validation HWFET, test
US06. Five named faults (stuck, dropout, offsets of +0.5, -0.5 and +3.0 m/s)
and a drift, five seconds each, then eight seconds of healthy sensor; every
acceleration case on the nominal car and white noise on a car 10% heavier;
at the noise floor and at ten times it. Validation and test: 560 named fault
runs each. Clean cycles are run whole beside the filter B5 on the same noise.

Criteria, per acceleration case: every named fault flagged within 0.5 s;
fewer than one false alarm per clean hour at the floor; clean energy within
0.2% and clean tracking within 0.005 m/s of B5; no flag still up eight
seconds after the sensor returns; 95% of flags down within two seconds.

One departure from the week-11 fault study: a fault run starts 30 s before
its fault at the cycle's speed, not at the start of the cycle. It cuts the
run time by five.

## 4. B6 and B7

B7 (`BiasAwareFaultKalman`) is B6 with an offset state in the dead reckoning,
a step test (mean gap of the last 300 ms against the 300 ms before, so the
slow error cancels), and the dead reckoning's own error in the mean test's
threshold. Its step test was tuned on the training split only
(`docs/week13-b7-tuning.json`): of eight candidates the chosen one missed 0 of
120 half-metre offsets at 10x noise with one clean false alarm in 3.8 hours.

Validation, 80 named faults per case:

| Acceleration case | B6 caught in 0.5 s | B6 clean false alarms per hour | B6 share of clean driving flagged | B7 caught in 0.5 s | B7 clean false alarms |
|---|---|---|---|---|---|
| white | 80 | 0 | 0% | 79 | 0 |
| white, car 10% heavier | 80 | 0 | 0% | 79 | 0 |
| offset | 22 | 4651 | 82% | 79 | 0 |
| wander | 25 | 1343 | 80% | 78 | 0 |
| wander hard | 15 | 44 | 98% | 78 | 0 |
| slope | 2 | 293 | 93% | 79 | 0 |
| replay | 25 | 1438 | 75% | 79 | 0 |

**B6 works only on the channel it was designed against.** On the other five
it is flagged for most of a healthy drive, and because the loop then runs on
its drifting dead-reckoned speed, clean tracking error reaches 6 to 41 m/s.
This is the simulation saying what the logged trips said in week 12.

**B7 has no false alarm in 4.5 clean hours at the floor or at 10x, in any
case, and catches 551 of 560 faults in time.** It does not pass the
registered criteria: the nine it misses are +0.5 m/s offsets at ten times
the noise, flagged only when they end. Its other weaknesses are what the
supervisory layer was then aimed at:

- 212 early releases. A half-metre offset that persists is let back in after
  one to two seconds, because the band a returning sensor must sit in has to
  widen as the dead reckoning ages.
- 14 flags still up eight seconds after the sensor returned, 10 of them
  under hard wander.
- A worst tracking error through a fault of 3.74 m/s: five seconds on a dead
  reckoning that the acceleration error is pulling away.

## 5. The architectures and the reviewer slot

`src/evpil/control/supervisor.py`. B7 and the PID stay on the fast path at
10 ms. Each 100 ms block is summarised in twelve numbers the chip already
holds (the gap to the dead-reckoned speed, the gap to the vehicle model's
prediction, their difference, the noise level, the offset estimate, and so
on). A reviewer answers with a probability for each of four diagnoses:
healthy, sensor fault, acceleration channel degraded, both. Its answer
travels through a channel with a delay, jitter, loss and outages, is
checked for age and for whether the flag has changed since it was asked,
and can then change four bounded settings of B7 and nothing else: hold a
raised flag, release it, fall back on the model instead of the dead
reckoning, or tighten the tests. A reviewer never sees the true speed and
never commands torque. With no usable answer B7 runs as it would alone,
which a test asserts bit for bit.

| | Where the reviewer runs | Channel |
|---|---|---|
| A0 | none | |
| A2 | on the chip | no delay |
| A1 | behind a link (the post-action review proposed for Jev) | 70, 150, 500, 1000 ms, 20% jitter |
| A1e | as A1 at 150 ms | asked only when something is up |
| A1c | as A1 at 150 ms | an answer reused for 5 s |
| A1x | as A1 at 150 ms | a fifth of answers lost; link down from 20 s to 40 s, which covers the fault |
| A6 | a larger model on a nearby host | 5 ms |
| A5 | a fast reviewer on the chip and the larger one at 150 ms | both |

The delays are fixtures. None is a measurement of a service.

Reviewers:

| Reviewer | What it is | Parameters | Weights |
|---|---|---|---|
| monitor | two references, one vote, written by hand: the control every other reviewer has to beat | none | |
| gru16 | tiny GRU, 12 inputs, 16 states, 4 outputs | 1,508 | 5.9 KiB |
| fastgrnn16 | FastGRNN cell, same shape | 550 | 2.1 KiB |
| gru64 | the "host" model: a GRU of 64 states | 15,236 | 59.5 KiB |
| Jev | not purchased | | |

On-chip memory and execution time are NOT measured for any of them. The cell
is ported to C (`firmware/main/reviewer.c`) and agrees with the Python cell
to 1e-4 on the host; it is not called from the firmware.

## 6. Shadow scores: diagnosis without acting on it

`docs/week13-arch-shadow.json`. 540,960 validation blocks from 714 runs with
B7 alone in the loop. Sensor-fault columns are per block.

| Reviewer | Accuracy | Brier | Calibration error | Fault recall, flag up | Fault recall, flag down | Fault false positives | Channel-degraded recall | Channel false positives |
|---|---|---|---|---|---|---|---|---|
| always healthy | 0.819 | 0.362 | 0.181 | 0.00 | 0.00 | 0.00% | 0.00 | 0.0% |
| monitor | 0.612 | 0.769 | 0.382 | 0.94 | 0.01 | 1.24% | 0.96 | 42.3% |
| gru16, first attempt | 0.879 | 0.188 | 0.030 | 0.28 | 0.00 | 0.86% | 0.71 | 3.8% |
| fastgrnn16, first attempt | 0.823 | 0.299 | 0.063 | 0.49 | 0.00 | 1.69% | 0.00 | 0.0% |
| gru16 | 0.882 | 0.168 | 0.026 | 0.99 | 0.88 | 0.95% | 0.91 | 11.3% |
| fastgrnn16 | 0.847 | 0.449 | 0.306 | 0.99 | 0.84 | 0.81% | 0.56 | 10.9% |
| gru64 | 0.894 | 0.156 | 0.013 | 1.00 | 0.89 | 0.75% | 0.92 | 10.2% |

The first attempt at training was wrong in two ways, both found from its
scores, not from the test split. Training cut each run into 300-block
pieces, and a fault run's fault starts at block 300: every fault was learned
from an empty state. And the inputs included speed and torque, which differ
between the training cycles and the highway validation cycle; validation
loss rose from the first epoch while training loss fell. The models in the
last three rows ("v3" in the files) keep a fault run whole, are trained on
four times the fault onsets, drop speed and torque, and weight the classes
by inverse frequency. Two intermediate attempts are in the JSON.

A learned reviewer that scores this well on runs that all have their fault
30 s in could be counting. `scripts/check_reviewer_lead.py` re-records the
runs with the fault 12 s and 47 s in: the GRU's recall is 0.955, 0.948 and
0.941. It is reading the fault.

**As diagnosticians the learned reviewers beat the monitor clearly**: the
same recall with the flag up, 88% against 1% with it down, fewer false
positives, and they are calibrated where the monitor is not. FastGRNN is
the exception on calibration and on the channel diagnosis.

## 7. In the loop: validation

`docs/week13-arch-val.json`, 560 named faults per row. "Early releases" are
flags dropped while the fault was still there. Peak error is the largest
tracking error from the fault's onset to the end of the run; the median is
that of the worst acceleration case. Clean cycles were run for the rows that
show a count.

| Row | Caught in 0.5 s | Early releases | Flags stuck at 8 s | Worst peak error, m/s | Median peak error, worst case, m/s | Clean false alarms (floor + 10x) |
|---|---|---|---|---|---|---|
| A0, B7 alone | 551 | 212 | 14 | 3.74 | 0.56 | 0 + 0 |
| control: always "healthy" | 551 | 327 | 0 | 3.52 | 0.63 | 0 + 0 |
| A2 monitor | 551 | 115 | 10 | 1.24 | 0.24 | 0 + 0 |
| A2 gru16 | 551 | 157 | 6 | 9.68 | 0.45 | 2 + 2 |
| A2 fastgrnn16 | 551 | 48 | 0 | 3.00 | 0.39 | 2 + 0 |
| A1 monitor, 70 ms | 551 | 115 | 3 | 1.11 | 0.25 | not run |
| A1 monitor, 150 ms | 551 | 113 | 3 | 1.00 | 0.25 | 0 + 0 |
| A1 monitor, 500 ms | 551 | 115 | 1 | 1.43 | 0.30 | not run |
| A1 monitor, 1000 ms | 551 | 212 | 4 | 3.24 | 0.55 | not run |
| A1 gru16, 70 ms | 551 | 155 | 36 | 12.76 | 0.46 | not run |
| A1 gru16, 150 ms | 551 | 147 | 26 | 10.90 | 0.48 | 2 + 1 |
| A1 gru16, 500 ms | 551 | 103 | 5 | 11.42 | 0.48 | not run |
| A1 gru16, 1000 ms | 551 | 212 | 0 | 2.07 | 0.56 | not run |
| A1 fastgrnn16, 70 ms | 551 | 46 | 0 | 3.04 | 0.40 | not run |
| A1 fastgrnn16, 150 ms | 551 | 112 | 0 | 2.53 | 0.48 | 2 + 0 |
| A1 fastgrnn16, 500 ms | 551 | 141 | 0 | 2.28 | 0.55 | not run |
| A1 fastgrnn16, 1000 ms | 551 | 212 | 0 | 2.07 | 0.58 | not run |
| A1e monitor / gru16 / fastgrnn16 | 551 | 113 / 143 / 53 | 3 / 12 / 0 | 1.06 / 12.35 / 3.16 | 0.27 / 0.45 / 0.43 | not run |
| A1c monitor / gru16 / fastgrnn16 | 551 | 113 / 147 / 112 | 3 / 26 / 0 | 1.00 / 10.90 / 2.53 | 0.25 / 0.48 / 0.48 | not run |
| A1x monitor / gru16 / fastgrnn16 | 551 | 212 / 212 / 212 | 2 / 0 / 0 | 2.95 / 2.95 / 2.95 | 0.56 / 0.56 / 0.56 | not run |
| A6 gru64, 5 ms | 555 | 67 | 9 | 9.69 | 0.39 | 4 + 5 |
| A5 monitor + gru64 | 551 | 46 | 0 | 3.23 | 0.38 | not run |
| A5 gru16 + gru64 | 551 | 46 | 0 | 3.23 | 0.38 | not run |

No row passes the registered criteria in all seven cases: none recovers the
nine late detections, which are B7's. A6 recovers four of them and passes
two cases, at the price of nine clean false alarms.

What the table says:

1. **The hand-written monitor is the best reviewer in the loop.** On the
   chip it halves B7's early releases, and cuts the worst tracking error
   through a fault from 3.74 to 1.24 m/s and the median from 0.56 to 0.24,
   with no clean false alarm.
2. **The better diagnosticians are the worse supervisors.** The GRU, right
   about the fault 99% of the time, holds a half-metre offset out for the
   whole five seconds. For those five seconds the loop runs on dead
   reckoning or on the model, and both drift further than the half metre
   they were protecting against: 2 to 3 m/s at ten times the noise, and
   9.4 m/s in one run at the noise floor where the flag was held for about
   twelve seconds. Fewer early releases is not the goal; it only looked
   like one.
3. **Delay costs little up to 500 ms and everything at 1 s.** At 1000 ms an
   answer is older than its 1.5 s expiry by the time a second one could
   follow, and the row is B7 alone. An outage across the fault is also B7
   alone, as designed: nothing breaks when the link does.
4. **Reusing an answer changed nothing** (A1c equals A1): a fresh answer
   arrives every block anyway. Asking only on events changed little.
5. **A second, larger reviewer adds nothing to the small one** (the two A5
   rows are identical: the slow reviewer's answer is the one used).
6. **The first-attempt GRU did harm** (313 early releases, 159 stuck flags,
   16.6 m/s). It is in the JSON as `A2 gru16`.

### One setting at a time

Reviewer on the chip, only one of the four settings allowed.

| | Monitor | gru16 | fastgrnn16 |
|---|---|---|---|
| hold only: early releases / stuck / worst peak | 115 / 30 / 3.80 | 155 / 28 / 3.74 | 47 / 10 / 3.74 |
| release only | 212 / 2 / 3.66 | 214 / 0 / 2.11 | 212 / 0 / 2.65 |
| fallback only | 215 / 54 / 14.77 | 214 / 40 / 14.77 | 214 / 56 / 14.88 |
| vigilance only | 212 / 14 / 3.74 | 212 / 14 / 3.74 | 212 / 14 / 3.74 |
| all four, hold limited to 2 s | 215 / 0 / 1.22 | 215 / 0 / 1.00 | 214 / 0 / 1.01 |

- **Falling back on the model, alone, is dangerous**: 14.8 m/s, with every
  reviewer. Why the model's prediction leaves the truth that far was not
  examined; the suspect is the unknown-acceleration state it carries with no
  measurement to correct it. It helps only together with a release that
  ends the episode.
- **Tightening the tests on a suspicion did nothing** for the on-chip
  reviewers. Only the larger model used it to effect, and it paid in false
  alarms.
- **With the hold limited to two seconds the three reviewers are the same
  on this split**: worst peak about 1 m/s, no stuck flag. The monitor's
  median (0.38) is still the lowest, and its default row (0.24) is lower
  again. The test split does not repeat this for the learned reviewers:
  section 8.

## 8. Test split

`docs/week13-arch-test.json`, `docs/week13-sensor-b6-test.json`. US06, with
replayed trips never used before. The rows were named before the split was
opened: the on-chip and 150 ms and 500 ms rows for each reviewer, A6, A5,
and the two-second-hold rows.

B6 and B7, 80 named faults per case:

| Acceleration case | B6 caught in 0.5 s | B6 clean false alarms per hour | B6 share of clean driving flagged | B7 caught in 0.5 s | B7 clean false alarms |
|---|---|---|---|---|---|
| white | 80 | 0 | 0% | 76 | 0 |
| white, car 10% heavier | 80 | 0 | 0% | 76 | 0 |
| offset | 12 | 1127 | 94% | 76 | 0 |
| wander | 19 | 1211 | 79% | 76 | 0 |
| wander hard | 9 | 232 | 94% | 77 | 0 |
| slope | 9 | 205 | 93% | 76 | 0 |
| replay | 34 | 814 | 78% | 76 | 0 |

B7's clean hours on this split are short: 0.83 at the floor per case, 5.8 in
all, and the same again at 10x. No false alarm in them.

The architectures, 560 named faults per row:

| Row | Caught in 0.5 s | Early releases | Flags stuck at 8 s | Worst peak error, m/s | Median peak error, worst case, m/s | Clean false alarms (floor + 10x) |
|---|---|---|---|---|---|---|
| A0, B7 alone | 533 | 188 | 32 | 5.10 | 0.58 | 0 + 0 |
| control: always "healthy" | 533 | 309 | 0 | 3.38 | 0.95 | 0 + 0 |
| A2 monitor | 533 | 122 | 5 | 1.41 | 0.47 | 0 + 0 |
| A1 monitor, 150 ms | 533 | 122 | 14 | 1.48 | 0.48 | 0 + 0 |
| A1 monitor, 500 ms | 533 | 122 | 3 | 1.62 | 0.53 | not run |
| A2 gru16 | 532 | 113 | 4 | 10.77 | 0.54 | 1 + 2 |
| A1 gru16, 150 ms | 529 | 104 | 11 | 10.00 | 0.53 | 1 + 2 |
| A1 gru16, 500 ms | 534 | 87 | 4 | 10.68 | 0.57 | not run |
| A2 fastgrnn16 | 533 | 59 | 1 | 12.84 | 0.43 | 4 + 1 |
| A1 fastgrnn16, 150 ms | 533 | 97 | 1 | 12.84 | 0.55 | 5 + 1 |
| A1 fastgrnn16, 500 ms | 533 | 123 | 0 | 3.40 | 0.54 | not run |
| A6 gru64 | 549 | 58 | 8 | 11.40 | 0.60 | 2 + 0 |
| A5 monitor+gru64, 150 ms | 534 | 38 | 4 | 5.80 | 0.55 | not run |
| A5 gru16+gru64, 150 ms | 534 | 38 | 4 | 5.80 | 0.55 | not run |
| A2 monitor hold 2 s | 533 | 196 | 0 | 1.41 | 0.54 | 0 + 0 |
| A2 gru16 hold 2 s | 532 | 196 | 3 | 12.40 | 0.55 | 1 + 2 |
| A2 fastgrnn16 hold 2 s | 533 | 197 | 1 | 12.84 | 0.55 | 4 + 1 |

The test split repeats the validation split where it matters and departs
from it in two places.

- **B6 fails every realistic acceleration case again, and B7 holds**: 533 of
  560 in time, no clean false alarm. US06 is harder on B7 than the highway
  cycle (27 late against 9), and it leaves more flags stuck (32 against 14).
- **The monitor is again the best reviewer in the loop**: worst peak error
  5.10 to 1.41 m/s, stuck flags 32 to 5, no clean false alarm, and the same
  at 150 ms and 500 ms of delay.
- **The learned reviewers are again worse than the monitor, and here worse
  than B7 alone on the worst case**: 10 to 13 m/s, with clean false alarms
  the monitor does not have.
- **Departure 1: the two-second hold did not rescue the learned reviewers.**
  On validation it brought all three to about 1 m/s. On test the GRU and
  FastGRNN rows stay at 12 m/s; only the monitor's is 1.41. Section 7's
  reading that the limit, not the reviewer, sets the outcome does not
  survive the test split. Which runs produce the 12 m/s was not examined.
- **Departure 2: the larger model on a nearby host recovers more late
  detections here** (549 against 533), still with an 11 m/s worst case and
  two clean false alarms.

Not one row passes the registered criteria in all seven cases, on either
split.

## 9. What this does and does not show

It shows that the acceleration channel B6 relied on was the whole of its
result, and that a classical detector (B7) can be made to live with a
realistic one: no false alarm in the clean hours run, and nearly every
abrupt fault caught.

It shows that a tiny recurrent model can diagnose a sensor fault from twelve
numbers per 100 ms far better than a hand-written rule, in 2 to 6 KiB of
weights.

It does not show that this helps the vehicle. In the loop the hand-written
monitor did better than every learned reviewer, in every architecture, on
both splits. On validation the cause was traced: the settings a diagnosis
can change do not include one that makes holding a small offset out worth
its cost, because the speeds the loop falls back on drift. A better fallback
speed would change that, and it is an estimator question (plan stage P3),
not a reviewer question. The learned reviewers also raise clean false alarms
through the tightened tests, which the monitor never does.

One reviewer in a supervisory seat is worth keeping from this: the rule
monitor around B7, on the chip or up to half a second away. It is the
candidate for the C port and a board run. It has not passed the registered
criteria, because B7 underneath it has not.

It says nothing about Jev. The slot it would fill was exercised by other
models with test delays. From these rows, what a hosted reviewer would have
to do to earn its place is specific: diagnose no worse than the 16-state
GRU, answer inside about half a second, and bring information the twelve
numbers do not carry. Whether it does is not known.

Not done: any board run, on-chip memory or timing, B7 in C, repeats of
training with other seeds, and energy planning. Drift faults are run but are
not in the criteria: B7 flagged 31 of 64 within 0.5 s in the three
acceleration cases checked on validation, and a slow drift is what its step
test is weakest against.

## 10. Files

| | |
|---|---|
| `src/evpil/control/accel_models.py` | the acceleration-channel errors |
| `src/evpil/control/speed_estimators.py` | `BiasAwareFaultKalman` (B7) |
| `src/evpil/control/sensor_eval.py` | registered cases, splits, criteria |
| `src/evpil/control/supervisor.py` | architectures, channel, policy, rule monitor |
| `src/evpil/control/tiny_rnn.py`, `firmware/main/reviewer.c` | the learned cells, Python and C |
| `scripts/tune_bias_aware.py`, `run_sensor_eval.py`, `build_reviewer_data.py`, `train_reviewer.py`, `score_reviewers_shadow.py`, `check_reviewer_lead.py`, `run_arch_study.py`, `report_arch_study.py` | the runs |
| `models/reviewer/` | the three trained reviewers and their training records |
