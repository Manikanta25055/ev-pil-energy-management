# SPEED ESTIMATION AND SENSOR-FAULT DETECTION {#sec:estimation}

This section is a supporting result. The one energy gain found in the study sits in the speed loop, a level below the energy manager of Section @sec:ems. Results are PIL-evaluated when the code ran on the ESP32-S3 in the processor-in-the-loop (PIL) arrangement, with computation times target-measured, and host-simulated when they ran on the host only. Faults were injected in software, and no physical accelerometer was used. The detector and fallback are evaluated as monitoring functions only; no ISO 26262 or safety-of-the-intended-functionality claim is made.

## Where the Noise Loss Sits

Sensor noise raises the energy used under the rule-based manager. On US06 the energy, on the comparable scale of Section @sec:platform, rose from 190.98 Wh/km at the noise floor to 200.42 Wh/km at ten times the floor (PIL-evaluated). The speed loop turns the reading into a torque command at 100 Hz, so noise becomes alternating drive and brake commands. Either the manager decides worse on a noisy state, or the loop wastes energy on the reversals.

Simulation supports the second reading: with the manager fixed, replacing only the speed estimate cut 200.3 to 190.6 Wh/km at ten times the noise and torque reversals from 1,342 to 83 per km (host-simulated, five seeds).

## Two-State Kalman Speed Estimator

The estimator is a Kalman filter [@kalman1960] over the speed $v$ and an unknown acceleration $d$, which absorbs what the vehicle model gets wrong, such as extra mass or headwind. The prediction advances the speed with the road-load model $a_{m}$ and the commanded torque $\tau$. On the target the state acted on is one request old, so the prediction uses the command before last; only the target exposed this.

$$ \hat{v}^{-}_{k} = \hat{v}_{k-1} + \left[ a_{m}(\hat{v}_{k-1}, \tau_{k-j}) + \hat{d}_{k-1} \right] \Delta t, \qquad \hat{d}^{-}_{k} = \hat{d}_{k-1} $$ {#eq:estimation-predict}

Here $j = 1$ in the host loop, $j = 2$ on the target, and $\Delta t$ is 10 ms. Process allowances of $q = 0.002$ m/s and $q_{d} = 0.02$ m/s² were set on the first 600 s of the urban training cycle. The measurement $z_{k}$ corrects both states, with a variance $r^{2}$ re-estimated from the jitter of the reading.

$$ \nu_{k} = z_{k} - \hat{v}^{-}_{k}, \quad S_{k} = P^{-}_{vv} + r^{2}, \quad \hat{v}_{k} = \hat{v}^{-}_{k} + \frac{P^{-}_{vv}}{S_{k}} \nu_{k}, \quad \hat{d}_{k} = \hat{d}^{-}_{k} + \frac{P^{-}_{vd}}{S_{k}} \nu_{k} $$ {#eq:estimation-update}

Two firmware images differing only in this input ran on the target, on three cycles at the noise floor, a second US06 noise seed, and US06 at three and ten times the floor. The baseline acts on the raw reading. Table @tab:estimation-noise and Fig. @fig:estimation-noise give the result.

Table: tab:estimation-noise | Energy on the comparable scale and peak battery current for the baseline loop and the two-state estimator, PIL-evaluated, one run per cell. | width=col
| Setting | Baseline, Wh/km | Two-state, Wh/km | Peak current, baseline / two-state, A |
|---|---|---|---|
| UDDS, floor | 168.10 | 168.05 | 118 / 111 |
| HWFET, floor | 153.98 | 153.92 | 97 / 92 |
| US06, floor | 190.79 | 190.61 | 284 / 262 |
| US06, floor, second seed | 190.98 | 190.56 | 295 / 260 |
| US06, 3x noise | 191.27 | 190.67 | 330 / 273 |
| US06, 10x noise | 200.42 | 190.80 | 341 / 288 |

![fig:estimation-noise](paper/figures/fig-estimation-noise.png){width=col}
Caption: Energy on US06 against sensor-noise multiple for the baseline speed loop and the two-state Kalman estimator, PIL-evaluated.

The headline loss is taken against the second US06 floor run. Against it the baseline loop loses 9.44 Wh/km (4.9%) at ten times the noise and the two-state estimator 0.24 Wh/km; against the first floor run the losses are 9.63 and 0.19 Wh/km. The baseline's two floor runs differ by 0.19 Wh/km with only the noise seed changed, so the estimator's residual loss is about the size of run-to-run spread. The peak battery current falls from 341 A to 288 A, the worst control computation grows from 62 to 69 µs of a 10,000 µs period, and no step was late. At the noise floor the arms agree within 0.1% on the three cycles and within 0.22% on the second US06 seed, so no saving is claimed there.

The estimator was then set against a cheaper filter. A first-order low-pass filter on the reading, with its smoothing constant of 0.1 chosen on the training cycles at ten times the floor, ran beside the baseline and the estimator in two further noise blocks, at the floor and at ten times it (PIL-evaluated). Table @tab:estimation-lowpass gives all three arms.

Table: tab:estimation-lowpass | Baseline loop, low-pass filter and two-state Kalman estimator on US06 in two noise blocks (floor seeds 100 and 200, ten-times seeds 102 and 202). Loss is ten-times energy minus the arm's own floor. PIL-evaluated, rule-based manager. | width=col
| Arm | Block | Floor, Wh/km | 10x, Wh/km | Loss, Wh/km | Floor RMSE, m/s |
|---|---|---|---|---|---|
| Baseline | 100 | 191.15 | 200.80 | +9.65 | 0.035 |
| Baseline | 200 | 190.89 | 200.63 | +9.73 | 0.023 |
| Low-pass | 100 | 191.89 | 192.00 | +0.12 | 0.107 |
| Low-pass | 200 | 191.91 | 191.51 | -0.40 | 0.107 |
| Kalman | 100 | 191.14 | 190.78 | -0.36 | 0.035 |
| Kalman | 200 | 191.48 | 191.00 | -0.48 | 0.045 |

Most of the recovery belongs to filtering as such. Against the baseline of the same block the low-pass filter recovered 9.53 and 10.14 Wh/km and the estimator 10.01 and 10.21. The estimator's extra 0.47 and 0.07 Wh/km is of the order of run-to-run spread; the baseline's floor moved 0.26 Wh/km between blocks. The rule fixed beforehand would have credited filtering in general only if the low-pass filter recovered at least as much, so it is formally not met, but the margin does not justify crediting the energy recovery to the Kalman structure. The difference shows at the floor. The low-pass filter's clean energy was 0.38% and 0.53% above the baseline floor, and its clean tracking error was about three times higher, 0.107 against 0.023 to 0.045 m/s. What the estimator adds, on this evidence, is filtering without that clean-condition cost, on US06 and the seeds tested. Two blocks give a spread, not a population claim, and the estimator's floor tracking in them was four to five times its earlier run for a reason not established.

One criterion fixed before the run failed. Clean tracking on the urban cycle had to stay within 0.005 m/s of the baseline, and the estimator missed it by 0.004 m/s (0.0193 against 0.0104 m/s). The baseline's own two US06 floor runs differ by 0.011 m/s, so one run per cell cannot resolve the bound; it stays a failure because the bound was set first.

## Fault Detection From an Acceleration Residual, and Why It Failed

The first detector compared the speed reading with a speed dead-reckoned from measured acceleration. With an idealised accelerometer it caught 160 of 160 named faults within 0.21 s and raised no false alarm in 3.8 h (host-simulated), but on the target it raised one false alarm on a healthy sensor in 1.26 h (PIL-evaluated). On the 70 logged trips, logged acceleration and the acceleration implied by logged speed differ by a slow component of about 0.11 m/s². Over the two-second pull of the dead reckoning that leaves a standing gap of about 0.22 m/s against a threshold of 0.036 m/s, and the detector was flagged 99% of the time. It is not usable as tuned.

## Bias-Aware Fault Detector

The bias-aware detector changes the reference the reading is tested against. The dead-reckoned speed carries a state $b$ for the acceleration-channel error, learned with a 2 s time constant and subtracted before integration. A step test handles abrupt faults: a sensor offset arrives in one sample and channel wander does not, so the mean gap $\bar{g}$ of the last $h = 30$ samples is compared with that of the 30 before.

$$ \left| \bar{g}_{\text{new}} - \bar{g}_{\text{old}} \right| > t_{s} \sqrt{\frac{2 \max(s^{2}, r^{2})}{h}} + \alpha h \Delta t $$ {#eq:estimation-step}

Here $s^{2}$ is the pooled variance of the gap, $t_{s} = 6$, and $\alpha = 0.2$ m/s² allows for a changing channel error. The threshold was tuned on the training cycles only; the cases and criteria were not altered after results were seen.

The simulated cases combine five named faults with six acceleration-channel errors, one of them the slow disagreement replayed from four logged trips per data split, and a vehicle 10% heavier than the model. The detector raised no clean false alarm in 4.5 h on validation (HWFET) or 5.8 h on test (US06) and caught 551 and 533 of 560 named faults within 0.5 s (host-simulated), which misses the criteria fixed for it.

The detector was then replayed, settings unchanged, on the 70 logged trips at their native 10 Hz, 30.4 h in all (host-simulated replay). The trips carry no speed truth or health labels, so an alarm is false only if the channels were healthy, and the replay supplies zero torque and grade. Two quantities must be kept apart. Alarm onsets numbered 30, or 0.99 per hour, with 196 at standstill set apart under a rule fixed in advance; that meets the registered limit numerically but does not establish a population rate. The flag, however, was raised for a trip-weighted 59% of recorded time, which no deployed detector could accept. With the frozen-speed test disabled, a diagnostic added after the result, onsets rose to 1.9 per hour. Interpolating the logged channels to 100 Hz and adding the noise floor gave 16.2 onsets per hour, almost all from the step test. Interpolation does not create a 100 Hz accelerometer, so that figure is a stress diagnostic, not a validation at the target rate. The detector is not field-ready, and the 120 of 120 below rests on software-injected faults on a simulated acceleration channel.

On the target the host injected the faults and simulated the accelerometer, and the detector ran in C, matched to the Python version on 4,000 samples. Table @tab:estimation-faults and Fig. @fig:estimation-faults give the result for US06 (PIL-evaluated).

Table: tab:estimation-faults | Injected faults caught within 0.5 s on the target by fault type (PIL-evaluated). First campaign: 8 runs per type. Three noise draws: 24 runs per type. | width=page
| Fault | Earlier detector, first campaign | Bias-aware, first campaign | Bias-aware, three draws | Worst tracking error, three draws, m/s |
|---|---|---|---|---|
| Stuck | 7 of 8 | 8 of 8 | 24 of 24 | 0.62 |
| Dropout | 7 of 8 | 8 of 8 | 24 of 24 | 0.65 |
| Offset +0.5 m/s | 6 of 8 | 8 of 8 | 24 of 24 | 0.83 |
| Offset -0.5 m/s | 6 of 8 | 8 of 8 | 24 of 24 | 0.72 |
| Offset +3.0 m/s | 7 of 8 | 8 of 8 | 24 of 24 | 0.66 |
| All | 33 of 40 | 40 of 40 | 120 of 120 | 0.83 |

![fig:estimation-faults](paper/figures/fig-estimation-faults.png){width=col}
Caption: Faults caught within 0.5 s in the first campaign on the target, earlier detector against bias-aware detector (PIL-evaluated). Eight faults per type.

In the first campaign the bias-aware detector caught 40 of 40 faults within 0.32 s; the earlier detector caught 33 of 40 and raised 162 false alarms on one clean cycle. The 120 of 120 is these 40 faults repeated over three noise draws, so it counts software faults on a simulated sensor, not independent events. The flag dropped while the fault persisted in 47 of the 120 runs. No false alarm occurred in the one clean hour, which bounds the false-alarm rate below about 3 per hour at 95% confidence. No step was late; the worst control computation was 74 µs (target-measured).

## Learned Reviewers Against a Rule Monitor

A slower supervisory slot sits around the detector. Every 100 ms it receives twelve summary numbers and may hold or release a flag, switch the fallback speed or tighten the tests; it never commands torque. A hand-written rule monitor, a gated recurrent unit (GRU) [@cho2014] of 1,508 parameters and a FastGRNN [@kusupati2018] of 550 each filled the slot (host-simulated; the learned reviewers were not timed on the target). The GRU diagnosed better: while the detector's flag was down, it still labelled a real fault correctly in 88% of blocks against 1% for the monitor. In the loop the order reversed (Fig. @fig:estimation-reviewers). The monitor cut the worst peak tracking error through a fault from 3.7 to 1.2 m/s on validation and from 5.1 to 1.4 m/s on test, while the GRU reached 9.7 and 10.8 m/s and the FastGRNN 3.0 and 12.8 m/s, and both raised clean false alarms.

![fig:estimation-reviewers](paper/figures/fig-estimation-reviewers.png){width=col}
Caption: Worst peak tracking error through any of 560 named faults for each reviewer on the controller with no delay (host-simulated). No reviewer means the bias-aware detector alone.

On the target the monitor looked slightly better than the detector alone in the first run (largest error 0.61 against 0.67 m/s) but worse over three noise draws, 1.32 against 0.83 m/s, with three alarms left raised (PIL-evaluated). No benefit is claimed.

## Fused Fallback Estimator

A fused fallback estimator learns both fallback errors, from the acceleration channel and from the model, while the sensor is trusted and carries them through a flagged period. On the validation highway cycle its worst error was 0.62 m/s against 3.74 m/s for the detector alone; on US06 it was best in six of seven conditions and worst, at 2.59 m/s, with the vehicle 10% heavier than the model, for a reason not tested. It has not been ported to C or run on the target (host-simulated only).
