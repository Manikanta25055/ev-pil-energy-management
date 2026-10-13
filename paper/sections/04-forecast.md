# ON-DEVICE POWER FORECASTING {#sec:forecast}

A forecast of battery power for the next few seconds has to run on the same microcontroller as the control loop. Two things are reported here: how accurate such a forecast can be, and what each model costs on the ESP32-S3. Accuracy numbers come from validation trips and were computed on the host; timings marked as measured were taken on the target. The test trips were not opened.

## Task and Safeguards

The task is to predict battery power $P_{b}$ at each of the next 30 samples, a horizon of 3.0 s at 10 Hz, from a window of the preceding 32 samples (3.2 s). Each sample holds eight signals: vehicle speed, acceleration, state of charge (SOC), battery current, battery voltage, ambient temperature, road grade and auxiliary power. Splits are by trip, with 55,125 training windows from 19 trips and 29,252 validation windows from 7 trips, and the check is made on the group label carried by each window.

Three safeguards were fixed as design requirements before any model was fitted. The first is a check that the target cannot be computed from the inputs. Battery power is the product of voltage and current, and both are inputs, so the window geometry has to leave a gap: inputs end at sample 32 and targets begin at sample 33, and an automated test asserts this on the sample index. The second is a shuffled-label check. A ridge regression with 257 parameters scored an $R^{2}$ of 0.4018 on the real targets and $-0.0044$ on shuffled targets, which is chance. The third is a persistence baseline, which predicts that power stays at its last value. Persistence reaches 13.219 kW of root-mean-square error (RMSE) at 3 s. Extrapolating the trend is worse, at 26.172 kW. Every model had to beat persistence, and gate G4 sets the bar at 10% below it, or 11.897 kW.

## Model Ladder

The ladder runs from persistence to linear regression, gradient-boosted trees (XGBoost), a one-layer long short-term memory network (LSTM) with 64 hidden units, and a Transformer encoder [@vaswani2017] with two layers, four heads and a model width of 32. Table @tab:forecast-ladder gives the result at 3 s. An untimed latency is an estimate: the multiply-accumulate count divided by the 29.82 million operations per second measured on the target. Each neural model is scored at its best validation epoch, so the validation trips also chose the stopping point and these errors are slightly optimistic; the sealed test trips were not opened to correct for it. The LSTM and Transformer errors are means over training runs of single models, which is what can be deployed; averaging five LSTMs gives 11.007 kW at five times the cost and is left out.

Table: tab:forecast-ladder | Forecast error at 3 s on validation trips, with the cost of each model on the ESP32-S3. Latency is MEASURED on the target where stated and otherwise an estimate from operation counts. | width=page
| Model | Error at 3 s (kW) | Gain over persistence (%) | Parameters or size (KB) | Latency on target (ms) | Share of 40 ms budget (%) |
|---|---|---|---|---|---|
| Persistence | 13.219 | 0 | 0 | 0 | 0 |
| Linear regression | 11.308 | 14.5 | 7.5 | 0.26 (estimated) | 0.6 (estimated) |
| XGBoost | 11.290 | 14.6 | about 3,658 (estimated) | not applicable | not applicable |
| LSTM | 11.120 | 15.9 | 20.4 | 35.07 (measured) | 88 |
| Transformer | 11.029 | 16.6 | 17.9 | 36.46 (measured) | 91 |

Gate G4 is passed by every fitted model, by at least 14.5%. It was passed before the larger models existed: the linear regression had already cleared it when the baselines were computed. A pass of this gate therefore shows that a forecast is possible but says nothing in favour of a Transformer, and every model is reported against the linear regression as well. XGBoost does not fit the 300 KB memory budget, being about twelve times over it, and remains in the table as an offline reference.

The central comparison is in Fig. @fig:forecast-cost. The Transformer reaches 11.029 kW against 13.219 kW for persistence, a gain of 16.6%, while linear regression reaches 11.308 kW. Linear regression gives 87% of the Transformer's benefit for 1.2% of its estimated compute. The ordering of the top three is narrow, since seed spread within a model, 0.038 to 0.174 kW, is the same order as the gaps between models. Fig. @fig:forecast-horizon shows the error along the horizon. Linear regression and the Transformer stay close at every horizon, and both stay clear of persistence.

![fig:forecast-cost](paper/figures/fig-forecast-cost.png){width=col}
Caption: Forecast error at 3 s against time per forecast. Open markers are estimates from operation counts; filled markers are MEASURED on the ESP32-S3. XGBoost has no latency figure and is pinned at the right edge.

![fig:forecast-horizon](paper/figures/fig-forecast-horizon.png){width=col}
Caption: Forecast error against horizon on the validation trips, SIMULATED on the host. The Transformer curve is the mean prediction of three trained models and reaches 10.926 kW at 3 s, against 11.029 kW for a single model.

## Physics-Informed Training

A physics-informed variant adds penalty terms to the data loss [@raissi2019]. The model therefore predicts power, current, voltage and charge, and two residuals tie them together: power must equal voltage times current, and terminal voltage must equal the open-circuit voltage at the predicted charge less the drop across the internal resistance. Each residual is scaled by its channel and weighted by 0.1, chosen on validation RMSE. Plain and informed models share 21,336 parameters and seeds, so only the loss differs.

Accuracy does not change: the mean error over three runs is 11.057 kW for the plain model and 11.052 kW for the informed one. Consistency with the electrical relation does, and by a wide margin. The share of predicted steps in which power disagrees with voltage times current by more than 500 W falls from 24.5% to 2.5%, with the mean disagreement dropping from 373 W to 139 W. The voltage disagreement with the battery relation falls less, from 8.40 V to 5.00 V, which is still above the 2 V tolerance; 72.6% of steps violate it against 91.3% before. The physics terms buy consistency and leave accuracy where it was.

A third relation, charge conservation, had to be switched off. The logged charge channel holds its value across 95.8% of consecutive samples, so the median 3 s window holds one distinct value, and the recorded change is zero against a physically implied 0.00022. Switching the constraint on cost 4.4% of accuracy (11.542 kW) and moved its own violation rate only from 0.988 to 0.966. Charge conservation is testable over minutes, as the trip-energy check of gate G2 does, but not over 3 s on this channel.

## Cost on the Target

The first cost figure for the Transformer, 22.28 ms, was an estimate: the multiply-accumulate count divided by the measured throughput. The same network was then written in C with 8-bit arithmetic and timed on the ESP32-S3, where one forward pass took 36.46 ms on the vendor-framework build (MEASURED), or 91% of the 40 ms budget of gate G5, and 35.03 ms after the move to the Arduino core (Section @sec:platform). The measurement was 64% above the estimate. The record attributes part of the gap to work that a multiply count does not price: the softmax needs 1,024 exponentials for each of four heads in each of two layers, which takes 7.25 ms, and layer normalisation adds 0.64 ms; together these explain 7.89 ms of the 14.18 ms difference. The LSTM has no softmax and was further off, 19.84 ms estimated against 35.07 ms measured, so the optimism lies in the estimating method, whichever architecture it is applied to. The timed code is scalar C with fixed weights, so it times the graph and says nothing about what a trained model would predict.

Integer quantisation [@jacob2018] was assessed separately, on the host. Rounding all weights and activations to 8 bits raised the error of the final-epoch model from 11.051 kW to 11.156 kW, a loss of 0.95%, and reduced the stored model, weights with their scale factors, from 71.7 KB to 20.2 KB, which is 3.6 times smaller; the 17.9 KB in Table @tab:forecast-ladder counts the weights alone at one byte each. The timed graph needs 17,600 bytes of weights and 11,294 bytes of working memory, 28,894 bytes or 9.4% of the 300 KB budget. Gate G5 is not closed in full, since the converted model has not been run through an embedded runtime on the target.

## Distillation

Whether a larger teacher distilled into the deployable student [@hinton2015] improves it was tested with a teacher of width 64 and four layers, 136,414 parameters, and students of width 32 (18,366 parameters) and width 16 (5,102). Students trained on an equal mixture of the true target and the teacher's output, and arms were compared seed by seed after quantisation. Distillation did not help. The width-32 student was 21.9 W worse (0.20%) and the width-16 student 99.2 W worse (0.89%), and the sign changed between seeds for both.

The record's reason is that the teacher had nothing to teach. It has 26.7 times the parameters of the smallest student and 23.1 times its memory, yet its error after quantisation, 11.212 kW, is 64.3 W worse than that student's 11.148 kW. All five models lie within 99.2 W of each other, 0.89%, which is less than the 0.95% that 8-bit conversion costs. The half-width student needs 6.1 KB and an estimated 6.75 ms, a figure not to be trusted until timed on the target. Whether a forecast of this accuracy is worth anything to the energy manager is the question taken up in Section @sec:ems.
