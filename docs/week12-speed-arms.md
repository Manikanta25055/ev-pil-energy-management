# The speed-loop arms on the board

**Run 2026-10-07, 03:05 to 06:55.** Arduino build, `-DFAULT_INJECT=0
-DFALLBACK_ENABLED=1`, rule manager for energy in every arm (no actor in the
image). Board on `/dev/cu.usbmodem101`.
**Data:** `docs/week12-speed-arms-{b0,b5,b6}.json`, summary and verdicts in
`docs/week12-speed-arms.json` from `scripts/report_speed_arms.py`.
**Firmware:** commits `24b6ba5` and `bb9a32f`.

MEASURED on the board unless a line says otherwise. One run per cell.

## 1. What was run

Three images that differ in one thing: what turns the measured speed into the
speed the 10 ms loop controls on.

| Arm | Build switch | What it is |
|---|---|---|
| b0 | `SPEED_KALMAN=0` | the loop as shipped: the raw measurement |
| b5 | `SPEED_KALMAN=3` | two-state Kalman estimate: speed, and acceleration the model does not know about |
| b6 | `SPEED_KALMAN=4` | b5 with the speed-sensor fault detector on top |

Six cells each: the three cycles at the noise floor, then US06 at the floor,
three times and ten times the sensor noise. The noise is on every measured
channel, acceleration included, as in the week-10 campaign. Every run reported
the estimator its arm needs (`speed_est_mode` in the DIAG frame), no cell had
more than 16 dropped frames, and none needed taking again.

b0 was measured again rather than taken from the corrected campaign of the
night before, because the image is not the same one.

## 2. Energy

Wh/km on the comparable scale.

| Cell | b0 | b5 | b6 |
|---|---|---|---|
| Urban (UDDS), floor | 168.10 | 168.05 | 167.99 |
| Highway (HWFET), floor | 153.98 | 153.92 | 153.92 |
| US06, floor | 190.79 | 190.61 | 190.59 |
| US06, floor (second seed) | 190.98 | 190.56 | 190.63 |
| US06, 3x noise | 191.27 | 190.67 | 190.54 |
| US06, 10x noise | 200.42 | 190.80 | 190.79 |

**Ten times the sensor noise costs the shipped loop 9.44 Wh/km
(4.9%). It costs b5 0.24 and b6 0.16.** Both arms recover
the whole of the penalty, 102% and 102% of it; the two points above a hundred are
the small amount they also save at the floor.

At the floor the arms are within 0.10% of the shipped loop on all three cycles,
always on the lower side. That is the same size as the difference between the
shipped loop's own two US06 floor cells (0.10%), so it is not a
saving this campaign can claim.

The simulation of 2026-10-06 put the shipped loop's 10x penalty at 9.74 Wh/km
and b5's energy at 10x at 190.58 Wh/km (`docs/week11-speed-arms.json`). The board
gives 9.44 and 190.80. The simulation's noise was on speed alone and the board's
is on every channel, so the agreement is closer than the two set-ups are alike.

## 3. Peak battery current

| Cell | b0, A | b5, A | b6, A |
|---|---|---|---|
| Urban (UDDS), floor | 118 | 111 | 110 |
| Highway (HWFET), floor | 97 | 92 | 92 |
| US06, floor | 284 | 262 | 261 |
| US06, floor (second seed) | 295 | 260 | 263 |
| US06, 3x noise | 330 | 273 | 265 |
| US06, 10x noise | 341 | 288 | 286 |

The shipped loop's peak climbs with noise to 341 A. The estimators hold it at 288 A or below.

## 4. Tracking

RMSE in m/s.

| Cell | b0 | b5 | b6 |
|---|---|---|---|
| Urban (UDDS), floor | 0.0104 | 0.0193 | 0.0119 |
| Highway (HWFET), floor | 0.0055 | 0.0035 | 0.0031 |
| US06, floor | 0.0161 | 0.0112 | 0.0103 |
| US06, floor (second seed) | 0.0271 | 0.0086 | 0.0144 |
| US06, 3x noise | 0.0124 | 0.0163 | 0.0095 |
| US06, 10x noise | 0.0257 | 0.0249 | 0.0254 |

Every cell is under 0.03 m/s. Read nothing finer than that into this table.
The shipped loop's two US06 floor cells are the same setting with a different
noise seed and read 0.0161 and 0.0271: a difference of 0.011 m/s with nothing
changed. Week 10 found the same thing, tracking error repeating to no better
than a quarter of itself.

## 5. Cost on the chip

| | b0 | b5 | b6 |
|---|---|---|---|
| Worst control computation, us | 62 | 69 | 73 |
| Late control steps | 0 | 0 | 0 |

Of a 10,000 us period. The fault detector costs 11 us more than nothing at
all.

## 6. The fault detector on a healthy sensor

**One false alarm in 1.26 hours.** It was in the urban cell, and the flag
was up for 50 control steps, which is the shortest the detector's own
recovery rule allows: it went up and came straight back down.

The design's limit is fewer than one false alarm per hour of clean driving.
One in 1.26 hours is 0.79 per hour, under the limit by less than the data can
support: a single event in a little over an hour. The simulation ran 3.8 hours
of clean driving, 1.9 of them on this cycle, with none
(`docs/week12-fault-arms-b6.json`).

**The cause is not established.** The campaign records how many times the
flag went up, not when or which of the detector's three tests raised it. The
urban cycle is the one with standstills and launches, and it also had the most
late host replies of b6's six cells (10), and either could be involved.
Section 9 says what would settle it.

## 7. Against the criteria

The criteria are the design's section 7.3, as `scripts/report_speed_arms.py`
applied them. The script and its tests were committed before the campaign
finished (`cdee36b`).

| Criterion | b5 | b6 |
|---|---|---|
| Clean energy within 0.2% of b0 | pass | pass |
| Clean tracking within 0.005 m/s of b0 | FAIL | pass |
| At least half of the 10x penalty recovered | pass | pass |
| Tracking under 0.1 m/s in every cell | pass | pass |
| No late control step | pass | pass |
| No false alarm on a healthy sensor | n/a | FAIL (1) |

Two failures, and they are not the same kind.

b5 fails clean tracking on one cycle: urban, 0.0193 against 0.0104, a gap of
0.0089 m/s where the bound is 0.005. On the other two cycles it tracks
better than the shipped loop. The gap is smaller than the 0.011 m/s by which
the shipped loop differs from itself, so the bound is tighter than one run per
cell can resolve. It is recorded as a failure because the bound was fixed
first.

b6's false alarm is a real event and is not explained.

## 8. What this does and does not show

It shows that the sensor-noise energy loss is real on hardware, is in the
speed loop, and is removed by a filter that costs under 12 us. That was a
simulated result until this campaign.

It does not show that the fault detector catches faults on the board: no fault
was injected. It does not cover 25 times the noise, a noise level that changes
during a cycle, or a vehicle heavier than the model. Those remain simulated.

Each cell is one run.

## 9. What would settle the false alarm

Two counters in the DIAG frame: which of the three tests raised the flag, and
the control step it was raised on. Then the urban cell again, a few times.
The step number gives the place in the cycle, which says at once whether it is
a standstill, a launch or neither.


## 10. The detector's accelerometer assumption, against real logs

**Checked 2026-10-07.** Script: `scripts/check_accel_channel.py`. Data:
`docs/week12-accel-channel-check.json`. Logged data only: 70 BMW i3 trips,
30.4 hours, 10 Hz, with no sensor fault in them.

The detector trusts measured acceleration. In the simulation, and on the
board, that channel is the vehicle's true acceleration with white noise on
it. The i3 archive logs `Longitudinal Acceleration [m/s^2]` beside speed, and
the project's loader has always discarded it and derived acceleration from
speed instead, because the two do not agree. This looks at how far they
disagree and what the detector would make of it.

| | |
|---|---|
| Logged acceleration against the acceleration speed implies: correlation, one trip | 0.96, no lag |
| Offset between the two, median over trips | 0.016 m/s^2 |
| Offset, worst trip | 0.167 m/s^2 |
| Slow disagreement (5 s average), median standard deviation | 0.11 m/s^2 |
| Its correlation with gravity along the logged slope, median | 0.14 |
| Times the detector's flag went up | 142 (4.7 per hour) |
| Share of the driving spent flagged | 99.4% |
| Trips with no alarm | 0 of 70 |

**On real logs the detector is flagged 99% of the time, on every trip, with
nothing wrong with the sensor.** 139 of the 142 alarms come from its mean test.

The reason is arithmetic. The two channels agree well sample by sample, and
their average offset is small. What they do not share is a slow component of
about 0.11 m/s^2. Dead reckoning integrates acceleration and is pulled back to
the reading over 2 seconds, so an acceleration error that lasts longer than
that leaves a standing gap of error times 2 seconds: about 0.22 m/s. The mean
test calls a fault at 0.036 m/s. White noise, which is all the simulation
put on the channel, averages away in the integral and never shows this.

The slow component is only weakly related to road slope (correlation 0.14),
so it is not simply gravity on a hill, which was the guess beforehand. The
logs do not say what it is.

Two limits on this check. The logs are 10 Hz and the firmware runs at 100 Hz,
so the detector's 20-sample window spans two seconds here against 0.2 on the
board, and the alarm count is not the count the firmware would give. The
standing-gap argument does not depend on the rate. And these are one car's
CAN signals, which may be filtered differently from each other before they
are logged.

**What follows.** The simulated fault results for B6 (`docs/week12-fault-arms-b6.json`)
and its clean runs on the board hold for the acceleration channel they were
given. They do not carry to an acceleration channel like this one. As tuned,
B6 is not usable on such a sensor. Making it usable means a test threshold set
from the measured disagreement rather than from the speed noise, and that
costs sensitivity: with a standing gap of 0.22 m/s in healthy driving, a 0.5 m/s
offset is no longer clearly separable, while a dropout, a frozen reading or
an offset of several m/s still are. That redesign has not been done.

The filter, B5, does not use the acceleration channel and is not affected.
