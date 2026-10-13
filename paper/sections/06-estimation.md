# SPEED ESTIMATION AND SENSOR-FAULT DETECTION {#sec:estimation}

The positive results of the study concern the speed loop, one level below the energy manager of Section @sec:ems. Results are MEASURED when they ran on the ESP32-S3 in the processor-in-the-loop (PIL) arrangement, and SIMULATED when they ran on the host only. Faults were injected in software; no physical accelerometer was used.

## Where the Noise Loss Sits

Speed-sensor noise raises the energy used under the rule-based manager. On US06 the equivalent energy rose from 190.98 Wh/km at the noise floor to 200.42 Wh/km at ten times the floor (MEASURED). The speed loop turns the reading into a torque command at 100 Hz, so noise becomes alternating drive and brake commands. Two readings are possible: the energy manager decides worse on a noisy state, or the speed loop wastes energy on the reversals.

The simulation supports the second reading. With the same manager in every arm, the baseline loop used 200.3 Wh/km at ten times the noise, and replacing only the speed estimate gave 190.6 Wh/km (SIMULATED, five seeds). Torque reversals fell from 1,342 to 83 per km in the same runs. The manager was unchanged, so the loss sits in the speed loop; the loss per reversal was not measured.

## Two-State Kalman Speed Estimator

The estimator is a Kalman filter [@kalman1960] over the speed $v$ and an unknown acceleration $d$, which absorbs what the vehicle model gets wrong, such as extra mass or headwind. The prediction advances the speed with the road-load model $a_{m}$ of the feedforward and the commanded torque $\tau$. In the pipelined loop of the target the state acted on is one request old, so the prediction must use the command before last; only the target exposed this.

$$ \hat{v}^{-}_{k} = \hat{v}_{k-1} + \left[ a_{m}(\hat{v}_{k-1}, \tau_{k-j}) + \hat{d}_{k-1} \right] \Delta t, \qquad \hat{d}^{-}_{k} = \hat{d}_{k-1} $$ {#eq:estimation-predict}

Here $j = 1$ in the host loop, $j = 2$ on the target, and $\Delta t$ is 10 ms. Process allowances of $q = 0.002$ m/s and $q_{d} = 0.02$ m/s² were set on the first 600 s of the urban training cycle. The measurement $z_{k}$ corrects both states through the innovation $\nu_{k}$, with a variance $r^{2}$ re-estimated from the jitter of the reading.

$$ \nu_{k} = z_{k} - \hat{v}^{-}_{k}, \quad S_{k} = P^{-}_{vv} + r^{2}, \quad \hat{v}_{k} = \hat{v}^{-}_{k} + \frac{P^{-}_{vv}}{S_{k}} \nu_{k}, \quad \hat{d}_{k} = \hat{d}^{-}_{k} + \frac{P^{-}_{vd}}{S_{k}} \nu_{k} $$ {#eq:estimation-update}

Two firmware images differing only in this input were run on the target, on three cycles at the noise floor, a second seed on US06, and US06 at three and ten times the floor, with noise on every measured channel. Table @tab:estimation-noise and Fig. @fig:estimation-noise give the result.

Table: tab:estimation-noise | Energy on the comparable scale and peak battery current for the baseline loop and the two-state estimator, MEASURED, one run per cell. | width=col
| Setting | Baseline, Wh/km | Two-state, Wh/km | Peak current, A |
|---|---|---|---|
| UDDS, floor | 168.10 | 168.05 | 118 / 111 |
| HWFET, floor | 153.98 | 153.92 | 97 / 92 |
| US06, floor | 190.79 | 190.61 | 284 / 262 |
| US06, floor, second seed | 190.98 | 190.56 | 295 / 260 |
| US06, 3x noise | 191.27 | 190.67 | 330 / 273 |
| US06, 10x noise | 200.42 | 190.80 | 341 / 288 |

![fig:estimation-noise](paper/figures/fig-estimation-noise.png){width=col}
Caption: Energy on US06 against sensor-noise multiple for the baseline speed loop and the two-state Kalman estimator, MEASURED on the target.

At ten times the noise the baseline loop loses 9.44 Wh/km (4.9%) against its own floor result, and the two-state estimator loses 0.24 Wh/km. The peak battery current falls from 341 A to 288 A. The worst control computation grows from 62 to 69 µs of a 10,000 µs period, and no step was late. At the noise floor the arms agree within 0.1%, the size of the baseline's own run-to-run difference, so no saving is claimed there.

One pre-registered criterion failed. Clean tracking on the urban cycle had to stay within 0.005 m/s of the baseline, and the estimator missed it by 0.004 m/s (0.0193 against 0.0104 m/s). The baseline's two US06 runs differ by 0.011 m/s with nothing changed, so one run per cell cannot resolve the bound; it stays a failure because the bound came first.

## Fault Detection From an Acceleration Residual, and Why It Failed

The first detector compared the speed reading with a speed dead-reckoned from measured acceleration. With an idealised accelerometer, true acceleration plus white noise, it caught 160 of 160 named faults within 0.21 s and raised no false alarm in 3.8 h of clean driving (SIMULATED).

On the target it raised one false alarm on a healthy sensor in 1.26 h (MEASURED). The alarm recurred at the same control step in repeated runs and in a host replay, because each campaign cell used one fixed noise seed. The replay showed that the dead-reckoned speed had drifted 0.018 m/s low while the speed noise averaged 0.013 m/s high, and the threshold allowed for the second error only.

Against 70 logged trips (30 h, no sensor fault) the logged acceleration and the acceleration implied by logged speed differ by a slow component of about 0.11 m/s². Over the two-second pull of the dead reckoning this leaves a standing gap of about 0.22 m/s against a threshold of 0.036 m/s, and the detector was flagged 99% of the time. The logs are 10 Hz and the firmware 100 Hz, so the flagged share is indicative. The detector is not usable as tuned.

## Bias-Aware Fault Detector

The bias-aware detector keeps the filter above and changes the reference it is tested against. The dead-reckoned speed carries a state $b$ for the acceleration-channel error, learned with a 2 s time constant and subtracted before integration, so a standing offset opens no gap. A step test handles abrupt faults: a sensor offset arrives in one sample and channel wander does not, so the mean gap $\bar{g}$ of the last $h = 30$ samples is compared with that of the 30 before, and the slow error common to both cancels.

$$ \left| \bar{g}_{\text{new}} - \bar{g}_{\text{old}} \right| > t_{s} \sqrt{\frac{2 \max(s^{2}, r^{2})}{h}} + \alpha h \Delta t $$ {#eq:estimation-step}

Here $s^{2}$ is the pooled sample variance of the gap, $t_{s} = 6$ and $\alpha = 0.2$ m/s² allows for a changing channel error. The 20-sample mean test remains, with the dead reckoning's own standard error of 0.15 m/s added to its threshold. The step threshold was tuned on the training cycles only, and the registered cases and criteria were not altered after the result was seen.

The registered cases combine five named faults with six acceleration-channel errors and a vehicle 10% heavier than the model. In simulation the detector raised no clean false alarm on validation (HWFET) or test (US06) and caught 551 and 533 of 560 named faults within 0.5 s. It does not pass the registered criteria: the nine late detections on validation are +0.5 m/s offsets at ten times the noise, flagged only when they end, and the 27 late detections on test were not characterised. The earlier detector, on the same cases, was flagged for 75% to 98% of clean validation driving in five of seven.

On the target the host injected the faults and the detector ran in C, matched step by step to the Python version on 4,000 samples. Table @tab:estimation-faults and Fig. @fig:estimation-faults give the result for US06 (MEASURED).

Table: tab:estimation-faults | Injected faults caught within 0.5 s on the target by fault type (MEASURED). First campaign: 8 runs per type. Three noise draws: 24 runs per type. | width=page
| Fault | Earlier detector, first campaign | Bias-aware, first campaign | Bias-aware, three draws | Worst tracking error, three draws, m/s |
|---|---|---|---|---|
| Stuck | 7 of 8 | 8 of 8 | 24 of 24 | 0.62 |
| Dropout | 7 of 8 | 8 of 8 | 24 of 24 | 0.65 |
| Offset +0.5 m/s | 6 of 8 | 8 of 8 | 24 of 24 | 0.83 |
| Offset -0.5 m/s | 6 of 8 | 8 of 8 | 24 of 24 | 0.72 |
| Offset +3.0 m/s | 7 of 8 | 8 of 8 | 24 of 24 | 0.66 |
| All | 33 of 40 | 40 of 40 | 120 of 120 | 0.83 |

![fig:estimation-faults](paper/figures/fig-estimation-faults.png){width=col}
Caption: Faults caught within 0.5 s in the first campaign on the target, earlier detector against bias-aware detector (MEASURED). Eight faults per type.

In the first campaign the bias-aware detector caught 40 of 40 faults within 0.32 s. The earlier detector caught 33 of 40 and raised 162 false alarms on one clean cycle under the wandering channel. With three noise draws the bias-aware detector caught 120 of 120, with no false alarm in one clean hour, no late step and a worst control computation of 74 µs.

## Learned Reviewers Against a Rule Monitor

A slower supervisory slot sits around the detector. Every 100 ms it receives twelve summary numbers and may hold a flag, release it, switch the fallback speed, or tighten the tests; it never commands torque. The slot was filled by a hand-written rule monitor, a gated recurrent unit (GRU) [@cho2014] of 1,508 parameters and a FastGRNN [@kusupati2018] of 550, on the controller or behind a link with 70 to 1000 ms delay (SIMULATED throughout).

Scored on diagnosis alone over 540,960 validation blocks, the GRU was better: it recognised a real fault in 99% of blocks with a flag raised and 88% with none, against 94% and 1% for the monitor. In the loop the order reversed (Fig. @fig:estimation-reviewers). The monitor cut the worst peak tracking error through a fault from 3.7 to 1.2 m/s on validation and from 5.1 to 1.4 m/s on test. The GRU reached 9.7 m/s on validation and 10.8 m/s on test in its worst cases, the FastGRNN 3.0 and 12.8 m/s, and raised clean false alarms. Offline agreement did not predict closed-loop benefit. A correct diagnosis keeps the flag up, and both fallback speeds then drift further than the small offset they guard against.

![fig:estimation-reviewers](paper/figures/fig-estimation-reviewers.png){width=col}
Caption: Worst peak tracking error through any of 560 named faults for each reviewer on the controller with no delay (SIMULATED). No reviewer means the bias-aware detector alone.

The target corrected the monitor's result. In the first run it looked slightly better than the detector alone (largest error 0.61 against 0.67 m/s). Over three noise draws it was 1.32 against 0.83 m/s, with three alarms left raised where the detector alone left none (MEASURED). No benefit on the target is claimed.

## Fused Fallback Estimator

Both fallback speeds drift, one with the acceleration error and one with the model error. The fused fallback estimator is one filter over speed, model error and accelerometer error that learns both while the sensor is trusted and carries them through a flagged period. In simulation on the validation highway cycle the worst error was 0.62 m/s against 3.74 m/s for the detector alone, with no stuck flag. On US06, against the detector alone and the rule monitor, it was best in six of seven conditions, with two alarms left stuck, and worst in the seventh: with the vehicle 10% heavier than the model the worst error was 2.59 m/s. The cause was not tested; the settings came from gentle urban driving. This estimator has not been ported to C and has not run on the target (SIMULATED only).
