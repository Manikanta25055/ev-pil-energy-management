# VEHICLE MODEL AND THE POWER-LIMIT ARTEFACT {#sec:plant}

Every controller in this study acts on a simulated vehicle, so a fault in that vehicle enters every comparison. One such fault produced an 8.28% mean energy saving for the learned policy that did not exist. This section describes the model, what its validation did not test, and the fault, its discovery and the checks it implies.

## Data

The model was identified and validated on a public archive of 70 trips of a BMW i3 [@i3data], logged every 0.1 s. Eligibility tests were fixed before any fit: state of charge (SOC) present, no charging, and two heater-power channels present and in agreement. Thirty-three trips passed, all in winter, so the validated envelope has a mean ambient temperature from -3.3 to 10.2 °C. The 33 were split by trip into 19 for identification, 7 for validation and 7 sealed for a final test that has not been opened.

The Vehicle Energy Dataset (VED) [@ved] served for a transfer check. The campaigns use three dynamometer schedules [@epacycles]: the Urban Dynamometer Driving Schedule (UDDS, 1369 s, 11.99 km), the Highway Fuel Economy Test (HWFET, 765 s, 16.51 km) and the aggressive US06 schedule (600 s, 12.89 km).

## Longitudinal Model

The force balance (@eq:plant-force) sets the acceleration, with mass $m$, rotational mass factor $e$, speed $v$, wheel force $F_{t}$, rolling and drag coefficients $c_{rr}$ and $c_{d}$, frontal area $A$, air density $\rho$ and grade $\theta$.

$$ m(1+e)\dot{v} = F_{t} - m g c_{rr}\cos\theta - \tfrac{1}{2}\rho c_{d} A v^{2} - m g \sin\theta $$ {#eq:plant-force}

Torque $T$ becomes wheel force through the gear ratio, wheel radius and drivetrain efficiency. Electrical power uses motor speed $\omega$ and an efficiency $\eta$ from a map identified on training trips only.

$$ P_{e} = T\omega/\eta(T,\omega) \;\; (T\omega > 0), \qquad P_{e} = T\omega\,\eta(T,\omega) \;\; (T\omega < 0) $$ {#eq:plant-motor}

The battery is a first-order equivalent circuit with terminal voltage $V_{t}$, open-circuit voltage $V_{oc}$ at SOC $s$, current $i$, resistance $R_{0}$ and an $R_{1}C_{1}$ branch; its open-circuit curve, branch values and current limits are assumptions.

$$ V_{t} = V_{oc}(s) - i R_{0} - v_{1}, \qquad \dot{s} = -\frac{i}{3600\,C_{b}}, \qquad \dot{v}_{1} = \frac{i}{C_{1}} - \frac{v_{1}}{R_{1}C_{1}} $$ {#eq:plant-battery}

The auxiliary load is 543 W at rest (measured) plus 127.3 W per degree below a 21 °C setpoint (fitted); the cooling slope is unidentified, because every eligible trip is colder than the setpoint. Regenerative braking returns a fraction of the braking power, limited by an assumed 50 kW ceiling and the pack's charge current. Table @tab:plant-params lists the main parameters.

Table: tab:plant-params | Main parameters of the i3 model, with the origin of each value. | width=col
| Parameter | Value | Origin |
|---|---|---|
| Mass $m$ | 1270 kg | published kerb mass plus driver |
| Frontal area $A$ | 2.38 m² | from published drag area and an assumed drag coefficient |
| Wheel radius, gear ratio | 0.3498 m, 9.665 | from tyre size; published |
| Motor limits | 250 Nm, 125 kW | published |
| Drivetrain efficiency $\eta_{d}$ | 0.95 | assumed |
| Rolling coefficient $c_{rr}$ | 0.01947 | identified, training trips |
| Drag coefficient $c_{d}$ | 0.2202 | identified, training trips |
| Rotational factor $e$ | 0.1706 | identified, training trips |
| Resistance $R_{0}$ | 0.010 ohm | identified, at lower bound |
| Capacity $C_{b}$ | 61.7 Ah | Coulomb counting of logged data |

## Validation Against Logged Trips

Gate G2 was written before the fit. It replays a held-out trip's logged speed and passes only if every validation trip meets the bounds. The original single criterion pooled three models and failed all seven trips without saying which was at fault, so it was split into three parts with both original thresholds kept. Part A: torque inverted from the speed profile within 50% of the logged-torque standard deviation, the only new number. Part B: battery power, driven by logged torque, within 10% of mean absolute power. Part C: terminal SOC within 2 percentage points (pp).

The gate fails on Part C. Parts A and B pass on 7 of 7 trips (worst case 48.6% and 8.3%), and Part C on 6 of 7, with a median of 0.19 pp. Trip B08 misses by 2.45 pp against 2.00 pp (Fig. @fig:plant-validation); the bound was kept and the miss recorded.

![fig:plant-validation](paper/figures/fig-plant-validation.png){width=col}
Caption: Terminal SOC error on the seven validation trips against the 2.00 pp bound of gate G2. Trip B08 (hatched) exceeds it. Host-simulated replay of logged trips.

G2 checks the model along logged trajectories: logged torque goes in, and battery power and SOC come out. The controllers here send the model a battery power ceiling, and a replay of logged torque never asks the model to enforce one. The path that carried the fault below lay outside everything G2 exercised, so the gate could not have failed on it.

## Transfer to Another Vehicle

The model was rebuilt around a 2013 Nissan Leaf from the battery-electric subset of VED and run on 89 validation trips. Arm A carried every i3 parameter across, arm B replaced the chassis coefficients with the Leaf's coastdown values, and arm C refitted the chassis. Median trip energy error was 16.9%, 14.4% and 13.4% (host-simulated against logged trips).

## The Earlier Campaign and the Apparent Gain {#sec:artefact}

The first processor-in-the-loop (PIL) campaign ran both energy managers on the ESP32-S3 target [@esp32s3] against this model, over six factors at three levels each: 36 runs, 32 of them valid (Section @sec:ems). The Soft Actor-Critic (SAC) policy [@haarnoja2018] used less energy than the rule-based manager in 14 of 16 valid settings, by 8.28% on average and by up to 21.6% at driver aggression 1.5, on the comparable energy scale of Section @sec:platform (PIL-evaluated). Fig. @fig:plant-reversal shows each setting.

![fig:plant-reversal](paper/figures/fig-plant-reversal.png){width=col}
Caption: Learned minus rule-based energy per setting on the comparable scale, in the earlier campaign on the faulty model and in the corrected campaign. Negative means the learned policy used less. PIL-evaluated, one run per cell; five of the 16 settings repeat the nominal US06 condition.

The gain rose with demand on three axes: 7.57%, 14.54% and 21.61% across driver aggression 1.0, 1.25 and 1.5, and 4.79%, 7.53% and 10.14% across downhill, flat and uphill. On the two gentlest cycles it was absent, with the learned policy using 0.27% (UDDS) and 0.09% (HWFET) more. A repeat campaign the next day, on firmware that also logged the discharge ceiling, reproduced it at 14 of 16 settings and 8.29% (PIL-evaluated). The ceiling averaged 72.0 kW for the learned policy and 123.4 kW for the rules over the valid settings. A repeat shows that a result is reproducible on a model, not that the model bills fairly.

## The Mechanism

Each energy manager sends the model a ceiling $P_{lim}$ on battery discharge power. The model applied it to the bill and not to the motion.

$$ P_{b} = \min(P_{m} + P_{a},\, P_{lim}), \qquad a = f(T_{req}) $$ {#eq:plant-limit}

Here $P_{m}$ is the machine power, $P_{a}$ the auxiliary load and $T_{req}$ the torque requested before any cap. The battery was charged $P_{b}$ while acceleration came from $T_{req}$, so billed and delivered power parted wherever demand exceeded the ceiling. A controller that lowered the ceiling was charged less and still received the motion it asked for.

The cause was isolated with no controller in the loop. A constant ceiling was held over US06 on the model before the fix, read from the repository history (Fig. @fig:plant-correction, host-simulated). A 5 kW ceiling drove all 12.888 km at 8.05 Wh/km, with the same 0.0013 m/s tracking error as an open ceiling at 190.39 Wh/km. A constant 40 kW ceiling billed 174.85 Wh/km. The deployed learned policy, simulated on that model, scored 176.71 Wh/km against 176.53 measured on the target.

![fig:plant-correction](paper/figures/fig-plant-correction.png){width=col}
Caption: A constant battery power ceiling held over US06, before and after the fix, with no controller in the loop. Before, a lower ceiling cut the billed energy and left the distance unchanged; after, it also cuts the distance. Host-simulated.

## How It Was Found

The gates did not find it. G2 never exercised the ceiling path. The campaign tables carried three cues. The learned policy finished 7% below the dynamic-programming (DP) reference of 190.39 Wh/km at equal tracking, a feasible policy the rules matched within 0.04%; its advantage grew with demand; and it vanished on UDDS and HWFET, where demand stays under the 40 kW floor of the ceiling range. The fault was found 15 days after the first campaign.

The standing safeguards could not see it. G2 replays trips with a ceiling that never binds, the DP held the ceiling at the motor maximum by design, the plant's unit test asserted only that billed power met the ceiling, and the test that speed is unaffected by the energy action ran with a 300 kW ceiling. Two explanations recorded on the way, peak-current shaving and power limiting by the learned policy alone, were both wrong; the repeat campaign showed both controllers using the same 40 to 125 kW range but did not reveal the fault. The controller-free sweep did.

## The Fix and Its Consequences

The fix gives the motor the power the pack delivered less the auxiliary load, reduces torque to match, and computes acceleration from the reduced torque. Four unit tests and one cycle-level test were added. Two limits that never bind give bit-identical outputs, and a starving ceiling must cost distance and tracking, not only the bill.

On the corrected model a 5 kW ceiling gives 156.16 Wh/km over 4.453 km with 16.15 m/s tracking error, and a 40 kW ceiling gives 189.80 Wh/km against 174.85 before (host-simulated). The rule-based manager and the DP reference did not change, since their ceiling never bound. The learned policy on US06 moved from 176.71 to 190.71 Wh/km, against 190.47 for the rules, with tracking error 0.48 m/s against 0.0013 m/s. On the target, across 16 valid settings, the corrected rule arm differed from the repeat campaign by +0.07% on average (95% interval -0.03 to +0.17%), 0.46% at worst, against 0.57% at worst between two campaigns that differed only in the day (PIL-evaluated). The corrected comparison is in Section @sec:ems.

## The Audit the Case Implies {#sec:checks}

Fixing one billing rule is a repair. The reusable part is the audit, which asks whether every command a controller sends acts on the model's physics as well as on its energy account. Table @tab:plant-checks sets it out in four groups, with the actuator path each check exercised, what it showed and what it leaves untested. All of these checks were written after the fault, and none was a gate fixed in advance.

Table: tab:plant-checks | Physical-consistency audit: what each check is for, the path it exercised, its result and its remaining coverage. Faulty means the pre-fix model loaded from the version history. Host-simulated. | width=page
| Group | Check | Purpose | Path exercised | Observed | Coverage |
|---|---|---|---|---|---|
| (i) Limits and conservation | Traction never exceeds what the battery supplied; a binding limit removes torque | Billed and delivered power must agree | Discharge-power ceiling; pack current limit | Faulty fails; corrected passes four unit tests and one cycle test | Tested |
| (i) Limits and conservation | Regeneration boundary against an oracle that does not call the plant helpers | Braking split, charge-current and SOC limits, terminal-port energy | Regeneration and charging | Seven cases pass on the corrected model | Tested, corrected model only |
| (ii) Controller-free sweep | Constant ceiling held over US06; energy and distance must fall together | A saving must carry a physical cost | Discharge-power ceiling, 5 to 250 kW | Faulty: 8.05 Wh/km at 5 kW, distance unchanged. Corrected: 156.16 Wh/km over 4.453 km | Tested |
| (ii) Controller-free sweep | Same sweep for the regeneration blend and the heater derate | As above | Blend; auxiliary derate | Only checked that the speed trace is unchanged | Recommended, not run |
| (iii) Non-binding invariance | A limit that does not bind leaves every output unchanged | A fix must not move unaffected arms | 250 kW against open ceiling; rule arm; DP reference | Bit-identical; rule arm +0.07% on the target; all 28 stored results reproduced | Tested |
| (iv) Reference anomaly | A learned result well past a feasible reference on the same model opens an audit | Flag results the action space should not allow | All three actions together | Triggered: 176.71 against 190.39 Wh/km | Applied once, after the fact, in one direction |

The anomaly trigger needs care. A learned result past a reference policy is a reason to investigate, not proof of a model defect: the learner may have found a larger action space, a weakness of the approximate reference, or a hole in the model. Here it was applied after the fact and only because the result favoured the learned policy; a fault that made the policy look worse would not have drawn the same scrutiny, and no symmetric audit was run. The pack current limit had the same fault as the power ceiling and was fixed in the same commit.

The plant tests that predate the fault already covered the five paths through which energy is billed: discharge-power and discharge-current limits, regenerative charge and SOC limits, auxiliary accounting, and energy integration. What they lacked was a check that a limit acts on motion. The faulty plant, run again from the version history, still gives 8.05 Wh/km at 5 kW, while the corrected plant reproduces its binding controls and leaves the 250 kW control and the rule arm unchanged (host-simulated).

## Limits of Plant Fidelity

The three identified chassis coefficients do not measure what they are named after. The fitted rolling coefficient of 0.01947 is 2.2 times the 0.00878 of a published coastdown test of a 2013 Nissan Leaf [@inl2013leaf]. That is unlikely to be tyre rolling resistance alone; the value probably absorbs drivetrain and brake drag, efficiency-map error and unmodelled load, and the same holds for $c_{d}$ and the rotational factor of 0.1706. The 50 kW regeneration ceiling and the 0.95 drivetrain efficiency are assumptions, and $R_{0}$ sits at its lower bound. Table @tab:plant-validity collects what the validation supports and what it leaves open.

Table: tab:plant-validity | Validity of the vehicle model and the consequence for reported figures. Host-simulated against logged trips unless stated. | width=col
| Evidence | Result | Consequence |
|---|---|---|
| G2 parts A and B, 7 i3 trips | Pass on 7 of 7 (worst 48.6%, 8.3%) | Torque and battery-power paths fit the logs |
| G2 part C, terminal SOC | 6 of 7; trip B08 2.45 against 2.00 pp | SOC drift over a trip can exceed the bound |
| Ambient envelope | Trip means -3.3 to 10.2 °C, winter only; campaigns at 12 °C | Campaigns sit just above the validated range; cooling load unidentified |
| Transfer, Nissan Leaf, 89 trips | Median trip-energy error 13.4% to 16.9% | Absolute Wh/km uncertain at that scale |
| Rolling coefficient | 2.2 times a published coastdown value | Lumped losses; rule arm on US06 falls from 190.47 to 150.09 Wh/km with the published value |
| One-at-a-time sensitivity, 14 variants | Learned higher in all 14, by 0.12% to 0.81% | Paired ranking held; interactions untested |
| Sealed test trips | 7 trips, not opened | No final test of the model |

These limits threaten absolute figures first: Wh/km values in this paper belong to this model, not to a car. Setting the rolling coefficient to the published 0.00878 lowers the rule arm's energy from 190.47 to 150.09 Wh/km on US06 and from 153.90 to 112.34 Wh/km on HWFET (host-simulated).

A one-at-a-time sweep tested the ranking, varying the vehicle model while both controllers kept the nominal one: the published rolling coefficient, a rotational factor of 0, the regeneration ceiling at 0.8 and 1.2 times its value, and drivetrain efficiency 3 points either side, on US06 and HWFET (host-simulated, no sensor noise, one policy seed). The learned policy used more energy in all 14 cases, by 0.12% to 0.81%, against 0.36% and 0.20% for the unchanged model. Raising the regeneration ceiling changed nothing, because it does not bind upward.

Interactions are untested; the drag coefficient, the battery resistance at its lower bound and the temperature dependence were left alone, and the sweep does not reach the winter-only envelope. The DP reference of Section @sec:ems comes from the same model and inherits its limits.
