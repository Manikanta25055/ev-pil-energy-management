# ENERGY MANAGEMENT AFTER THE CORRECTION {#sec:ems}

This section compares a hand-written energy manager with a learned one on the corrected vehicle model of Section @sec:plant. Both run on the microcontroller. The question is narrow. With the speed profile fixed by a tracking loop and only three actuation numbers to choose, can a learned policy use less energy than the rules, on the corrected vehicle model? It cannot.

## Control Structure and the Rule-Based Manager

Two loops share the vehicle. An inner speed loop runs at 100 Hz on the microcontroller and turns the speed reference into motor torque. A slower supervisory energy manager runs at 10 Hz and sends three numbers: the fraction of braking energy routed to the machine (regeneration blend), a ceiling on battery discharge power, and the fraction of the auxiliary load, mainly cabin heating, to shed. The energy manager cannot change the speed reference, so no controller can save energy by driving slower.

The rule-based energy manager is a pure function of state of charge (SOC) and speed, with no memory. Regeneration is full below SOC 0.85, tapers linearly to zero at 0.94, and fades out below 2 m/s so that stops stay predictable. The discharge ceiling is 125 kW above SOC 0.20 and falls linearly to 40 kW at SOC 0.07. Auxiliary shedding stays at zero above SOC 0.15 and rises to a cap of 30% as the pack empties. Two of these constants copy plant limits (0.94 is the battery's maximum SOC and 0.07 its minimum); the others were set by engineering judgement and not tuned against any test cycle. Table @tab:ems-hyper lists them next to the learned policy's settings.

## Headroom Under a Fixed Speed Profile

An offline dynamic-programming (DP) optimum [@bellman1957] was computed on the WLTC class 3b cycle and the three dynamometer schedules UDDS, HWFET and US06 [@epacycles], at a starting SOC of 0.80 and 12 degrees C. The rule-based manager sits within 0.01% to 0.16% of it: 153.90 against 153.89 Wh/km on the highway cycle (HWFET), 167.93 against 167.67 on the urban cycle (UDDS), 190.47 against 190.39 on the aggressive cycle (US06) and 175.99 against 175.94 on WLTC class 3b (SIMULATED). The optimum is a constant instruction: recover as much braking energy as the pack accepts. The DP held the discharge ceiling at its maximum, and the HWFET rule value is unchanged on the corrected model.

The bound follows from the structure. Acceleration depends on torque and grade alone, so regeneration blend and shedding cannot alter the speed trajectory, and a ceiling can only remove power the speed loop needs, which the tracking constraint forbids. Shedding is priced at the energy it saves, which makes it neutral. A learned policy in this task therefore has at most 0.16% to gain, and the experiment cannot tell a good learner from a poor one by energy alone. A gain needs a task with headroom, and Section @sec:planning shows where one exists.

## The Learned Policy

The learned policy is trained with Soft Actor-Critic (SAC) [@haarnoja2018]. It observes eight scaled quantities: SOC, speed, acceleration, battery temperature, road grade, tracking error, and the mean and maximum of the next 3 s of reference-implied traction power. It outputs the same three numbers as the rules, mapped affinely from $[-1, 1]$ to the physical ranges. The reward is the negative sum of battery energy, shed auxiliary energy at the price it saves, a tracking-error term and penalties for excess current and low SOC; Table @tab:ems-hyper gives the weights. The deployed actor is 8-64-64-3 with 4,931 parameters. Training used the WLTC3B and UDDS cycles with the HWFET cycle for validation, five seeds of 200,000 steps each.

Only one reward design and one hyperparameter set were run. There was no sweep. The tracking deficit reported below may reflect the tracking weight. This was not tested.

Table: tab:ems-hyper | Settings of the learned policy and the rule-based manager. Library values are defaults of the Stable-Baselines3 SAC class; the others are set in the training script. | width=page
| Item | Value | Origin |
|---|---|---|
| Actor and critic hidden layers | 64, 64 | script; 4,931 actor parameters |
| Learning rate | 0.0003 | library default |
| Batch size, replay buffer | 256, 1,000,000 | library default |
| Discount, soft-update rate | 0.99, 0.005 | library default |
| Entropy coefficient | automatic | library default |
| Steps before learning starts | 1,000 | script |
| Training steps, seeds | 200,000, 5 | script |
| Episode length | 300 outer steps (30 s) | script default |
| Reward: energy, shed heat | 1.0 per Wh each | script |
| Reward: tracking | 5.0 per m²/s² | script |
| Reward: current, low SOC | 2.0 per A s over limit; 50 per unit SOC below floor plus 0.02 | script |
| Rule thresholds | see text | judgement; two equal plant limits |

The comparable energy scale charges shed cabin heat back at exactly the energy it saved, so a policy that switches the heater off cannot look efficient. All ranking uses it.

After the model correction, five seeds per arm were retrained and scored on HWFET (SIMULATED). The arm without forecast channels reaches 154.86 +- 0.51 Wh/km (seed standard deviation) against 153.90 for the rules, and the arm with them reaches 155.12 +- 0.82. The no-forecast seed with the lowest validation energy, seed 3 at 154.21 Wh/km, was exported to the target. It costs 0.121 ms per decision on average and 19.3 KB on the ESP32-S3 [@esp32s3], and its outputs match the host implementation to 2e-06 against a tolerance of 2e-05 (MEASURED, on another seed of the same network). The worst policy computation in the campaign loop took 0.84 ms.

## Forecast Ablation

The forecast ablation removes two observation channels, the mean and maximum of the next 3 s of reference-implied traction power, which are computed from the reference speed. It is not the Transformer forecaster of Section @sec:forecast, which never ran inside the energy-management loop. Seeds are paired. On the original vehicle model the difference (with minus without) is +0.240 Wh/km with a 95% bootstrap interval of -0.669 to +1.228; after retraining on the corrected model it is +0.262 with an interval of -0.698 to +0.982 (both SIMULATED, five paired seeds). Both intervals contain zero. No equivalence margin was set, so the result is the absence of a detected effect and not proof of none. Under a fixed speed profile the best action does not depend on what happens next, which agrees with the DP result. The deployed policy was trained without them.

## Corrected Campaign on the Target

The campaign closes the loop in the processor-in-the-loop (PIL) arrangement: the control software runs on the microcontroller at 100 Hz, and the host simulates the vehicle, motor, inverter and battery. An arm is one controller under test; a setting is one combination of conditions. Six factors were each swept across three levels, one at a time from a US06 baseline at 12 degrees C: driving cycle (UDDS, HWFET, US06), road grade (+0.03, 0 and -0.03 rad), starting SOC (0.85, 0.55, 0.25), sensor noise (1x, 3x and 10x a stated floor), communication delay (none, 10 ms, 30 ms) and driver aggression (a time scaling of the reference by 1.0, 1.25 and 1.5). Each setting ran once per arm: 36 runs, 32 of them in the valid set, and 2,282,832 control steps, none late against the loop's own deadline (MEASURED).

The two delay settings above zero are excluded because the host cannot answer within the delay and neither controller follows the cycle (tracking error 25.7 to 43.4 m/s); the exclusion rule, a tracking error of 1 m/s or more, was fixed after those runs were seen, and the largest valid error is 0.504 m/s. The remaining 16 settings are not 16 distinct conditions. Five of them, labelled R in Table @tab:ems-campaign, are the same nominal US06 condition (mixed driving, no delay, flat road, 1x noise, driver 1.0), reached through different axes; the SOC 0.55 setting starts at a different charge and is not one. The valid set therefore holds 12 distinct conditions. Three of the five repeats used noise seed 0, so they differ mainly in link timing and run order, which is why their spread is a floor on run-to-run variation and not a full estimate of it.

The repeats give the run-to-run spread directly. The rule arm used 190.73 to 191.41 Wh/km across them, a range of 0.36%, and the learned arm 191.43 to 191.98, 0.29%. The paired difference (learned minus rules) is +0.40% on average with a standard deviation of 0.22 and a 95% t-interval of 0.13 to 0.67 (n = 5). The difference in dropped frames between the two arms is unrelated to the energy difference (r = -0.03 over the 16 settings).

Table @tab:ems-campaign and Fig. @fig:ems-campaign give the per-setting result. The learned policy uses less energy in 1 of the 16 settings, uphill at -0.02%, which is 0.05 percentage points below the lowest nominal repeat and smaller in size than the 0.36% spread of the rule arm. Averaged over the 16 settings it uses 0.94% more, with a median of +0.35%. Counting each distinct condition once, with the five repeats merged into their mean, the learned policy is higher in 11 of 12. The mean difference is +1.11% (bootstrap 95% interval 0.27 to 2.27) and the median +0.31% (0.17 to 0.76). An exact Wilcoxon signed-rank test gives p = 0.001 and a sign test p = 0.006, both two-sided and over the 12 conditions. Two settings carry the mean. These are downhill (+5.71%) and 10x sensor noise (+4.45%).

Table: tab:ems-campaign | Corrected PIL campaign, 16 valid settings, one run per setting per controller, comparable energy scale. R marks the five repeats of the nominal US06 condition; Mixed is that condition reached through the driving-condition axis. MEASURED. | width=page
| Setting | Cycle | Rules (Wh/km) | Learned (Wh/km) | Difference (%) | Rules RMSE (m/s) | Learned RMSE (m/s) |
|---|---|---|---|---|---|---|
| Urban | UDDS | 168.13 | 169.30 | +0.70 | 0.013 | 0.016 |
| Highway | HWFET | 153.96 | 154.40 | +0.29 | 0.004 | 0.004 |
| Mixed (R) | US06 | 191.41 | 191.48 | +0.03 | 0.044 | 0.226 |
| No delay (R) | US06 | 190.73 | 191.76 | +0.54 | 0.014 | 0.230 |
| Uphill 0.03 rad | US06 | 305.26 | 305.21 | -0.02 | 0.039 | 0.237 |
| Flat (R) | US06 | 190.75 | 191.43 | +0.36 | 0.015 | 0.229 |
| Downhill 0.03 rad | US06 | 79.30 | 83.83 | +5.71 | 0.010 | 0.193 |
| SOC 0.85 | US06 | 190.93 | 191.37 | +0.23 | 0.026 | 0.233 |
| SOC 0.55 | US06 | 191.00 | 191.63 | +0.33 | 0.027 | 0.195 |
| SOC 0.25 | US06 | 190.80 | 191.20 | +0.21 | 0.021 | 0.168 |
| Noise 1x (R) | US06 | 190.75 | 191.81 | +0.55 | 0.021 | 0.230 |
| Noise 3x | US06 | 191.33 | 192.90 | +0.82 | 0.014 | 0.218 |
| Noise 10x | US06 | 201.55 | 210.53 | +4.45 | 0.055 | 0.192 |
| Driver 1.0 (R) | US06 | 190.99 | 191.98 | +0.52 | 0.028 | 0.228 |
| Driver 1.25 | US06 | 197.16 | 197.38 | +0.11 | 0.045 | 0.331 |
| Driver 1.5 | US06 | 204.46 | 204.75 | +0.14 | 0.098 | 0.504 |

![fig:ems-campaign](paper/figures/fig-ems-campaign.png){width=page}
Caption: Corrected campaign, 16 valid settings: (a) paired energy difference of the learned policy relative to the rules, positive meaning more energy, with the range of the five nominal repeats as a shaded band and the repeats hatched; (b) tracking RMSE of both controllers on a log axis. MEASURED, one run per setting.

On tracking, the learned policy has a root-mean-square error (RMSE) of 0.17 to 0.24 m/s on most US06-based settings, 0.33 m/s at driver aggression 1.25 and 0.504 m/s at 1.5, against 0.010 to 0.098 m/s for the rules. On UDDS and HWFET the learned policy stays at 0.016 and 0.004 m/s. US06 was held out of training, but it was also the cycle of the earlier campaign that led to the model fix, so it was not unseen by the authors, and the deficit appears on the cycles built on it.

The verdict covers this task only: one vehicle model at one ambient temperature, one board, one learned algorithm with one reward design, and speed fixed by the tracking loop.

## The Earlier Campaign

An earlier campaign on the uncorrected model showed the opposite sign: the learned policy used less energy in 14 of the same 16 settings, by 8.28% on average. That gain came from the vehicle model, not from the policy. Section @sec:plant gives the mechanism, the controller-free sweep that exposed it and the checks it implies. After the fix and retraining it disappears.

## Behaviour Under Link Outage

When the host link drops, the firmware reacts in two ways. If the 100 ms energy-manager setpoint is more than 300 ms old, the rule-based action runs inside the speed loop. If no vehicle state has arrived for more than five control periods (50 ms), the torque command is ramped to zero at 10 N m per step and the integrator is frozen. The fallback ablation compiles these two behaviours out; the firmware then holds the last command.

The sweep used outage lengths of 0.2, 0.5, 1, 2, 3, 4, 5 and 10 s, eight paired onsets on US06 per length, with the retrained policy in the loop and the corrected model (MEASURED). Fig. @fig:ems-outage shows the worst peak speed error. Removing the handling gives the smaller worst error from 0.2 s to 4 s (0.18 against 0.23 m/s at 0.2 s, 3.73 against 6.67 m/s at 4 s). At 5 s the order reverses, 7.40 m/s with the handling against 7.97 without, so the crossover lies between 4 and 5 s; no point inside that interval was measured. At 10 s the worst error is 13.3 m/s with the handling and 18.2 m/s without. The median is less regular: the handling has the lower median at 4 s (1.21 against 1.55 m/s) and at 10 s (3.72 against 5.33 m/s), and the higher one at 5 s (1.64 against 1.44 m/s).

![fig:ems-outage](paper/figures/fig-ems-outage.png){width=col}
Caption: Worst peak speed error against outage length, with the fallback handling on and off, on the corrected model. MEASURED, eight onsets per length; lines join measured points only.

Holding a stale command works for a second or two and fails once the reference has moved on; the handling gives up accuracy early and loses less late. This is a description of behaviour under a link fault, not a functional-safety claim.
