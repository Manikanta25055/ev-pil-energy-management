# Design: Deadline-Aware Energy Management for Electric Vehicles on an ESP32-S3

**Date:** 2026-08-30
**Status:** Approved design, pending implementation plan
**Supersedes:** "Overall Project Plan" (professor's initial design), restructured with approval

---

## 1. Purpose and framing

This is an **embedded-systems study with a machine-learning payload**, not a
machine-learning study with an embedded appendix. It answers one question:

> What survives when a lab-grade AI energy-management controller is forced
> through int8 arithmetic, a few hundred kilobytes of SRAM, and a hard 10 ms
> deadline — and what does it cost when it does not?

The professor's original plan names exactly this gap ("high-performance AI
models in simulation vs. real-time execution on resource-constrained embedded
hardware") but schedules the embedded work last, where a failure to fit has no
recovery path. This design keeps the gap and inverts the order.

Target output: one journal paper, 12 weeks.

### 1.1 Terminology: this is PIL, not HIL

The original plan calls the Python-plant/ESP32 loop "Hardware-in-the-Loop".
It is not. There is no plant hardware, no analog I/O, and no power stage. The
correct term is **Processor-in-the-Loop (PIL)**, sometimes "controller-in-the-loop".

This is a deliberate, approved decision. Reviewers in embedded and control
venues will flag a misused "HIL" immediately, and the PIL framing costs nothing:
running real firmware on real silicon under a real RTOS against a simulated
plant is a legitimate and standard validation method.

---

## 2. Relationship to prior work

The predecessor is Tangi, Vatsa, Opam, Bonthagorla & Gaonkar, "Smart Strategies
for Improving Electric Vehicle Battery Performance and Efficiency", *Scientific
Reports* 15:42070 (2025), and the underlying B.Tech report (Vatsa & Opam, MIT
Manipal, May 2024).

This project is **not an incremental extension** of that work. It is a different
system. Its relationship to the prior paper is that it addresses that paper's
own stated Limitation 1 (absence of real-world data), Limitation 2 (static
feature representation, no temporal granularity), and Future Scope item 5
(embedded / edge deployment).

### 2.1 Defects in the prior work that this design must not inherit

Identified by reading Annexure 4 of the B.Tech report (the dataset generator)
and cross-checking against the published tables.

| # | Defect | Evidence | How this design avoids it |
|---|---|---|---|
| D1 | Target is a closed-form deterministic function of the features | Generator computes `range_estimate = (Eb*3.6*speed)/Pd` from the same variables fed to the models | Real logged data (Section 5); ML learns residuals the nominal physics cannot express |
| D2 | Row-level train/test leakage | `train_test_split(random_state=42)` on 2000 temporally-correlated rows | Trip-level grouped splits (Section 5.2) |
| D3 | Ensemble weights almost certainly fitted on test data | Individual R^2 of -0.55 to -9.11, weighted ensemble R^2 of 0.92 | Any ensemble weights fitted on validation only, never test (Section 5.2) |
| D4 | LSTM fed non-sequential data | `X_train.reshape((n, n_features))` used as a "sequence"; LSTM had no temporal information | Real `(batch, seq_len, features)` tensors; LSTM re-run correctly as a baseline |
| D5 | Feature leakage in the velocity model | `Range (Km)` used as an input feature, and `Range` was computed from speed | Explicit written leakage audit before training (Section 6.4) |
| D6 | Incomplete physics | No rolling resistance, no inertial `m*a` term, no drivetrain or motor efficiency, `HVAC_load = 5` declared and never used, `h = sqrt(dElev^2 + 50^2)` hardcodes a 50 m baseline | Full longitudinal model with 2-D efficiency map and fitted auxiliary load (Section 4.1) |
| D7 | "Optimum velocity" ground truth is itself an assumed formula | Predicting one's own assumption | Targets are logged measurements, or a DP optimum computed against a validated plant |
| D8 | Figures and tables disagree | Ensemble scatter plots (Figs 7, 12) show systematic under-prediction while tables report improving R^2 | Per-trip metric distributions and bootstrap CIs reported alongside every aggregate |

Re-running the LSTM correctly (D4) is deliberate: it makes the comparison to the
prior paper direct and shows the earlier underperformance was a tensor-shape
error, not a property of recurrent models.

---

## 3. Claims

### 3.1 What this work will claim

| ID | Claim | Supporting evidence |
|---|---|---|
| C1 | A real-data-anchored EV plant model | Longitudinal + Thevenin ECM, parameters identified against BMW i3 logs; physics-vs-reality residual quantified |
| C2 | Physics-informed multi-step battery-power forecasting | Trained on real logged trips, tested on held-out trips; PI vs plain variant at matched parameter count |
| C3 | Hierarchical control that separates safety from optimisation | Deterministic PID inner loop (10 ms) + RL energy-management outer loop (100 ms) consuming the forecast |
| C4 | An accuracy/latency/memory/energy Pareto front for sequence models on a commodity MCU | Measured on silicon across float32, int8, and distilled student |
| C5 | Deadline-aware execution with quantified degradation | Externally measured WCET distributions; deadline-miss handling with PID fallback; control-quality cost of a miss |
| C6 | Characterised PIL validation | Measured latency and jitter budget; robustness under injected sensor noise, communication delay, grade, and SoC variation |

### 3.2 What this work will explicitly not claim

Stating these is what makes the rest credible.

- Not HIL. Processor-in-the-Loop.
- No real-vehicle validation.
- No claim of state-of-the-art range or energy prediction accuracy.
- **No claim that physics-informed beats plain unless the data shows it.** A null
  result on C2 is pre-accepted and will be reported with an explanation.
- No claim that the forecast improves control unless ablation A3 shows it
  (Section 6.3). A null result on A3 is pre-accepted.

---

## 4. System architecture

Five units, each independently testable.

```
   BMW i3 logs (10 Hz)          Driving cycles (WLTP/UDDS/HWFET/US06)
          |                                    |
          +--- parameter ID -->+---------------v----------------+
          |                    |   [1] PYTHON EV PLANT (host)   |
          +--- training data   |  longitudinal - eta(T,w) map - |
          |                    |  Thevenin ECM - thermal/aux -  |
          |                    |  regen limits                  |
          |                    +---------------+----------------+
          |                                    | state frame, 10 ms
          v                                    |  +-- CRC + seq no.
   [2] PREDICTION STACK                        v  |
   (offline, PyTorch)          +------------------v-------------+
   XGBoost | LSTM | Transformer|   [4] ESP32-S3  (ESP-IDF)      |
   plain vs physics-informed   |  comm_rx - ctrl - comm_tx 10ms |
          |                    |  infer - ems            100ms  |
          | distil + int8      |  diag                   500ms  |
          +------------------->|  GPIO timing pins ---------+   |
                               +------------------+---------|---+
   [3] CONTROLLER                                 | actuation   |
   PID inner (10 ms) ----------------------------+              v
   SAC outer (100 ms)                            [5] Analog Discovery 3
   vs PID-only - vs DP optimum                    WCET - jitter - mJ
```

### 4.1 Unit 1: Python EV plant (host)

Purpose: a validated simulator of the vehicle, battery and road, used both to
generate controller-evaluation scenarios and to close the real-time PIL loop.

Longitudinal dynamics, complete (fixing D6):

```
F_trac = m*a + F_roll + F_aero + F_grade
F_roll = C_rr * m * g * cos(theta)
F_aero = 0.5 * rho * Cd * A * v^2
F_grade = m * g * sin(theta)
```

Drivetrain: gear ratio, wheel radius, and a **2-D motor efficiency map
eta(T, omega)** implemented as an interpolated lookup, not a scalar constant.

Battery: first-order Thevenin equivalent-circuit model with OCV(SoC) curve and
internal resistance R(SoC, T_batt); SoC by Coulomb counting. Charge and
discharge current limits, SoC bounds, and a regenerative-braking power limit
with blending.

Thermal and auxiliary: HVAC/auxiliary power as a function of ambient
temperature, fitted from the i3 dataset's heating-circuit channel.

Vehicle parameters (mass, C_rr, Cd, frontal area, wheel radius, gear ratio,
battery capacity, nominal voltage, internal resistance, motor rated power and
peak torque) are identified from the logs where identifiable and otherwise taken
from published specifications. **Every parameter carries a citation.** Numbers
are not asserted in this spec because none have been verified yet; establishing
them is a Week 2 task.

**Interface:** `step(torque_cmd, dt) -> state` where state is the full signal
vector; `reset(cycle, grade_profile, soc0, t_ambient)`.

**Dependencies:** i3 dataset for parameter identification and validation;
driving-cycle files.

### 4.2 Unit 2: prediction stack (offline, PyTorch)

Input: 64 past steps (6.4 s at 10 Hz) of
`[v, a, SoC, I, V, T_ambient, grade, P_aux]`.
Output: 30-step (3 s) future battery power.

Sequence length and model width are **not fixed by this spec**. They are
determined by the Week 1 compute budget (Section 7.1). The values above are the
starting point that the G1 measurement will confirm or shrink.

Four arms, each in plain and physics-informed variants at matched parameter
count:

| Arm | Role |
|---|---|
| Persistence | Mandatory naive baseline (Section 6.4) |
| XGBoost on windowed features | Single strong tabular baseline, replacing the prior work's RF/ET/LR ladder |
| LSTM, correct tensors | Direct comparison against the prior paper, fixing D4 |
| Transformer encoder | Candidate proposed model |

Physics-informed loss adds weighted residual terms to the data loss:

```
r1: P_batt - V*I                                (electrical consistency)
r2: dSoC/dt + I/(3600*Q)                        (charge conservation)
r3: relu(P_mech/eta_max + I^2*R - P_batt)       (power-balance inequality)

L = L_data + lambda_1*|r1| + lambda_2*|r2| + lambda_3*|r3|
```

The lambda weights are validation-tuned. The physics-violation rate is reported
as a metric in its own right (Section 6.2), independent of accuracy.

**Interface:** `forecast(window) -> horizon` — a pure function, no state.

**Dependencies:** the data pipeline (Section 5), not the plant.

### 4.3 Unit 3: controller

Two loops with a clean separation of concerns: the inner loop owns safety and
tracking, the outer loop owns optimisation.

**Inner (10 ms, on-device):** PID with feedforward on speed. Deterministic,
bounded, always meets the cycle. This is what makes the energy comparison honest
— tracking quality is a hard constraint the optimiser cannot trade away.

**Outer (100 ms, on-device):** SAC policy.

- State: `[SoC, v, a, T_batt, grade, forecast_summary, tracking_error]`, where
  `forecast_summary` is the mean and max of the H-step predicted power.
- Action (continuous, 3-D): regenerative blending ratio in [0,1], discharge
  power limit, auxiliary derate.
- Reward: `-w_e*E_step - w_t*e_track^2 - penalties(I_limits, SoC_bounds)`.

Because the inner loop owns tracking, the reward cannot buy energy savings by
driving slower — the failure mode that would otherwise reduce an "energy saving"
result to "it did not follow the cycle".

**Comparison arms:**

| Arm | Role |
|---|---|
| PID + rule-based regen | Conventional baseline; also the guaranteed-working fallback if SAC fails |
| Dynamic Programming, offline | **Global optimum upper bound.** Without it, "energy-efficient" is unanchored |
| SAC outer loop (proposed) | The method under test |

**Interface:** `policy(state) -> action`; the inner loop is
`pid_step(v_ref, v_meas, dt) -> torque_cmd`.

### 4.4 Unit 4: ESP32-S3 firmware (ESP-IDF, FreeRTOS)

Revised task set. Note the correction to the original plan: **communication runs
at 10 ms, not 50 ms.** As originally specified, a 50 ms communication task made
the advertised 10 ms control loop impossible.

| Task | Period | Core | Priority | Function |
|---|---|---|---|---|
| `comm_rx` | 10 ms | 0 | highest | Parse plant state frame, verify CRC and sequence |
| `ctrl` | 10 ms | 0 | high | PID inner loop; apply outer-loop setpoints |
| `comm_tx` | 10 ms | 0 | high | Emit actuation frame |
| `infer` | 100 ms | 1 | low | Transformer forecast + SAC actor |
| `ems` | 100 ms | 1 | medium | Apply policy output, safety clamps |
| `diag` | 500 ms | 1 | lowest | Stack high-water marks, CPU load, deadline-miss counters |

Two firmware decisions that matter:

- **Tasks are pinned to cores.** The S3 is dual-core; the hard real-time loop on
  core 0 then cannot be perturbed by inference on core 1. The ESP32-C6 is
  single-core RISC-V and cannot do this — worth one sentence in the paper as a
  platform note.
- **WiFi and Bluetooth are disabled in menuconfig.** The radio would dominate the
  supply-current measurement and inject timing jitter unrelated to the
  controller, corrupting both headline embedded metrics.

Inference at 100 ms feeding a 10 ms control loop means the controller sometimes
consumes a stale forecast. This is acceptable and is measured, not hidden.

**Deadline handling:** if `infer` overruns its budget, `ctrl` falls back to
rule-based regen and a deadline-miss counter increments. Misses appear in the
results; they are never silently absorbed.

### 4.5 Unit 5: PIL link and measurement rig

**Link.** Fixed-size binary frames with CRC and sequence numbers in both
directions, so drops and reordering are detected rather than inferred.
Timestamps at both ends make latency and jitter measured quantities.

**The ESP32 is the clock master.** The host is macOS on 8 GB — not a real-time
operating system. If the host paced the loop, its scheduler jitter would
contaminate every timing result and present as a firmware defect. Inverting the
relationship, so the MCU requests each plant step, converts host jitter into a
measured disturbance on a link that is already characterised.

Transport: native USB-Serial-JTAG and an external USB-UART are both candidates;
G3 (Section 8.2) selects between them on measured latency.

**Measurement.**

| Quantity | Method |
|---|---|
| WCET, jitter | GPIO toggled at task entry/exit, captured on Analog Discovery 3 digital channels |
| mJ per inference | 1 ohm shunt on the 3V3 rail, AD3 differential analog input |
| CPU load, stack HWM, deadline misses | FreeRTOS runtime statistics via `diag` |
| Link latency, jitter, drop rate | Dual-ended timestamps, CRC and sequence numbers |

Externally captured timing is materially stronger evidence than firmware
self-reporting, and is the part of this work that a simulation-only study cannot
replicate.

---

## 5. Data strategy

### 5.1 Sources

| Source | Role | Detail |
|---|---|---|
| Battery and Heating Data in Real Driving Cycles (IEEE DataPort, DOI 10.21227/6jr9-5235) | **Primary** | 2014 BMW i3 (60 Ah), 72 trips, Munich, 10 Hz. Battery V/I/T/SoC, ambient temperature, elevation, throttle, speed, heating-circuit power |
| Vehicle Energy Dataset (VED), github.com/gsoh/VED | Secondary | 3 pure EVs (2013 Nissan Leaf, 24 kWh) at 1 Hz OBD-II. Used only as an out-of-distribution generalisation check |
| WLTP, UDDS, HWFET, US06 | Controller scenarios | Standard cycles run through the validated plant |

The i3 set is the primary source specifically because it carries the
heating-circuit channel. Auxiliary load is the term the prior work declared
(`HVAC_load = 5`) and then never used, and it is a first-order contributor to
real energy consumption.

### 5.2 Splits

Trip-level grouping. No sample from a trip ever appears on both sides of a split.
This is the direct fix for D2.

| Split | Trips | Purpose |
|---|---|---|
| Train | ~44 | Model fitting |
| Validation | ~14 | Hyperparameters, early stopping, quantisation calibration, **any ensemble weights** |
| Test | ~14 | Touched once, at the end |
| VED Leaf | separate | Out-of-distribution check, reported separately |

Stratified by ambient temperature: the i3 set spans winter and summer, and HVAC
load is the dominant confounder.

Quantisation calibration sets are drawn from **training trips only**. A
calibration set built from test data is a subtle and common leak.

VED results are expected to be worse — different vehicle, battery chemistry,
capacity and sample rate. They are reported as a generalisation bound, not as a
headline.

For the controller, the original plan's split is retained: train on WLTP+UDDS,
validate on HWFET, test on US06 plus unseen grade profiles.

---

## 6. Experiment design

### 6.1 Plant validation (gate G2)

Replay a held-out i3 trip's **logged speed profile** through the plant and
compare predicted battery power and SoC against the **logged** values.

Pass criterion: battery-power RMSE at most 10% of the trip's mean absolute
power, and terminal SoC error at most 2 percentage points, on every held-out
validation trip.

If the plant cannot reproduce real trips, nothing downstream is meaningful. This
criterion may be revised once, at G2, only with the reason recorded in this
document.

**REVISED at G2, 2026-08-30. This is the one permitted revision; it is now
spent.** Full evidence in `docs/g2-plant-validation.md`.

Neither threshold changed. What changed is which model each threshold is
applied to, because the single pooled number could not localise a failure.

| Part | Test | Threshold |
|---|---|---|
| A | Torque inverted from the logged speed profile, against the archive's logged motor torque | RMSE at most 50% of the trip's logged-torque standard deviation |
| B | Battery power with logged torque as the input | RMSE at most **10%** of mean absolute power (unchanged) |
| C | Terminal SoC from full speed-profile replay | at most **2 percentage points** (unchanged) |

Reason: replaying a speed profile requires differentiating a 10 Hz speed
channel to recover acceleration, and multiplying the result by 1270 kg. That
injects a zero-mean 10.4 Nm torque residual which no plant model can remove.
Fitting the chassis parameters directly against logged torque reduces the
residual only from 10.70 to 10.37 Nm over 276,751 samples, and the correlation
between a trip's torque spread and its relative power error is −0.85: the error
is set by signal-to-noise, not by model quality. Driven by logged torque, the
powertrain, battery and auxiliary models meet the original 10% bound on every
validation trip (median 7.0%, worst 8.3%).

Trip energy error is reported alongside but not gated, since it integrates the
same quantity as terminal SoC.

### 6.2 Metrics

The original plan's Section 22 listed metric headings with no content. These are
the metrics.

| Layer | Metrics |
|---|---|
| Prediction | MAE, RMSE, R^2 **per horizon step**, not pooled; physics-violation rate; per-trip distributions alongside aggregates; bootstrap confidence intervals |
| Control | Speed-tracking RMSE; Wh/km; **percentage gap to the DP optimum**; terminal SoC; peak battery current; regenerative energy recovered |
| Embedded | WCET p50/p99/max; jitter standard deviation; per-task CPU load; peak stack high-water mark; flash and SRAM footprint; mJ per inference; deadline-miss rate |
| Statistical | 5 seeds for SAC, reported as mean with confidence interval. Single-run RL results are not publishable |

Reporting per-trip distributions alongside pooled means addresses D8 directly.

### 6.3 Ablations

| ID | Question | Backs claim |
|---|---|---|
| A1 | Physics-informed vs plain, matched parameter count | C2 |
| A2 | float32 to int8 to distilled student | C4 |
| A3 | **RL with vs without the forecast in its state** | C3 |
| A4 | Deadline-miss handling on vs off | C5 |

**A3 carries real risk to the narrative and is run anyway.** If removing the
forecast from the RL state does not degrade control, the entire prediction stack
is decorative on-device and the paper will say so. A negative A3 is itself a
publishable finding about preview horizons in embedded energy management, and it
would free the memory budget for other uses.

### 6.4 Guards, run before any training

1. **Leakage audit.** A written check that no target-derived quantity appears as
   an input. This is the specific class of error behind D5.
2. **Shuffled-label control.** Shuffle targets, retrain, confirm performance
   collapses to chance. If it does not, there is leakage to find before any
   result is recorded.
3. **Persistence baseline.** Predict that power remains at its current value
   across the 3 s horizon. Short-horizon power forecasting is a domain where
   persistence is difficult to beat, and its omission is a standard reviewer
   objection.

### 6.5 Scenarios

Trimmed from the thirteen variations listed in the original plan to six
scenario axes, retaining full robustness coverage at roughly half the runs.

| Scenario | Variation |
|---|---|
| Driving condition | Urban / highway / stop-and-go, via cycle choice |
| Road grade | Sweep from uphill through downhill; absorbs the original plan's separate "rapid grade change" |
| Battery state | High / medium / low SoC bands |
| Sensor noise | Injected noise on measured signals |
| Communication delay | Injected latency on the PIL link |
| Driver aggression | Aggressive acceleration and sudden braking |

---

## 7. Embedded deployment

### 7.1 Budget first, then model

The single most important structural change from the original plan. Week 1
measures the silicon, and that measurement sizes the model.

MAC counts for a Transformer encoder are arithmetic:

| Config | seq | d_model | layers | approx. params | approx. MACs / inference |
|---|---|---|---|---|---|
| As the original plan implies | 64 | 64 | 2 | ~66 k | ~5.2 M |
| Trimmed | 32 | 32 | 2 | ~17 k | ~0.7 M |
| Aggressive | 32 | 16 | 1 | ~2 k | ~0.1 M |

Counts are for the encoder stack only and exclude the input embedding and
output head; feed-forward width is taken as 2x d_model. Parameters fit SRAM
comfortably in all three cases. **MACs are the binding constraint and they span
roughly 50x.** The unknown is effective int8 throughput
with ESP-NN vector kernels on the S3; no figure is asserted here because none has
been measured.

Whichever row proves feasible determines the architecture, the training runs and
the distillation target. Discovering this in Week 10 leaves no recovery path.
Discovering it in Week 1 costs nothing.

**G1 deliverable:** a measured MACs/second figure, the table above with real
latencies filled in, and a chosen configuration.

### 7.2 Toolchain

PyTorch to ONNX to TFLite to **esp-tflite-micro** with ESP-NN int8 kernels.
TFLite-Micro is the pragmatic path because it covers the awkward Transformer
operations (batch matmul, softmax, normalisation).

The SAC actor is a plain MLP and may be hand-written in C against ESP-NN
directly if TFLite-Micro overhead proves significant. This is a small, contained
escape hatch.

Quantisation: int8 post-training, calibrated on training trips only. QAT only if
PTQ loses more accuracy than the Pareto curve can absorb.

Distillation: train the unconstrained Transformer offline, then distil into
whatever fits the G1 budget. Reporting accuracy at each rung **is** claim C4 —
the Pareto curve is the result, not a compromise.

### 7.3 Fallback ladder

Decided now rather than under schedule pressure. **Every rung still produces a
publishable paper.**

1. Shrink `(seq, d_model)` per the table in 7.1
2. Distil to a GRU or TCN student
3. Move the forecast to a 200 ms period
4. Deploy a lightweight AR or linear predictor on-device; report the Transformer
   as offline-only and make the Pareto curve the headline finding

Rung 4 is the honest form of "advanced sequence models do not fit on a commodity
MCU at this deadline" — which is precisely the gap the project set out to study.
Budget-first is what converts a potential project collapse into a result.

### 7.4 Hardware

**ESP32-S3-DevKitM-1** is the primary platform: dual-core Xtensa LX7 at 240 MHz
with a 128-bit vector ISA that ESP-NN's int8 kernels exploit, and dual cores that
permit isolating the real-time loop from inference.

The **ESP32-C6** (single-core RISC-V at 160 MHz, no vector ISA) is unsuitable as
the primary platform. It may appear as a one-line contrast point.

**Open hardware question — RESOLVED 2026-08-30.** `esptool chip_id` reports
`ESP32-S3 (QFN56) revision v0.2, Features: WiFi, BLE, Embedded PSRAM 8MB`, so
the board is an **N8R8**, not the base N8.

Memory is therefore not a constraint: even the plan-implied configuration
(~66 k int8 parameters) fits with orders of magnitude to spare. **MACs remain
the binding constraint**, as section 7.1 predicted, so G1 is still decisive and
the budget-first procedure is unchanged.

Two caveats keep PSRAM from being free: `CONFIG_SPIRAM` must be enabled before
the application can see it, and octal PSRAM is substantially slower than
internal SRAM, so inference-hot weights belong in internal SRAM. Quantifying
that gap is itself a reportable result. See `docs/hardware-inventory.md`.

---

## 8. Schedule and gates

### 8.1 Twelve weeks, two parallel tracks

| Wk | ML / modelling track | Embedded track | Gate |
|---|---|---|---|
| 1 | Literature; acquire i3 and VED data | ESP-IDF skeleton; int8 MAC micro-benchmark | **G1** |
| 2 | Plant v1: longitudinal + Thevenin ECM; parameter identification | PIL link echo loop; GPIO and AD3 timing rig | **G2** |
| 3 | eta(T,w) map, thermal/auxiliary, regen; splits, leakage audit, shuffled-label control | Full FreeRTOS task set at final periods, dummy compute | **G3** |
| 4 | Persistence, XGBoost, LSTM with correct tensors | Frame protocol hardening, CRC, sequence numbers | **G4** |
| 5 | Transformer sized to the G1 budget; PI variant; **A1** | Core pinning, WiFi/BT disabled, jitter baseline | |
| 6 | Distillation and int8 PTQ; **A2** | Deploy forecaster; measure latency, SRAM, mJ | **G5** |
| 7 | DP global optimum; PID baseline; RL ramp-up on a toy SB3 environment | Watchdog and fallback path | |
| 8 | SAC outer loop, 5 seeds; **A3** | Actor export and on-device verification | |
| 9 | Reward and hyperparameter refinement | Full stack on device; **A4** | |
| 10 | — | Full PIL campaign: 6 scenarios x controllers x seeds | |
| 11 | VED out-of-distribution check; analysis; figures | AD3 measurement campaign | |
| 12 | Write-up and submission | | |

### 8.2 Gates

Each gate has a defined action on failure. The purpose of placing them this
early is that **every failure still leaves a paper** — a different one, but a
real one.

| ID | End of | Test | Action on failure |
|---|---|---|---|
| **G1** | W1 | **Feasibility floor:** measured throughput supports at least the aggressive config, 0.1 M MACs in 20 ms or less on core 1. This is a floor, not the deployed budget; G5 sets the latter | Descend the fallback ladder immediately; inform the professor in Week 1, not Week 10 |
| **G2** | W2 | Plant reproduces held-out i3 trips within the criterion in 6.1 | **Stop. Fix the physics before any ML work.** Nothing downstream is valid otherwise |
| **G3** | W3 | 10 ms loop closes end-to-end with p99 jitter at most 1 ms and zero dropped frames over a 10-minute run | Switch transport (native USB-JTAG vs external UART), or re-scope the loop to 20 ms. Decide here, not later |
| **G4** | W4 | Some model beats persistence by at least 10% RMSE at the 3 s horizon on validation | Forecasting contribution is weak; shift emphasis to claims C3, C4, C5, C6 |
| **G5** | W6 | Forecaster runs on-device within 40 ms on core 1, with model plus tensor arena at most 300 KB | Fallback ladder rungs 2 through 4 |

### 8.3 Risks

| ID | Risk | Mitigation |
|---|---|---|
| **R1** | **SAC does not converge.** RL is the identified skill gap, and RL is genuinely finicky | Ramp-up week in W7; SB3 defaults; action space limited to 3 dimensions; full week in W8. **The rule-based EMS and DP optimum are guaranteed-working comparisons, so the paper survives an RL failure** |
| R2 | Transformer does not fit | G1 plus the fallback ladder |
| R3 | A3 null: forecast does not help control | Pre-accepted (3.2). Publishable, and frees the memory budget |
| R4 | A1 null: PI does not beat plain | Pre-accepted (3.2) |
| R5 | macOS host jitter contaminates timing | MCU is clock master (4.5) |
| R6 | No PSRAM on the devkit | Resolved in Week 1 (7.4) |
| R7 | **Twelve weeks is tight even after cutting** | Write methods sections as they are built, from W4 onward, not all in W12. If two gates fail badly, cut an ablation rather than compress the writing |

---

## 9. Open items requiring verification

None of these block the implementation plan; each has a scheduled owner and week.

| Item | Resolved by | Week |
|---|---|---|
| ESP32-S3-DevKitM-1 module variant and PSRAM presence | **RESOLVED 2026-08-30: N8R8, 8 MB embedded PSRAM** (esptool chip_id). Memory is not a constraint; MACs remain binding. See `docs/hardware-inventory.md` | 1 |
| Effective int8 MACs/second with ESP-NN on the S3 | **RESOLVED 2026-08-30: 29.82 MMAC/s** (scalar int8 loop, 240 MHz, single core). G1 PASS with 6.1x margin. Phase 2 targets seq 32 / d_model 32 / 2 layers at 22.0 ms, 55% of the G5 budget. Lower bound: no ESP-NN vector kernels used. See `docs/g1-compute-budget.md` | 1 |
| **A MAC count is not a latency** | **RESOLVED 2026-08-31 by measurement.** The deployed encoder shape timed on silicon takes **36.46 ms**, against the 22.28 ms the MAC-count estimate gave: the estimate is 64% low. Softmax alone is 7.25 ms of the difference and the MAC count assigns it zero. The matmul rate itself validates G1 at 28.1 MMAC/s against 29.82 on a synthetic loop. It still fits the 40 ms budget, at 91%, on scalar C with no ESP-NN kernels, so the real margin is larger. Estimates stay useful for ranking arms and must not be quoted as latencies. See `docs/g5-latency.md` | G5 | 6 |
| Whether int8 quantisation costs more accuracy than the Pareto curve can absorb | **RESOLVED 2026-08-31: 0.95%.** float32 11.051 kW against int8 11.156 kW over three seeds, still 15.6% better than persistence. The model shrinks 3.56x, 71.7 KB to 20.2 KB, and the independently written cost model predicts its 20,664 bytes exactly. Calibration drew 4,096 windows from training trips only. QAT is not needed. This is ablation A2's first rung; the distilled student is not yet run | A2 | 6 |
| i3 dataset access terms and exact channel list | Downloading from IEEE DataPort | 1 |
| BMW i3 (60 Ah) vehicle and battery parameters, with citations | Parameter identification plus published specifications | 2 |
| Whether native USB-Serial-JTAG or external USB-UART gives lower loop latency | **PARTLY RESOLVED 2026-08-31.** The native peripheral carries the loop with zero malformed and zero lost frames over 59,650 loops, and loop jitter of 25 us against a 1000 us limit. The transport is not a limiting factor, so the external UART was not needed to close G3 and remains unmeasured. Both are implemented behind one interface in `firmware/main/link.c` | G3 | 3 |
| **G3 fails its zero-dropped-frame criterion, and the cause is the host, not the loop** | **OPEN, raised and narrowed 2026-08-31.** Synchronous loop: 6 reply timeouts in 59,650, worst round trip 7,405 us. The recommended fix was then built, not deferred: the control task now requests the next state and acts on the most recent one it holds (`CTRL_PIPELINED` in `firmware/main/tasks.h`, both modes still compilable). Pipelined loop over the same 59,650: 0 timeouts, worst round trip **77 us**, jitter unchanged at 25 us, and **8 steps on a stale state**. The gate still fails, and what an event costs has changed completely: a synchronous miss put the loop at risk, a pipelined one means the controller used a state 10 ms older than intended. **The decision the gate must take is whether its criterion should separate a loop missing its own deadline, of which there are zero in both modes, from the host answering late, of which there are 8, bounded and handled.** Zero over ten minutes at 100 Hz against a general-purpose OS may not be reachable. The criterion is NOT being loosened here. **RE-MEASURED 2026-08-31 on the week 7 firmware, still OPEN.** The loop changed this week (real PID, larger frames), so the campaign was re-run in full: 59,650 loops, jitter p99 unchanged at 25 us, 4 late host replies rather than 8, 0 reply timeouts, 0 malformed frames, 0 frames lost. A new counter settles the half of the question that was previously an inference: `ctrl_late`, loops that missed their **own** deadline, reads **0** -- including throughout the injected fallback campaign. The two failures the criterion pools are now measured apart, and one of them is empty. See `docs/g3-loop-timing.md` and `docs/week7-fallback.md` | G3 | 7 |
| Whether the plant validation criterion in 6.1 is achievable as stated | G2 | 2 |
| Whether G4's threshold is worth what it claims to test | **RAISED 2026-08-31, OPEN.** A 257-parameter ridge on flattened windows already beats persistence by 14.5% RMSE at the 3 s horizon on validation, against G4's required 10%. The gate is passed before any proposed model exists, so passing it is not evidence for one. Reporting every arm against the ridge as well as persistence is adopted now; restating the threshold as 10% over the ridge (10.177 kW at 3 s) is a gate change and is left for G4 to decide. See `docs/forecast-guards.md` | G4 | 4 |
| Which arm goes on the device, given that accuracy barely separates them | **PARTLY RESOLVED 2026-08-31.** Costed against G1's measured 29.82 MMAC/s and the G5 limits. XGBoost is out: ~3.7 MB against a 300 KB budget, more than 12x over, so it stays an offline reference arm. The reported LSTM figure is a 5-seed ensemble at 99 ms and does not fit either; one model fits at 19.8 ms, half the budget. Ridge fits at 0.26 ms and 7.5 KB, reaching 87% of the achievable skill for 1.3% of the compute. Every arm is now costed at the moment it is scored. See `docs/forecast-ladder.md` and `docs/forecast-deploy-cost.csv` | G5 | 6 |
| XGBoost and PyTorch cannot share a process in either order on macOS | **RESOLVED 2026-08-31.** Two OpenMP runtimes: importing torch first segfaults a later XGBoost fit, fitting XGBoost first hangs a large LSTM forward pass. Both were reached by ordinary use. Fixed by import ordering in `src/evpil/forecast/_openmp.py`, applied session-wide by `tests/conftest.py`; `fit_lstm` also pins CPU threads. Proved by subprocess tests | Week 4 | 4 |
| **The outer energy-management loop has almost no headroom, so there may be nothing for SAC to learn** | **RAISED 2026-08-31 by the DP optimum, OPEN, and this one changes the shape of the paper.** With the speed trajectory fixed by the tracking constraint and cabin comfort priced at what it costs, the DP optimum **is** the constant action "regenerate as much as the pack will take": the two match to 0.000% on all four cycles, and the rule-based manager is within 0.16% of it (0.01% HWFET, 0.03% WLTC, 0.04% US06, 0.16% UDDS). This is a property of the action space, not of the optimiser. The plant's acceleration depends only on torque and grade, so the trajectory is *exactly* invariant to the outer action (proved in `tests/control/test_sim.py`); the discharge ceiling can only starve the tracker, which the tracking constraint forbids; the auxiliary derate is a comfort trade, a wash at a fair price; and the regeneration blend is monotone, so its optimum is a bound. **Ablation A3 is therefore predictably null before it is run** -- under a fixed trajectory the optimal action does not depend on future power, so a preview cannot help. That is stronger than the pre-acceptance in 3.2: it is a reason. Three routes, and the choice is the professor's: **(a)** report it as a negative result and let the contribution be the embedded study plus "a learned energy manager cannot beat two rules once tracking is a hard constraint", which the framing in section 1 already supports; **(b)** widen the outer loop's authority to eco-driving -- let it shape the speed reference inside a tolerance band with an arrival-time penalty -- which is the standard formulation in which preview genuinely pays, and which changes claim C3; **(c)** add the constraints that make the split non-trivial: battery thermal limits and an ageing cost, under which "always regenerate" stops being optimal. Route (b) is the most work and the most defensible as a method contribution; route (a) costs nothing and is publishable. **No route is being taken here.** Evidence in `docs/week7-control.md` and `docs/week7-control-baselines.csv` | Professor / C3 | 7 |

---

## 10. Version control note

This directory is not currently a git repository. The brainstorming workflow
expects design documents to be committed. Recommend running `git init` and
committing this spec before implementation begins, so that design revisions are
traceable alongside code.
