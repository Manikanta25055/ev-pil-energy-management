# SPEED PLANNING {#sec:planning}

This section is a supporting result, and everything in it is host-simulated; nothing ran on the target. The energy managers of Section @sec:ems could not change the speed trace, and that fixed trace is what left them almost nothing to win. Here the vehicle chooses the trace, so the headroom can be measured where it appears. Eco-driving is a long-standing optimal-control problem [@sciarretta2015].

A route is built from a standard drive cycle with the driver removed. It keeps the cycle's distance, its stops and the wait at each, a speed limit at every point, the hardest acceleration and braking the cycle used, and its duration as the arrival time within 1%. The US06 and HWFET routes serve as test and validation sets.

Five arms were compared. The cycle as driven is the reference. A dynamic-programming (DP) planner [@bellman1957] searches the whole route in 10 m steps, with a price on time set by bisection so that the planned arrival time is met. It solves the planner's own energy model, so it is a planning reference, not a certified optimum of the vehicle. The same planner was run with a 300 m horizon, replanning every 40 m, and again with a small network supplying a terminal cost, an estimate of what the rest of the route costs. The fifth arm is a student policy, a network trained on the planner's solutions that names the next speed directly. The learned arms see more than the 300 m arm: speed limits up to 700 m ahead, a stop cue up to 1300 m, and a feasibility mask computed over the whole remaining route, so the 300 m arm is not an equal-preview control. Every profile was driven through the full vehicle model with the speed loop and the rule-based energy manager, and energy is stated on the comparable scale (Table @tab:planning-savings).

Table: tab:planning-savings | Energy saved against the cycle as driven, by planning arm; one run per route, host-simulated, no other traffic. | width=col
| Arm | US06 route (%) | HWFET route (%) |
|---|---|---|
| Cycle as driven | 0.0 | 0.0 |
| DP, whole route | 10.4 | 1.2 |
| DP, 300 m horizon | 9.5 | 0.8 |
| 300 m, learned terminal cost | 10.4 | 1.1 |
| Student policy | 0.03 | 0.3 |

On the US06 route the whole-route planner saved 10.4% at the same stops and within the 1% arrival tolerance. The HWFET route offered 1.2%, since that drive has little to smooth. The terminal-cost arm matched the whole-route saving, but it planned to arrive 3.9 s later than the whole-route planner and 6.3 s later than the 300 m arm, with more preview than the latter, so no learned benefit is isolated. The student policy saved 0.03% on US06. Arrival here is the planned time of the node profile, not the time the driven trace crossed the route's end, and the constraint counts describe the planned profile; closed-loop limit and stop compliance were not evaluated. Replayed from the frozen code, all eight runs reproduced, and every driven trace crossed the route's end about 6.2 s (US06) or 2.2 s (HWFET) before its planned time, so the gaps between arms hold (host-simulated).

An empty road is an optimistic scenario. As a surrogate for traffic constraints, the planner was held within a corridor around the recorded drive, ahead or behind, at every second, with distance and arrival time unchanged. Fig. @fig:planning-corridor shows that the US06 saving was 5.1% within 25 m and 9.7% within 100 m, while HWFET stayed between -0.1% and 1.7%. The corridor planner differs in construction from the empty-road planner, so its 200 m figure of 12.6% is not comparable with the 10.4% above.

![fig:planning-corridor](paper/figures/fig-planning-corridor.png){width=col}
Caption: Energy saving against corridor half-width, with the no-traffic saving as a dash-dotted reference line for each route. Host-simulated; one run per width.

Planning took 0.19 s in Python on the laptop for all 323 replans of the US06 route with the terminal cost; nothing was ported, so no time or memory on the target is claimed. The traffic is one recorded drive, with no other vehicle, hills or signals, and each arm was run once.

# DISCUSSION AND LIMITATIONS {#sec:discussion}

## Why the Rules Held

The comparison of Section @sec:ems left little visible room for any controller. With the speed fixed by the tracking loop, three actuation numbers and cabin heat charged back at the energy it saves, a feasible policy derived by approximate dynamic programming and run through the full model differed from the rules by 0.01% to 0.16% on four cycles; refining its grid did not move it, and the fix did not either, because its discharge ceiling never binds. The gap is a difference from one evaluated reference policy and does not certify the largest saving physically attainable. Against it, with a tracking penalty to pay, the evaluated policy used more energy in 12 of 12 distinct conditions over three noise draws (host-simulated reference, PIL-evaluated campaign).

The null result is about this task. This SAC policy, with one reward design, one hyperparameter set and one deployed seed, found nothing on this plant that the rules had missed. It does not show that reinforcement learning in general cannot outperform rules, nor that a policy with authority over speed could not win; Section @sec:planning finds 5% to 10% on offer once speed is free, for a classical solver on an empty or constrained simulated road.

## The Audit as a Procedure

The 8.28% gain was not caught by a gate. Plant gate G2 replays logged trips and never exercised the power-ceiling path, and repetition on the target reproduced the fault faithfully. The lesson is that repeated controller runs and timing checks, however careful, test the controller and the loop; they do not test whether the model's energy account agrees with its physics. Table @tab:plant-checks turns the case into an audit with four groups. Limit-and-conservation tests, the controller-free sweep of the discharge ceiling and the invariance checks were run, and the first two fail on the faulty model. The sweeps of the regeneration blend and heater derate were not run and remain recommendations. The reference-policy trigger was applied once, after the fact and only because the result favoured the learner; beating a feasible reference is a reason to investigate, not proof of a defect, and the trigger should fire in both directions.

Measurement caught what the host could not: the forecaster's compute estimate of 22.28 ms became 36.46 ms on the target, 64% higher (target-measured).

## What Transfers to Vehicle Hardware

The ESP32-S3 is a general-purpose microcontroller, not an automotive-qualified part. The operation count of a network and its weight memory (19.3 KB for the learned policy, 28,894 B for the timed forecaster graph) do not depend on the vendor; timing does not port. The 25 µs period deviation was measured with the target as clock master against a non-real-time host, with radio stacks present in the Arduino image though never started. Flash and cache behaviour, interrupt load from real peripherals, supply current and the fault-tolerance features of safety-rated parts were not examined.

## Scope of the Safety Claims

The sensor-fault detector, the fallback speeds and the link-outage handling were evaluated as monitoring functions of a research prototype. No claim of conformance with ISO 26262 or the safety of the intended function is made. The fault model is one speed-sensor channel, injected in software, with a simulated accelerometer.

On 70 logged trips assumed healthy, the bias-aware detector met its count limit numerically at the logs' 10 Hz, 0.99 alarm onsets per hour with standstill alarms set apart, while its flag was up for 59% of recorded time; with the channels interpolated to 100 Hz it counted 16.2 onsets per hour (host-simulated replay). Its 120 of 120 applies only to faults injected into a simulated acceleration channel, and no field-ready detection or general sensor robustness is claimed.

The outage handling shows why the wording matters. Without it the worst peak speed error is smaller for outages from 0.2 s to 4 s (3.73 against 6.67 m/s at 4 s). It reverses at 5 s, 7.40 against 7.97 m/s, and at 10 s the handling gives 13.3 against 18.2 m/s (PIL-evaluated). No point between 4 and 5 s was measured, so the handling is a behaviour with a stated cost, not a safety measure.

## Limitations

The arrangement is processor-in-the-loop, not hardware-in-the-loop, with one board and one vehicle model. The model's rolling coefficient is 2.2 times a published coastdown value for a different car; it fails gate G2 on 1 of 7 validation trips (state-of-charge error 2.45 against 2.00 percentage points); it was validated on winter trips only; and its median trip energy error on the Vehicle Energy Dataset is 13.4% to 16.9%. These threaten absolute Wh/km more than the paired ranking: every Wh/km figure in the paper is computed by this model, under winter-identified parameters, for campaigns run at 12 °C, just above the validated envelope, and could differ from a car's by the 13% to 17% seen on transfer. The one-at-a-time sensitivity sweep of Section @sec:plant found no sign change, but a combined error could still move the result. Heater shedding's comfort cost is not modelled.

The learned policy is one algorithm, SAC, with one reward design, no hyperparameter sweep and one deployed seed chosen on validation energy. The delay exclusion and the 16-frame re-run threshold were set after results were seen (Table @tab:platform-revisions). The corrected campaign ran three noise seeds per condition; the delay settings and the first campaign ran once. US06 was held out of training, but it drove the earlier campaign and its fix; the learned tracking deficit appears there (0.17 to 0.50 m/s) and not on UDDS or HWFET (0.004 and 0.016 m/s). Gate G3 fails its zero-dropped-frame criterion, although dropped frames and the energy difference are unrelated (r = -0.03), and the Kalman estimator was compared with the raw-reading loop and one low-pass filter in two noise blocks, while the fused estimator, the learned reviewers and the planner are simulated only.

A learned speed planner set against the classical solver would test the one place where headroom exists, and a physical accelerometer would replace the simulated drift, so that a detector retuned on logged channels could be tested against it. Sensitivity runs on the board, with noise and more policy seeds, would test the ranking under campaign conditions.

# CONCLUSION {#sec:conclusion}

A Soft Actor-Critic controller initially appeared to reduce model-computed energy use by 8.28% against a rule-based manager in a processor-in-the-loop evaluation on an ESP32-S3. The advantage was traced to a plant implementation that capped billed battery power without limiting delivered torque. A controller-free sweep exposed it, and the gain is withdrawn.

After the model was corrected and the policy retrained, the evaluated SAC design used more energy than the rules in all 12 distinct conditions, each averaged over three paired noise draws (median 0.50%, Wilcoxon p = 0.0005). With speed fixed by the tracking loop, the rules differed by 0.01% to 0.16% from a feasible policy derived by approximate dynamic programming, a gap that does not certify the largest attainable saving. The result holds for one vehicle model, one board and one learned configuration; absolute Wh/km figures belong to that model.

The transferable result is the audit. Repeated controller runs and timing checks on the target must be complemented by actuator-level tests of physical consistency: limits that act on motion, controller-free sweeps of every command, invariance under limits that do not bind, and a reference-policy trigger applied in both directions. Only part of that audit was exercised here. In the speed loop, filtering the reading recovered the energy lost at ten times the sensor noise, with a Kalman estimator doing so at lower clean tracking error than a low-pass filter. The fault detector's 120 of 120 rests on injected faults and does not hold on logged channels. Free speed offers 5% to 10% in simulation; that is where a learned method would next be worth testing.
