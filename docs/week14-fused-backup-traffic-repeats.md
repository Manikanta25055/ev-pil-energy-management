# Week 14: a backup speed that does not drift, traffic in the speed plan, and board repeats

**Run 2026-10-09 afternoon.** Branch `night/2026-09-21-pil-campaign-and-final-report`.
Follows `docs/week13-estimator-and-board.md` and `docs/week13-energy-planning.md`.
Sections 1 and 2 are SIMULATED on the laptop. Section 3 is MEASURED on the
board. Plain names are used: the "new checker" is B7, the "rule helper" is
the rule monitor, the "fused backup speed" is B8.

## 1. A backup speed that does not drift (SIMULATED)

**Data:** `docs/week14-b8-tuning.json`, `docs/week14-b8-val.json`,
`docs/week14-b8-test.json`. **Code:** `FusedFallbackKalman` in
`src/evpil/control/speed_estimators.py`.

Week 13 found the limit on every helper: while the speed sensor is
distrusted the controller works from a backup speed, and both backups
drift. One is worked out from the acceleration reading and drifts with that
reading's error. The other is the vehicle model's prediction and drifts
with whatever the model has wrong. Week 13 tried mixing the two outputs and
that did not help.

The fused backup speed is one filter that keeps track of three things: the
speed, the model's error, and the acceleration reading's error. While the
sensor is trusted it learns both errors. While the sensor is distrusted it
carries on with what it learned, and the acceleration reading still
corrects the two errors together. Detection is unchanged: the same checker
raises and drops the alarm.

Its three settings were chosen on the urban training cycle only
(`scripts/tune_fused_fallback.py`, 18 candidates, rule fixed before the
runs). On those runs the largest speed error through a fault was
0.26 m/s against 4.14 for the checker alone.
One of the chosen settings sits at the edge of the range tried.

Highway cycle (validation), 560 faults per row:

| | Caught in 0.5 s | Alarm stuck at 8 s | Largest speed error, m/s | Typical speed error, worst condition, m/s | Clean false alarms |
|---|---|---|---|---|---|
| New checker alone | 551 | 14 | 3.74 | 0.56 | 0 |
| New checker with the rule helper | 551 | 10 | 1.24 | 0.24 | 0 |
| With the fused backup speed | 551 | 0 | 0.62 | 0.08 | 0 |
| Fused backup speed and rule helper | 551 | 10 | 0.70 | 0.09 | 0 |

Aggressive cycle (test), 560 faults per row:

| | Caught in 0.5 s | Alarm stuck at 8 s | Largest speed error, m/s | Typical speed error, worst condition, m/s | Clean false alarms |
|---|---|---|---|---|---|
| New checker alone | 533 | 32 | 5.10 | 0.58 | 0 |
| New checker with the rule helper | 533 | 5 | 1.41 | 0.47 | 0 |
| With the fused backup speed | 533 | 2 | 2.59 | 0.55 | 0 |
| Fused backup speed and rule helper | 533 | 4 | 1.29 | 0.50 | 0 |

**On the highway cycle the fused backup speed is the best result so far**:
largest error 0.62 m/s against 3.74 for the checker alone and 1.24 with the
rule helper, typical error 0.08 against 0.24, no alarm left stuck, no false
alarm.

**On the aggressive cycle it is the best in six of the seven conditions and
the worst in one.** With the car as the model expects, in every
acceleration condition, its largest error is 0.61 to 0.64 m/s and its
typical error 0.05 to 0.10, against 0.72 to 1.19 and 0.20 to 0.47 for the
rule helper. With the car 10% heavier than the model, its largest error is
2.59 m/s and its typical error 0.55. Adding the rule helper brings the
largest error across all conditions to 1.29, a little under the rule helper
with the old backup (1.41).

The heavier car on the aggressive cycle is where the model is most wrong
and changes fastest. The filter was tuned on the gentle urban cycle and
chose the slowest setting offered for following the model's error. That is
the likely cause; it was not tested.

Not done: the fused backup speed in C, or on the board.

## 2. Speed planning with traffic (SIMULATED)

**Data:** `docs/week14-corridor-planner.json`. **Code:**
`src/evpil/plan/corridor.py`, `scripts/run_corridor_planner.py`.

Week 13's planner drove an empty road, and its 10.4% saving was the most
planning could give. A real car is in traffic. Here the planner must stay
within a set distance of the recorded drive at every second, ahead or
behind. Zero distance is the recorded drive. A large distance is the empty
road. Distance covered and arrival time are the recorded drive's exactly.

Aggressive route (test):

| The car stays | Wh/km | Saving | Peak current, A |
|---|---|---|---|
| the recorded drive | 190.5 | | 257 |
| within 5 m | 186.0 | 2.3% | 233 |
| within 10 m | 184.0 | 3.4% | 223 |
| within 25 m | 180.7 | 5.1% | 215 |
| within 50 m | 176.7 | 7.2% | 218 |
| within 100 m | 172.0 | 9.7% | 218 |
| within 200 m | 166.6 | 12.6% | 198 |

Highway route (validation):

| The car stays | Wh/km | Saving | Peak current, A |
|---|---|---|---|
| the recorded drive | 153.9 | | 91 |
| within 5 m | 154.0 | -0.1% | 162 |
| within 10 m | 153.4 | 0.3% | 162 |
| within 25 m | 152.6 | 0.8% | 151 |
| within 50 m | 151.9 | 1.3% | 151 |
| within 100 m | 151.6 | 1.5% | 148 |
| within 200 m | 151.3 | 1.7% | 148 |

**About half of the saving survives a tight traffic limit.** Held within
25 m of the recorded drive, the planner still saves 5.1% on the aggressive
route; within 50 m, 7.2%; within 100 m, 9.7%. On the steady highway route
there is little to save at any distance: 0.8% within 25 m.

Peak battery current falls here, from 257 A to between 198 and 233 A on the
aggressive route. Week 13's empty-road planner raised it. The two planners
differ in more than the traffic limit (this one works in one-second steps
and has no separate stop rule), so the reason is not established.

Limits: the "traffic" is one recorded drive, not a traffic model. One run
per distance. No learning in this experiment, and nothing on the board.

## 3. Board repeats of the fault campaign (MEASURED)

**Data:** `docs/week14-b7-pil-repeats.json`
(`scripts/report_b7_pil_repeats.py`), from the week-13 files and
`docs/week14-b7-pil-{b7,b7mon}-seed{100,200}.json`.

Week 13 ran each board case once. The same 42 cases per version were run
twice more with different draws of sensor noise and of acceleration drift,
for the new checker alone and with the rule helper. That is 120 injected
faults and one hour of clean driving per version.

| | New checker | New checker with rule helper |
|---|---|---|
| Faults caught within half a second | **120 of 120** | **120 of 120** |
| Slowest catch, seconds | 0.32 | 0.33 |
| False alarms before any fault | 0 | 0 |
| False alarms in one clean hour | **0** | **0** |
| Alarm dropped during the fault | 47 | 30 |
| Still raising the alarm when the run ended | 0 | 3 |
| Largest speed error during a fault, m/s | 0.83 | 1.32 |
| Typical speed error during a fault, m/s | 0.43 | 0.40 |
| Control steps finished late | 0 | 0 |
| Longest control calculation, millionths of a second | 74 | 78 |

By draw, largest and typical speed error in m/s:

| | First run | Repeat 1 | Repeat 2 |
|---|---|---|---|
| New checker | 0.67, 0.25 | 0.83, 0.44 | 0.68, 0.45 |
| New checker with rule helper | 0.61, 0.20 | 1.32, 0.53 | 1.03, 0.47 |

**The new checker's detection result holds.** Every one of 120 injected
faults was caught within a third of a second, across three draws of noise,
with no false alarm in an hour of clean driving and no late control step.

**The rule helper's advantage on the board does not hold.** In the first
run it looked a little better than the checker alone. Over three draws it
drops the alarm early less often (30 against 47) and its typical error is
about the same (0.40 against 0.43), but its largest error is larger (1.32
against 0.83) and it left three alarms raised at the end of a run where the
checker alone left none. Week 13 said the first-run difference was not
established. It was not.

The typical speed error in the first run (0.25) was lower than in either
repeat (0.44, 0.45). One draw is not a measurement of that number.

How the runs were taken: while simulations were running on the laptop, 5
board cells lost more than 16 frames, and 3 more did later with nothing
else running. All 8 were set aside in `-disturbed.json` files and taken
again, as the week-12 rule says. No cell in the result has more than 16.
The board was left on the normal actor image and reported policy steps
when asked. The acceleration drift is still simulated, not a real sensor.

## 4. What to take from week 14

1. **Keep the new checker.** Its board result has now been repeated.
2. **Do not add the rule helper on the board's evidence.** It helps in
   simulation and did not help over three draws on the chip.
3. **The fused backup speed is the most promising change to the sensor
   work**, in simulation: it removes most of the speed error while an alarm
   is raised, except on a car heavier than its model in aggressive driving.
   It needs that case fixed, then a C version and a board run.
4. **Planning still pays in traffic**, in simulation: about half of the
   empty-road saving is left when the car must stay within 25 m of the
   recorded drive, on the aggressive route.

## 5. Not done

- The fused backup speed on the board.
- A fix for the heavier car on the aggressive cycle.
- A real acceleration sensor: still simulated drift.
- A traffic model with more than one recorded car.
- Jev: not purchased.
