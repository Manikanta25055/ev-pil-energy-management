# On-device decision model for robustness: design and test plan

**Date:** 2026-10-06
**Status:** design, awaiting review. Nothing here is built.
**Target:** ESP32-S3-DevKitM-1 N8R8, the board already in the loop.
**Decision taken by the user:** target robustness, with energy held equal to
the rule manager.

## 1. What the model is for, and what it is not for

The energy manager has no headroom. Week 7's dynamic program puts the rule
manager within 0.16% of the optimum on every cycle, and the correction of
2026-10-06 (`docs/week11-plant-correction.md`) removed the one result that
seemed to say otherwise. A new model that tries to save energy by choosing
regeneration, ceiling and derate differently has nothing to find.

Robustness is different. The measurements below show a loss that the rule
manager cannot see and a setting that would remove it, and the right setting
depends on conditions the controller has to recognise.

So the model does not replace the rule manager. The rule manager keeps the
three energy actions. The model sits beside it as a supervisor: it reads the
recent history, decides what condition the vehicle is in, and returns a small
set of typed decisions with a probability each. Low probability means the
default is kept, and the default is today's behaviour.

This is the shape of a "System One" decision model (typed choices with
calibrated confidence, no generated text), sized for a microcontroller. The
cloud model of that name cannot be used here: it answers in 70 to 500 ms over
a network and the outer loop is 100 ms.

## 2. The evidence that fixes the scope

SIMULATED on the corrected plant, US06, rule manager, 2026-10-06.

**The noise loss is in the speed loop, not the energy manager.** With speed
noise of 0.15 m/s the rule manager uses 195.73 Wh/km and a constant
always-regenerate action uses 195.64. The two degrade together, so the energy
manager is not the cause. The speed controller chases the noise with torque,
alternating drive and regeneration, and pays the round-trip loss.

**A speed filter removes it, and the best filter depends on the noise.**
First-order filter on measured speed, coefficient alpha (1.00 is no filter):

| Speed noise, m/s | alpha 1.00 | alpha 0.30 | alpha 0.10 | alpha 0.03 |
|---|---|---|---|---|
| 0.00 | **190.47** / 0.0013 | 190.57 / 0.0241 | 190.91 / 0.0924 | 193.00 / 0.3356 |
| 0.02 (floor) | **190.52** / 0.0025 | 190.58 / 0.0243 | 190.91 / 0.0925 | 193.01 / 0.3357 |
| 0.06 (3x) | 191.12 / 0.0066 | **190.65** / 0.0251 | 190.94 / 0.0928 | 193.03 / 0.3358 |
| 0.20 (10x) | 200.23 / 0.0215 | 191.78 / 0.0325 | **191.18** / 0.0954 | 193.17 / 0.3366 |
| 0.50 (25x) | 258.12 / 0.0671 | 199.99 / 0.0584 | **193.03** / 0.1068 | 193.74 / 0.3400 |

Each cell is energy in Wh/km, then tracking RMSE in m/s.

- Unfiltered at 10x noise costs 5.1% (200.23 against 190.47). The board
  measured 200.6 for the same setting in week 10, on the rule arm.
- Every filter costs tracking when the signal is clean.
- No single alpha is best on every row. That is the decision to be made.

**A fixed filter is already a strong answer.** Alpha 0.30 everywhere gives up
0.05% of energy and 0.02 m/s of tracking when clean, and recovers most of the
loss at 10x. Any learned model has to beat that, not just the unfiltered loop.

## 3. Architecture

```
            10 ms task, core 0                     100 ms task, core 1
  sensors -> [block features] ----- 32 blocks ---> [decision model]
     |                                                   |
     v                                                   v
  [speed filter, alpha from table] <----------- typed decisions + probability
     |                                          (kept only above a threshold)
     v
  [PID speed loop] -> torque          [rule manager] -> blend, ceiling, derate
```

**Where it runs.** `infer_task`, core 1, 100 ms period. That task runs a
783 us dummy load today, left over from the forecaster that did not ship.

**Input.** The last 32 blocks of 100 ms each (3.2 s). The 10 ms task reduces
each block to 10 numbers, which costs a few adds per step:

| Feature | Why |
|---|---|
| mean of measured speed | operating point |
| standard deviation of the 10 ms speed differences | noise level on speed |
| mean and standard deviation of measured acceleration | cross-check on speed |
| mean torque command, count of torque sign changes | the chatter itself |
| mean and standard deviation of battery current | electrical cross-check |
| reference speed and reference acceleration | what was asked for |

**Output.** Two decisions in version 1.

| Decision | Type | Options | Acts on | Default |
|---|---|---|---|---|
| Noise regime | choice | clean, elevated, severe | filter alpha from a 3-row table | clean (alpha 1.00) |
| Speed sensor fault | yes/no | stuck, dropped or biased | swap the PID input to a model-based speed estimate | no |

A third decision, what to do when the host link goes quiet (hold the last
command or ramp torque out), is held for version 2. Ablation A4 shows the
better choice depends on outage length and on whether the car is stopping, but
A4's actor runs are being re-measured on the corrected plant and the design
should wait for them.

**Safety.** The model never commands torque and never touches the energy
actions. A decision is applied only when its probability is above a threshold
fixed on validation data, and a change of regime must persist for 3
consecutive outer steps. If the model misses its deadline, the previous
decision is held; after 3 misses the defaults return. The rule manager and the
inner loop run unchanged whether the model is present or not, so it is a
compile-time arm like the actor.

## 4. The model

| | Chosen | Fallback if accuracy is short |
|---|---|---|
| Sequence length | 32 | 32 |
| Width (d_model) | 16 | 32 |
| Layers, heads | 1, 2 | 2, 4 |
| Feed-forward width | 32 | 64 |
| Encoder MACs | 98,304 | 655,360 |
| Parameters, int8 | about 2.5 k | about 18 k |
| Latency, estimated | 3.3 ms | 22.0 ms |
| Latency, expected on chip | about 5.4 ms | 36.46 ms (measured, gate G5) |
| Share of the 40 ms budget | about 14% | 91% |

MAC counts and the 29.82 MMAC/s throughput are from `docs/g1-compute-budget.md`.
The "expected" figure scales the estimate by 1.64, the ratio gate G5 measured
between the estimate and the chip. It is a prediction until measured.

The wide configuration is the one already benchmarked on the board in
`firmware/main/bench_encoder.c`, so the int8 kernels exist. The narrow one is
the default because the task is classification of a few regimes, and the
distillation study (`docs/a2-distillation.md`) found the d16 forecaster within
0.89% of d32 on a harder task.

Heads: a 3-way softmax and one sigmoid, read from a mean over the sequence.
Quantisation and export reuse `src/evpil/forecast/quantise.py` and
`deploy.py`. A parity test drives the Python and C versions with the same
inputs, as every exported model in this project has.

## 5. Training

Supervised, on simulation, because the labels are known there.

- **Regime label.** For each noise level the alpha that gives the lowest
  energy subject to tracking RMSE under 0.1 m/s, found by sweep. The table in
  section 2 is the first version of this.
- **Fault label.** Injected: stuck value, dropout to zero, step bias of 0.5 to
  3 m/s, each with a random onset.
- **Variation.** Noise level drawn continuously from 0 to 30x the floor,
  grade offset, starting charge, driver aggression 1.0 to 1.5, vehicle mass
  plus or minus 10% (the trip-to-trip spread found at gate G2).
- **Split.** Train on WLTC 3b and UDDS, validate on HWFET, test on US06. No
  threshold, table entry or checkpoint is chosen on US06.
- **Calibration.** Temperature scaling on validation; the probability
  threshold is chosen there too.
- Five seeds.

## 6. What it is compared against

| Arm | What it is | Why it is in the test |
|---|---|---|
| B0 | Rule manager and speed loop as shipped | the baseline the user named |
| B1 | B0 plus a fixed filter, alpha 0.30 | the cheapest fix; one line of C |
| B2 | B0 plus a threshold on the rolling speed-difference variance, with hysteresis, choosing alpha from the same table | a hand-written version of the same decision |
| B3 | B0 plus a Kalman filter on speed using the torque command | the textbook answer |
| M1 | A two-layer perceptron on the same 320 inputs | asks whether attention is needed |
| **T** | **The decision transformer of section 4** | the proposal |

B1 to B3 are the comparison that matters. Beating B0 is expected from the
table in section 2 and proves little. If T does not beat the best of B1 to B3,
the report says so and the classical arm ships.

## 7. Test plan

### 7.1 Scenarios

| Group | Levels |
|---|---|
| Clean | UDDS, HWFET, US06 at the noise floor |
| Gaussian noise | 3x, 10x, 25x on all measured channels |
| Noise that changes mid-cycle | floor to 10x at a random time, and back |
| Speed sensor faults | stuck, dropout, bias step; 8 onsets each |
| Plant mismatch | mass plus 10%, grade plus 0.03 rad |
| Existing axes | starting charge, driver aggression, as in the week-10 campaign |

### 7.2 Measures

Energy on the comparable scale (Wh/km), tracking RMSE and worst error, peak
battery current, torque sign changes per kilometre, fault detection delay,
false alarms per hour, decision WCET, `ctrl_late`, flash and RAM.

### 7.3 Criteria, fixed before any run

**Energy held equal (clean scenarios).** T within 0.2% of B0 on every clean
cycle, and tracking RMSE no more than 0.005 m/s above B0. The 0.2% bound is
the run-to-run agreement the two week-10 campaigns measured (0.19%).

**Robustness.**
- At 10x noise, T recovers at least half of B0's energy penalty.
- At 25x noise, at least 80%.
- Tracking RMSE under 0.1 m/s in every noise scenario.
- A speed-sensor fault is flagged within 0.5 s, with fewer than one false
  alarm per hour of clean driving.
- After a mid-cycle change the regime is correct within 1 s.

**Against the classical arms.** T is "justified" only if it beats the best of
B1 to B3 on at least one robustness measure by more than the seed spread and
loses on none. Otherwise the result is reported as null.

**Embedded.** Decision WCET under 40 ms, `ctrl_late` 0, jitter unchanged from
the current image, weights under 30 KB.

**Guard against a repeat of the week-10 error.** No arm may finish below the
DP optimum at equal tracking. Any that does is treated as a plant fault until
shown otherwise.

### 7.4 Stages

1. **Offline.** All six arms, five seeds, every scenario, paired by seed.
   Bootstrap 95% intervals on each difference. Laptop only.
2. **On the chip, timing.** Export T, parity test, measure WCET with the
   existing benchmark harness.
3. **Processor in the loop.** B0, the best classical arm and T on the board,
   every scenario once, plus the three clean cycles three times each for the
   repeat spread. About 9 hours of board time.
4. **Scoreboard.** One row per measure, T against B0 and against the best
   classical arm, each cell marked better, equal or worse with its interval.

### 7.5 What "beats the rule manager in most terms" will mean

Counted over the measures in 7.2, T against B0: better on the noise and fault
measures, equal on clean energy and clean tracking, worse on compute and
memory. Compute cost is a real loss and is reported as one.

## 8. Risks

| Risk | Consequence | Mitigation |
|---|---|---|
| B1 or B2 matches T | the transformer is not needed | reported as a null; the classical arm ships |
| Regime flapping near a boundary | filter switches back and forth | 3-step persistence, probability threshold |
| Simulated noise is Gaussian, real noise is not | a model fitted to the wrong thing | mid-cycle and fault scenarios; stated as a limit |
| Model-based speed estimate drifts during a fault | tracking error grows with time | estimate is bounded to 5 s, then torque ramps out |
| Plant bookkeeping error | a false win | the DP guard in 7.3 |

## 9. Order of work

1. `speed_filter_alpha` as an input to the simulator's speed loop and to the
   firmware's control task, with a parity test. B1 becomes runnable.
2. Block features in Python and C, with a parity test.
3. B2 and B3 offline. Stage 1 for the classical arms alone. This already
   answers whether the problem needs a learned model.
4. Dataset generator, M1 and T, calibration. Rest of stage 1.
5. Stages 2 to 4.

Step 3 is a decision point for the user: if a classical arm meets every
criterion in 7.3, building T is a choice about the paper's story, not about
the controller.
