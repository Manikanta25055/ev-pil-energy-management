# ENERGY MANAGEMENT: RULES AGAINST A LEARNED POLICY {#sec:ems}

A learned energy manager is compared here with a hand-written one, with both running on the microcontroller and driving the simulated vehicle of Section @sec:plant. The learned one does not win.

## Control Structure and the Rule-Based Manager

Two loops share the vehicle. An inner speed loop runs at 100 Hz on the microcontroller and turns the speed reference into motor torque. A slower supervisory energy manager runs at 10 Hz and sends three numbers: the fraction of braking energy routed to the machine (regeneration blend), a ceiling on battery discharge power, and the fraction of the auxiliary load, mainly cabin heating, to shed. The energy manager cannot change the speed reference, which stops a controller from saving energy by driving slower.

The rule-based energy manager is a pure function of state of charge (SOC) and speed, with no memory. Regeneration is full below SOC 0.85, tapers linearly to zero at 0.94, and fades out below 2 m/s so that stops stay predictable. The discharge ceiling is 125 kW above SOC 0.20 and falls linearly to 40 kW at SOC 0.07. Auxiliary shedding stays at zero above SOC 0.15 and rises to a cap of 30% as the pack empties. The constants were not tuned against any test cycle.

The room for improvement is small. An offline dynamic-programming optimum [@bellman1957] was computed on the WLTC class 3b cycle and the three dynamometer schedules UDDS, HWFET and US06 [@epacycles], and the rule-based manager sits within 0.01% to 0.16% of it: 153.90 against 153.89 Wh/km on the highway cycle (HWFET), 167.93 against 167.67 on the urban cycle (UDDS) and 190.47 against 190.39 on the aggressive cycle (US06). The optimum is a constant instruction: recover as much braking energy as the pack accepts. With speed fixed by the inner loop, the discharge ceiling can only remove power the speed loop needs, and cabin shedding is priced at what it saves. A learned policy therefore has at most 0.16% to gain (SIMULATED).

## The Learned Policy

The learned policy is trained with Soft Actor-Critic (SAC) [@haarnoja2018]. It observes eight scaled quantities: SOC, speed, acceleration, battery temperature, road grade, tracking error, and the mean and maximum of the next 3 s of reference-implied traction power. It outputs the same three numbers as the rules, mapped affinely from $[-1, 1]$ to the physical ranges. The reward is the negative sum of battery energy, shed auxiliary energy at the price it saves, a tracking-error term and penalties for excess current and low SOC. The deployed actor is 8-64-64-3 with 4,931 parameters. Training used the WLTC3B and UDDS cycles, with the HWFET cycle for validation and US06 sealed for the final campaign. Each arm used 5 seeds and 200,000 steps per seed.

The comparable energy scale charges shed cabin heat back at exactly the energy it saved. Without it, a policy that switches the heater off would look efficient on raw Wh/km while delivering a less comfortable vehicle, and every trained arm here scores lower than the rules on the raw figure and higher on the comparable one. All ranking uses the comparable scale.

Seed selection used validation only. After the model correction described below, five seeds per arm were retrained and scored SIMULATED on HWFET: the no-forecast arm reaches 154.86 +- 0.51 Wh/km (seed standard deviation) against 153.90 for the rules, and the arm with the forecast reaches 155.12 +- 0.82. The no-forecast seed with the lowest validation energy, seed 3 at 154.21 Wh/km, was exported to the target. A policy of this shape costs 0.121 ms per decision on average and 19.3 KB of memory on the ESP32-S3 [@esp32s3], and its outputs match the host implementation to 2e-06 against a tolerance of 2e-05 (MEASURED on another seed of the same network). Inside the campaign loop the worst policy computation was 0.84 ms.

## Forecast Ablation

The forecast ablation removes the two forecast channels from the observation, holds everything else fixed, and compares paired seeds. On the original vehicle model the difference (with minus without forecast) is +0.240 Wh/km with a 95% interval of -0.669 to +1.228 (SIMULATED). After retraining on the corrected model it is +0.262 Wh/km with an interval of -0.698 to +0.982 (SIMULATED). Both intervals contain zero.

The forecaster of Section @sec:forecast is accurate at a 3 s horizon, and this controller still gains nothing from it. Under a fixed speed profile the best action does not depend on what happens next, which matches the dynamic-programming result above. The forecast is not worth its on-target cost to this controller, so the deployed policy is the one trained without it. A policy trained with the forecast and run with two blank inputs would be one that no training run had seen.

## Processor-in-the-Loop Campaign

The campaign closes the loop in the processor-in-the-loop (PIL) arrangement: the control software runs on the microcontroller at 100 Hz, and the host simulates the vehicle, motor, inverter and battery. Six factors were each swept across three levels, one factor at a time from a US06 baseline: driving cycle (UDDS, HWFET, US06), road grade (+0.03, 0 and -0.03 rad), starting SOC (0.85, 0.55, 0.25), sensor noise (1x, 3x and 10x a stated floor), communication delay (none, 10 ms, 30 ms) and driver aggression (a time scaling of the reference by 1.0, 1.25 and 1.5). Each cell ran once per controller with its own noise seed, giving 36 runs and 2,282,832 control steps, of which 0 were late against the loop's own deadline (MEASURED). Vehicle mass was not an axis of this campaign.

The two delay settings above zero are excluded. The delay is injected by making the host wait before each reply, so at 10 ms on a 10 ms loop the host cannot keep up, and neither controller follows the cycle (tracking error 25.7 to 43.4 m/s). That axis therefore measures how fast the host can answer, which says nothing about tolerance to link delay. The rule, tracking error of 1 m/s or more for either controller, was fixed after those runs were seen; the largest valid error is 0.504 m/s. The remaining 16 settings form the valid set.

Table @tab:ems-campaign and Fig. @fig:ems-campaign give the result. The learned policy uses less energy than the rule-based manager in 1 of the 16 settings, uphill on US06 at -0.02%, a difference smaller than the 0.16% mean spread between two identical rule-arm campaigns. Averaged over the 16 settings it uses 0.94% more. The largest deficits are downhill (+5.71%) and 10x sensor noise (+4.45%); the other 13 settings lie between 0.03% and 0.82%. On tracking, the learned policy has a root-mean-square error (RMSE) of 0.17 to 0.24 m/s on most US06-based settings, 0.33 m/s at driver aggression 1.25 and 0.504 m/s at 1.5, against 0.010 to 0.098 m/s for the rules.

Table: tab:ems-campaign | Corrected PIL campaign, 16 valid settings, one run per cell per controller, comparable energy scale. MEASURED. | width=page
| Setting | Cycle | Rules (Wh/km) | Learned (Wh/km) | Difference (%) | Rules RMSE (m/s) | Learned RMSE (m/s) |
|---|---|---|---|---|---|---|
| Urban | UDDS | 168.13 | 169.30 | +0.70 | 0.013 | 0.016 |
| Highway | HWFET | 153.96 | 154.40 | +0.29 | 0.004 | 0.004 |
| Mixed | US06 | 191.41 | 191.48 | +0.03 | 0.044 | 0.226 |
| No delay | US06 | 190.73 | 191.76 | +0.54 | 0.014 | 0.230 |
| Uphill 0.03 rad | US06 | 305.26 | 305.21 | -0.02 | 0.039 | 0.237 |
| Flat | US06 | 190.75 | 191.43 | +0.36 | 0.015 | 0.229 |
| Downhill 0.03 rad | US06 | 79.30 | 83.83 | +5.71 | 0.010 | 0.193 |
| SOC 0.85 | US06 | 190.93 | 191.37 | +0.23 | 0.026 | 0.233 |
| SOC 0.55 | US06 | 191.00 | 191.63 | +0.33 | 0.027 | 0.195 |
| SOC 0.25 | US06 | 190.80 | 191.20 | +0.21 | 0.021 | 0.168 |
| Noise 1x | US06 | 190.75 | 191.81 | +0.55 | 0.021 | 0.230 |
| Noise 3x | US06 | 191.33 | 192.90 | +0.82 | 0.014 | 0.218 |
| Noise 10x | US06 | 201.55 | 210.53 | +4.45 | 0.055 | 0.192 |
| Driver 1.0 | US06 | 190.99 | 191.98 | +0.52 | 0.028 | 0.228 |
| Driver 1.25 | US06 | 197.16 | 197.38 | +0.11 | 0.045 | 0.331 |
| Driver 1.5 | US06 | 204.46 | 204.75 | +0.14 | 0.098 | 0.504 |

![fig:ems-campaign](paper/figures/fig-ems-campaign.png){width=page}
Caption: Corrected campaign, 16 valid settings: (a) energy difference of the learned policy relative to the rules, positive meaning more energy; (b) tracking RMSE of both controllers on a log axis. MEASURED, one run per cell.

The 16 settings are different conditions, so no interval is attached to their average.

## An Apparent Gain That Was Withdrawn

An earlier campaign, on the vehicle model before correction, appeared to show the opposite. The learned policy used less energy in 14 of the same 16 settings, by 8.28% on average and up to 21.6% at driver aggression 1.5. The gain grew with demand and vanished on UDDS and HWFET. It was an artefact: the model capped the battery power it billed at the policy's ceiling but computed acceleration from the uncapped torque, so a low ceiling reduced the energy charged and left motion untouched (Section @sec:plant). The policy had learned to set a low ceiling and still draw power above it, where motion was delivered and not billed. On US06 a constant 5 kW ceiling then billed 8.05 Wh/km for the full 12.89 km (SIMULATED). After the fix and retraining, the gain disappears, while the rule-based arm differed by +0.07% with a 95% interval of -0.03 to +0.17, which contains zero and lies within the spread between identical campaigns. The earlier energy result was withdrawn when the model fault was found, which is why Section @sec:plant audits the vehicle model.

## Behaviour Under Link Outage

When the host link drops, the firmware reacts in two ways. If the 100 ms energy-manager setpoint is more than 300 ms old, the rule-based action runs inside the speed loop. If no vehicle state has arrived for five control periods (50 ms), the torque command is ramped to zero at 10 N m per step and the integrator is frozen. The fallback ablation compiles these two behaviours out; the firmware then holds the last command.

The sweep used outage lengths of 0.2, 0.5, 1, 2, 3, 4, 5 and 10 s, eight paired onsets on US06 per length, with the retrained policy in the loop and the corrected model (MEASURED). Fig. @fig:ems-outage shows the worst peak speed error. Removing the handling gives the smaller worst error from 0.2 s to 4 s (0.18 against 0.23 m/s at 0.2 s, 3.73 against 6.67 m/s at 4 s). At 5 s the order reverses, 7.40 m/s with the handling against 7.97 without, so the crossover lies between 4 and 5 s; no point inside that interval was measured. At 10 s the worst error is 13.3 m/s with the handling and 18.2 m/s without. The median is less regular: the handling has the lower median at 4 s (1.21 against 1.55 m/s) and at 10 s (3.72 against 5.33 m/s), and the higher one at 5 s (1.64 against 1.44 m/s).

![fig:ems-outage](paper/figures/fig-ems-outage.png){width=col}
Caption: Worst peak speed error against outage length, with the fallback handling on and off, on the corrected model. MEASURED, eight onsets per length; lines join measured points only.

The handling is there for safety: it gives up some tracking in short outages so that long ones fail small. Holding a stale command works for a second or two and stops working once the reference has moved on.
