# SPEED PLANNING {#sec:planning}

Everything in this section is SIMULATED on the host computer; nothing ran on the target. The energy managers of Section @sec:ems could not change the speed trace, and that fixed trace is what left them almost nothing to win. Here the vehicle chooses the trace, so the headroom can be measured where it appears. Eco-driving is a long-standing optimal-control problem [@sciarretta2015].

A route is built from a standard drive cycle with the driver removed. It keeps the cycle's distance, its stops and the wait at each, a speed limit at every point, the hardest acceleration and braking the cycle used, and its duration as the arrival time within 1%. The US06 and HWFET routes serve as test and validation sets.

Five arms were compared. The cycle as driven is the reference. A dynamic-programming (DP) planner [@bellman1957] searches the whole route in 10 m steps, with a price on time set by bisection so that the arrival time is met. The same planner was run with a 300 m horizon, replanning every 40 m, and again with a small network supplying a terminal cost, an estimate of what the rest of the route costs. The fifth arm is a student policy, a network trained on the planner's solutions that names the next speed directly. Every profile was driven through the full vehicle model with the speed loop and the rule-based energy manager, and energy is stated on the comparable scale (Table @tab:planning-savings).

Table: tab:planning-savings | Energy saved against the cycle as driven, by planning arm; one run per route, SIMULATED, no other traffic. | width=col
| Arm | US06 route (%) | HWFET route (%) |
|---|---|---|
| Cycle as driven | 0.0 | 0.0 |
| DP, whole route | 10.4 | 1.2 |
| DP, 300 m horizon | 9.5 | 0.8 |
| 300 m, learned terminal cost | 10.4 | 1.1 |
| Student policy | 0.03 | 0.3 |

On the US06 route the whole-route planner saved 10.4% at the same stops and arrival time. The HWFET route offered 1.2%, since that drive has little to smooth. The terminal cost closed the gap left by the short horizon, and the student policy saved 0.03% on US06.

An empty road is the upper bound. To represent traffic, the planner was held within a corridor around the recorded drive, ahead or behind, at every second, with distance and arrival time unchanged. Fig. @fig:planning-corridor shows that the US06 saving was 5.1% within 25 m and 9.7% within 100 m, while HWFET stayed between -0.1% and 1.7%. The corridor planner differs in construction from the empty-road planner, so its 200 m figure of 12.6% is not comparable with the 10.4% above.

![fig:planning-corridor](paper/figures/fig-planning-corridor.png){width=col}
Caption: Energy saving against corridor half-width, with the no-traffic saving as a dash-dotted reference line for each route. SIMULATED; one run per width.

Planning took 0.19 s in Python on the laptop for all 323 replans of the US06 route with the terminal cost; nothing was ported, so no time or memory on the target is claimed. The traffic is one recorded drive, with no other vehicle, hills or signals, and each arm was run once.

# DISCUSSION AND LIMITATIONS {#sec:discussion}

## Why the Rules Held

The comparison of Section @sec:ems left little room for any controller. With the speed fixed by the tracking loop, three actuation numbers and cabin heat charged back at the energy it saves, an offline dynamic-programming optimum on the same plant sat within 0.01% to 0.16% of the rules on four cycles. A learned policy had that much to gain and a tracking penalty to pay. Against this bound the corrected campaign behaves as expected: the learned policy used more energy in 11 of 12 distinct conditions, and the one exception lies inside the repeat range of the rule arm.

The null result is therefore about this task. It shows that this SAC policy, tuned once, found nothing on this plant that the rules had missed. It does not show that a policy with authority over speed could not win; Section @sec:planning shows 5% to 10% on offer once speed is free, for a classical solver.

## The Audit as a Procedure

The 8.28% gain was not caught by a gate. Plant gate G2 replays logged trips and never exercised the power-ceiling path, so it passed a model in which a lowered ceiling cut the bill and left the motion alone. The audit began because the campaign tables looked wrong: the learned policy finished below the offline optimum at equal tracking, and its gain grew with demand. That trigger was one-sided. A model error that made learned policies look worse could have passed unexamined, so the checks below should run whatever the direction of the result.

Three checks follow from the case. First, billing and motion must agree: a sweep of constant limits with no controller in the loop should show that a lower ceiling reduces delivered motion as well as the bill (Fig. @fig:plant-correction). Second, a learner must not beat the offline optimum computed on the same plant; a result that does is evidence about the plant before it is evidence about the learner. Third, every actuator limit must act on motion and not only on the energy account. None needs the learned policy or the microcontroller. All three run on the host.

Measurement caught other things the host could not. A compute estimate of 22.28 ms for the forecaster became 36.46 ms on the target, 64% higher. The rule monitor's edge in a first run, 0.61 against 0.67 m/s, reversed over three noise draws to 1.32 against 0.83 m/s (MEASURED).

## What Transfers to Vehicle Hardware

The ESP32-S3 is a general-purpose microcontroller, not an automotive-qualified part. Some results port by construction: the operation count of a network and its weight memory (19.3 KB for the learned policy, 28,894 B for the timed forecaster graph) do not depend on the vendor. Latency scales with the integer throughput of the target, 29.82 million multiply-accumulates per second here, though an estimate from that scaling was 64% low once.

Timing does not port. The 25 µs period deviation was measured with the target as clock master against a non-real-time host over a serial link, with radio stacks present in the Arduino image though never started. The 8.8 dropped frames per run belong to the host. Flash and cache behaviour, interrupt load from real peripherals and supply current were not examined, nor were the fault-tolerance features of safety-rated parts.

## Scope of the Safety Claims

The sensor-fault detector, the fallback speeds and the link-outage handling were evaluated as monitoring functions of a research prototype. No claim of conformance with ISO 26262 or the safety of the intended function is made. The fault model is one speed-sensor channel, injected in software, with a simulated accelerometer. The detector has no self-monitoring.

The outage handling shows why the wording matters. On the corrected model, without the handling the worst peak speed error is smaller for outages from 0.2 s to 4 s (3.73 against 6.67 m/s at 4 s). It reverses at 5 s, 7.40 against 7.97 m/s, and at 10 s the handling gives 13.3 against 18.2 m/s (MEASURED). No point between 4 and 5 s was measured, so the handling is described as a behaviour with a stated cost, not as a safety measure.

## Limitations

The arrangement is processor-in-the-loop, so nothing here is a hardware-in-the-loop result, and one board and one vehicle model were used. The model's rolling coefficient is 2.2 times a published coastdown value for a different car; it fails gate G2 on 1 of 7 validation trips, missing the state-of-charge bound by 0.45 percentage points (2.45 against 2.00); it was validated on winter trips only; and on the Vehicle Energy Dataset transfer check its median trip energy error is 13.4% to 16.9%. These threaten absolute Wh/km more than the paired ranking on one plant. Yet one plant fault has already changed an answer here. No sensitivity study of the verdict to the rolling coefficient, rotational factor, regeneration ceiling or drivetrain efficiency was run, and the comfort cost of heater shedding is not modelled.

The learned policy is one algorithm, SAC, with one reward design and no sweep. Each campaign cell ran once, except the five repeats of the nominal US06 condition. US06 was held out of training, but it drove the earlier campaign and its fix, so it was not unseen by the authors; the learned tracking deficit appears there (0.17 to 0.50 m/s) and not on UDDS or HWFET (0.004 and 0.016 m/s). Gate G3 fails its zero-dropped-frame criterion; dropped frames and the energy difference are unrelated (r = -0.03). The Kalman estimator was compared only with the raw-reading loop. The bias-aware detector was tested on injected faults and not replayed on the logged trips, and the fused fallback estimator, the learned reviewers and the planner are simulated only.

A sensitivity sweep of the plant parameters would show whether the ranking holds. A learned speed planner set against the classical solver would test the one place where headroom exists. A physical accelerometer would replace the simulated drift behind the fault results.

# CONCLUSION {#sec:conclusion}

A processor-in-the-loop campaign on an ESP32-S3 at 100 Hz appeared to show a learned Soft Actor-Critic energy manager using 8.28% less energy than a rule-based one, in 14 of 16 settings. The saving was an artefact: the vehicle model billed battery power at the policy's ceiling but computed motion from uncapped torque, so a low ceiling cut the bill and left the vehicle driving. A controller-free sweep exposed it, and the gain is withdrawn.

On the corrected model the learned policy used less energy in 1 of 16 settings and 0.94% more on average. That outcome is explained by the task: with speed fixed by the tracking loop, the rules sit within 0.01% to 0.16% of the offline optimum. The finding holds for one vehicle model, one board, one learned algorithm and one reward design.

The method that exposed the fault is the lasting result. A billing-against-motion sweep, a rule that a learner must not beat the offline optimum on the same plant, and a requirement that every limit act on motion would each have caught it before the campaign. The measured gain was in the speed loop, where a two-state Kalman estimator cut the energy lost at ten times sensor noise from 9.44 to 0.24 Wh/km. The detector's 120 of 120 rests on faults injected in software. Planning with free speed offers 5% to 10% in simulation, the place to test a learned method next.
