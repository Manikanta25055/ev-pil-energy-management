# SPEED PLANNING {#sec:planning}

Everything in this section is SIMULATED on the host computer; nothing ran on the target. The earlier sections gave the controller a speed trace to follow. Here the vehicle chooses the trace. A route is built from a standard drive cycle with the driver removed: it keeps the cycle's distance, its stops and the wait at each, a speed limit at every point, the hardest acceleration and braking the cycle used, and its duration as the arrival time within 1%. The US06 (aggressive) and HWFET (Highway Fuel Economy Test) routes serve as test and validation sets.

Five arms were compared. The cycle as driven is the reference. A classical dynamic-programming (DP) planner [@bellman1957] searches the whole route in 10 m steps, with a price on time set by bisection so that the arrival time is met. The same planner was also run with a 300 m horizon, replanning every 40 m, and once more with a small network supplying a terminal cost, an estimate of what the rest of the route costs. The fifth arm is a student policy, a network trained on the planner's solutions that names the next speed directly. Every profile was driven through the full vehicle model with the speed loop and the rule-based energy manager, and energy is stated on the comparable scale (Table @tab:planning-savings).

Table: tab:planning-savings | Energy saved against the cycle as driven, by planning arm; one run per route, SIMULATED, no other traffic. | width=col
| Arm | US06 route (%) | HWFET route (%) |
|---|---|---|
| Cycle as driven | 0.0 | 0.0 |
| DP, whole route | 10.4 | 1.2 |
| DP, 300 m horizon | 9.5 | 0.8 |
| 300 m, learned terminal cost | 10.4 | 1.1 |
| Student policy | 0.0 | 0.3 |

On the US06 route the whole-route planner saved 10.4% at the same stops and arrival time; the HWFET route offered 1.2%, since the drive has little to smooth. The terminal cost closed the gap left by the short horizon; the student policy saved nothing on US06.

An empty road is the upper bound on what planning gives. To represent traffic, the planner was held within a corridor around the recorded drive, ahead or behind, at every second, with distance and arrival time unchanged. Fig. @fig:planning-corridor shows that the saving on US06 was 5.1% within 25 m and 9.7% within 100 m, while HWFET stayed between -0.1% and 1.7%. The corridor planner differs in construction from the empty-road planner, so its 200 m figure of 12.6% is not comparable with the 10.4% above.

![fig:planning-corridor](paper/figures/fig-planning-corridor.png){width=col}
Caption: Energy saving against corridor half-width, with the no-traffic saving as a dash-dotted reference line for each route. SIMULATED; one run per width.

No other vehicle was simulated, and the corridor around one recorded drive stands in for traffic. Hills and signals are absent, each arm was run once, and the planner has not been ported to the target.

# DISCUSSION AND LIMITATIONS {#sec:discussion}

## Why the Rules Held

The result rests on how little room the problem leaves. The offline optimum, computed by dynamic programming over each whole cycle, was within 0.01% to 0.16% of the rule-based energy manager on WLTC3B, UDDS, HWFET and US06. Recovering braking energy is worth 5% to 23% between the highway and city cycles, and the rules already take all of it. With the speed loop fixed by a tracking constraint, the discharge limit can only remove power the loop needs, and heating priced at its cost cancels out. A learned policy therefore has almost nothing to win and a tracking penalty to pay, which matches the measured outcome (Section @sec:ems).

The forecast ablation agrees: after retraining on the corrected model, removing the forecast changed energy by +0.262 Wh/km with a 95% interval of -0.698 to +0.982, which contains zero. Better offline scores did not carry into the loop either. The learned reviewers classified faults better than the rule monitor in shadow scoring, then controlled the vehicle worse in closed loop (SIMULATED, Section @sec:estimation). These statements hold for this vehicle model, these four cycles and this class of processor, and no further.

## What the Method Caught

Four findings came from the gates and the repeat rules rather than from the experiments they guarded. The first is the vehicle-model power ceiling. It cut the energy billed without cutting delivered torque, which produced an apparent 8.28% advantage for the learned policy in 14 of 16 settings. After the model was corrected the policy won 1 of 16 and used 0.94% more energy on average, and the earlier gain is withdrawn here.

The second is the compute estimate for the forecaster, 22.28 ms from a multiply count, against 36.46 ms measured on the target. Measured latency was 64% above the estimate, which is why estimates are used here only to rank models. The third is a false alarm of the acceleration-residual detector, raised once in 1.26 h of clean driving. It returned at the same control step in two repeats and in a host replay, because each setting used one fixed noise seed: a same-seed repeat is not a repeat, and the alarm was one event seen four times. The fourth is the rule monitor. Its largest speed error during a fault was 0.61 m/s in the first run, slightly under the detector alone, but over three noise draws it was 1.32 m/s against 0.83 m/s, so the advantage did not hold on the target.

## Limitations

The arrangement is processor-in-the-loop: the processor is real, while the motor, inverter and battery are simulated, so nothing here is a hardware-in-the-loop result. One microcontroller board was used. One vehicle model was identified, and it fails gate G2 on one of seven validation trips, missing the state-of-charge bound by 0.45 percentage points (2.45 against 2.00). Gate G3 fails its zero-dropped-frame criterion, because the host answered late 9 times in the first run of 59,650 loops and 8.8 times per run over five repeats; no control step finished late.

Sensor faults were injected in software and no physical accelerometer was used. The logged acceleration disagrees with the logged speed by a slow component of about 0.11 m/s², which a simulation with random noise alone does not show. The fused fallback estimator, the learned reviewers comparison and the speed planner are simulated only, and the fused estimator fails for a vehicle 10% heavier than its model on US06 (largest error 2.59 m/s). The main comparison has one run per campaign cell. The learned policy is one algorithm, SAC (Soft Actor-Critic), with one reward design; the result does not show that no learned policy could win.

## Future Work

A physical accelerometer on a test vehicle would replace the simulated drift, and would show whether the 0.11 m/s² disagreement is a property of the logged data or of the sensor. The fused fallback estimator needs its heavier-vehicle case fixed before it is ported to the target and measured there. The planning task needs a traffic model in place of one recorded drive. The planner itself needs a measured planning time on the processor, because the replanning distance of 40 m sets the time allowed.

# CONCLUSION {#sec:conclusion}

The earlier study [@tangi2025] left three questions open: whether data-driven models agree with logged trips, whether they can close a control loop, and whether they run on an embedded controller under a real-time deadline. On logged trips, a longitudinal model identified from BMW i3 trips reproduces six of seven validation trips within the bounds of gate G2 and fails on the seventh, with larger errors on the Vehicle Energy Dataset transfer check (median energy error 13% to 17%). In closed loop, a learned policy drove the simulated vehicle. On an ESP32-S3 at 100 Hz, 36 runs covered 2,282,832 control steps with no late step (MEASURED).

After the vehicle-model fault was fixed, the learned policy used less energy than the rule-based energy manager in 1 of 16 settings on the target, 0.94% more on average, and tracked speed worse on US06. The forecast changed nothing measurable. Two positive results were measured on the target: a two-state Kalman speed estimator cut the energy lost to 10x sensor noise from 9.44 to 0.24 Wh/km on US06, and a bias-aware detector caught 120 of 120 injected faults with no false alarm in one clean hour. On this hardware and this problem, classical estimation and hand-written rules survived measurement. The single most useful next step is a physical accelerometer, because the fault results and the fallback estimator all rest on simulated acceleration drift.
