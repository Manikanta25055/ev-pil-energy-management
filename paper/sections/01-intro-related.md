# INTRODUCTION {#sec:intro}

A battery electric vehicle (EV) spends stored energy on traction, on auxiliaries such as cabin heating, and on losses that depend on how it is driven. A supervisory energy manager decides, at every control step, how much battery power the drivetrain and the heater may take. Energy management for electrified powertrains has a long record, mostly in hybrids [@biswas2019], and managers trained with reinforcement learning are now a common proposal [@hu2019]. In a battery EV the manager's authority is narrow.

This paper reports an incident from a processor-in-the-loop (PIL) campaign. A Soft Actor-Critic (SAC) energy manager [@haarnoja2018] running on an ESP32-S3 microcontroller [@esp32s3] appeared to use 8.28% less energy than a rule-based manager. It was lower in 14 of 16 settings and by up to 21.6% at the highest driver aggression, and the gain grew with demand, vanished on the gentle urban and highway cycles, and exceeded what the rules' distance from the optimum allowed. Those anomalies raised the alarm. No validation gate did. The cause was a fault in the vehicle model: battery power was billed at the policy's chosen ceiling, while acceleration was computed from the torque requested before that cap. The policy learned to ask for a low ceiling and draw power above it, unbilled; a sweep with no controller in the loop reproduced the effect, with a constant 5 kW ceiling billing 8.05 Wh/km over the full US06 cycle (SIMULATED). The gain is withdrawn here (Section @sec:plant).

The task is narrow. Speed is fixed by an inner tracking loop, and the energy manager sends three numbers: a regeneration blend, a discharge ceiling and a fraction of auxiliary load to shed. An offline dynamic-programming (DP) optimum places the rule-based manager within 0.01% to 0.16% of the best possible energy on four cycles (SIMULATED), so a learned policy has at most that much to win. After the correction it used less energy than the rules in 1 of 16 valid settings on the target and 0.94% more on average (MEASURED). Little room, little gain. The claim is bounded to this vehicle model, this board, one learned algorithm and speed set by the tracking loop, and is no verdict on learned energy management in general.

The starting point of the work is the study by Tangi et al. [@tangi2025]. That study predicted EV range, optimum acceleration and optimum velocity with Random Forest, Extra Trees, Linear Regression and Long Short-Term Memory (LSTM) models [@hochreiter1997] and their ensembles. It used a synthetically generated dataset of 2,000 samples, averaged results over ten randomised partitions and served the trained models through a web application, and the full ensemble was the most accurate. The study showed that data-driven models can estimate driving parameters, and its authors named real-world data and embedded evaluation among the next steps. Three questions follow. Do such models hold on logged driving data? What happens when predictions and policies close a control loop around a vehicle? Can the chain run on an embedded controller under a real-time deadline?

The setting is PIL and not hardware-in-the-loop (HIL). The processor is real; the motor, inverter and battery are simulated. The controller runs on the microcontroller at 100 Hz, while a longitudinal vehicle model on a host computer exchanges state and commands with it every 10 ms. The vehicle model is identified and validated on logged BMW i3 trips [@i3data], 33 of 70 of which passed the eligibility tests, and checked against the Vehicle Energy Dataset (VED) [@ved], while the controllers run the Urban Dynamometer Driving Schedule (UDDS), the Highway Fuel Economy Test (HWFET) and the US06 aggressive schedule [@epacycles]. Acceptance gates and pass criteria were fixed before each experiment. Misses are reported as misses. Every result is labelled MEASURED if it ran on the microcontroller or SIMULATED if it ran on the host only.

Where the energy was actually lost is a separate finding. Under sensor noise, the loss sits in the speed loop, below the energy manager. A two-state Kalman speed estimator [@kalman1960] cut it from 9.44 to 0.24 Wh/km at ten times the nominal noise on US06 (MEASURED). Learned reviewers of sensor faults classified better offline and controlled worse in the loop (SIMULATED). Accuracy did not predict benefit, for the second time.

This paper makes five contributions.

- An audited case of a vehicle-model artefact that produced an 8.28% learned-policy gain, with the controller-free sweep that exposed it and three checks that would have caught it before the campaign.
- A headroom bound from dynamic programming, 0.01% to 0.16%, that explains why no honest gain was available to the energy manager.
- A corrected comparison of a rule-based manager and a SAC policy on the target, reported with paired statistics over 12 distinct conditions and the spread between repeated runs.
- A measured estimation gain in the speed loop, and the finding that offline fault-classification accuracy did not predict closed-loop benefit.
- On-device costs, timing and memory, reported next to the accuracy of each learned component.

Section @sec:related reviews related work and Section @sec:platform the platform and its acceptance gates. Section @sec:plant presents the vehicle model and the artefact, Section @sec:ems the corrected comparison, Section @sec:forecast on-device forecasting and Section @sec:estimation speed estimation and fault detection. Section @sec:planning treats the simulated speed planner, Section @sec:discussion the limits of the evidence and Section @sec:conclusion the conclusions.

# RELATED WORK {#sec:related}

## Data-Driven Range and Energy Prediction

Models of EV energy use are usually fitted to logged or generated trips and scored offline. The study of Tangi et al. [@tangi2025] belongs here: it compared four model families and their ensembles on a synthetic dataset and exposed them through a web application. Zhang et al. [@zhang2020] used real-world driving data of 55 electric taxis in Beijing and reported a root mean squared error (RMSE) of 0.159 kWh, and Baluch et al. [@baluch2026] fitted a nonlinear autoregressive model with exogenous inputs to on-road data from four trips, with a mean squared error 30% below that of an LSTM network. Gradient-boosted trees [@chen2016], Transformers [@vaswani2017] and physics-based loss terms [@raissi2019] are further candidates. None of these studies acts on its predictions or states a run time on a vehicle-class processor.

## Learned Energy Management

Reinforcement learning has been applied to energy management mainly in hybrid vehicles. A deep Q-network strategy for a power-split hybrid bus reached about 89% of the fuel economy of DP on an unseen driving condition [@wu2018], a SAC-based strategy for a hybrid tracked vehicle was compared with standard SAC and with DDPG in simulation [@sun2022], and a look-ahead strategy for a parallel hybrid combined velocity prediction with reinforcement learning and was checked on a HIL bench against DP [@liu2017]. A learned power manager for a battery EV with an ultracapacitor was compared with rules and DP [@xiong2018]. The reference points are classical. DP [@bellman1957] gives the optimum for a known cycle, Pontryagin's minimum principle offers an analytical route [@kim2011], and the equivalent consumption minimisation strategy (ECMS) turns the problem into an instantaneous cost [@paganelli2002; @sciarretta2004]. Rules are the usual deployable baseline.

Headroom differs between settings. In a hybrid, the split between engine and motor is a large lever. Here the manager holds only a regeneration blend, a discharge ceiling and a shed fraction, with speed held by a tracking loop, and the DP optimum is within 0.16% of the rules. Hybrid gains do not carry over, and a null result here does not contradict them.

Evaluation practice matters as much as the method. Deep reinforcement learning results differ across seeds and implementation choices [@henderson2018], and point estimates over a few runs hide uncertainty that intervals and rank statistics would show [@agarwal2021]. Paired differences with intervals and a rank test are reported here for that reason.

## Eco-Driving and Speed Planning

When speed is free, the problem changes. Sciarretta et al. [@sciarretta2015] cast energy-efficient driving as an optimal control problem and survey its solutions, and deep reinforcement learning has been applied to eco-driving in urban scenarios [@wegener2021]. The DP planner of Section @sec:planning belongs to the classical family. It shows where headroom reappears and is not offered as a new planner.

## Simulator Artefacts and Specification Gaming

A learner optimises the simulator it is given, not the vehicle it stands for. Amodei et al. [@amodei2016] list reward hacking among the concrete problems of learned systems, including exploits of how a reward is implemented, Skalse et al. [@skalse2022] define it formally as optimisation of an imperfect proxy that lowers the true objective, and Lehman et al. [@lehman2020] collected cases in which evolutionary search exposed bugs in simulations and exploited them. Sim-to-real work addresses a neighbouring gap, between simulator and physical system, by randomising simulator parameters [@tobin2017] and related methods [@zhao2020]. The artefact here is a plain instance of the first kind: a billing rule that did not act on motion. Section @sec:discussion lists checks that would have exposed it.

## Embedded and In-the-Loop Validation

Vehicle controllers are validated through a staged path of model-, software-, hardware-in-the-loop and vehicle tests [@biswas2019]. HIL benches drive a real controller or real energy storage from a simulated vehicle, as in the validation of a learned power manager on an xPC Target platform [@xiong2018]. PIL is an earlier step. Inference frameworks for microcontrollers [@david2021] and joint model and library design [@lin2020] show that small devices can run networks, and integer quantisation [@jacob2018] and distillation [@hinton2015] shrink them. Dulac-Arnold et al. [@dulac2021] list the constraints that separate laboratory reinforcement learning from deployment, among them real-time inference; what the cited works do not give, in the vehicle-energy setting, is a measured loop with a stated deadline on the target together with a rule baseline run through the same loop. This work supplies one.

## Estimation and Sensor-Fault Detection

Kalman filtering [@kalman1960] is a standard tool for state estimation, including vehicle speed; a recent example fuses inertial, steering-angle and wheel-speed sensors [@seo2025]. Model-based fault detection compares measured signals with model predictions and examines the residual [@isermann2005], and learned detectors are the alternative: LSTM networks for time-series anomalies [@malhotra2015], a general survey [@chandola2009], and the small recurrent models gated recurrent unit (GRU) [@cho2014] and FastGRNN [@kusupati2018]. Here, a classical estimator and a model-based detector are set against learned reviewers, each run in the vehicle loop as well as scored on labelled faults.

Table @tab:related-positioning places six prior works and this study along the axes that matter here. A cell is filled only where the source states the point. The sample is small and chosen for relevance, so the table positions this work and does not survey the field.

Table: tab:related-positioning | Positioning of six prior studies and this work; cells marked not stated could not be confirmed from the source. | width=page
| Work | Data | Closed loop | On target processor | Timing measured | Baseline |
|---|---|---|---|---|---|
| Tangi et al. [@tangi2025] | synthetic | no | no | not stated | model families and ensembles |
| Zhang et al. [@zhang2020] | logged | no | not stated | not stated | conventional method |
| Baluch et al. [@baluch2026] | logged | no | not stated | not stated | LSTM |
| Wu et al. [@wu2018] | not stated | yes (simulated) | not stated | not stated | Q-learning, DP |
| Sun et al. [@sun2022] | not stated | yes (simulated) | not stated | not stated | SAC, DDPG |
| Xiong et al. [@xiong2018] | not stated | yes (HIL) | real-time target (xPC) | not stated | rules, DP |
| This work | logged | yes (PIL) | yes | yes | rule-based |
