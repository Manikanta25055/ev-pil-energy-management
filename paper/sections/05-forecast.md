# ON-DEVICE FORECASTING: ACCURACY AGAINST COST {#sec:forecast}

This section is a supporting result. A forecast of battery power for the next few seconds has to run on the same microcontroller as the control loop, so the question here is how accurate such a forecast can be and what each model costs on the ESP32-S3. The energy manager of Section @sec:ems did not use any of these forecasters. Accuracy was computed on the host from validation trips (host-simulated); timings marked target-measured were taken on the target. The test trips were not opened.

## Task and Safeguards

The task is to predict battery power at each of the next 30 samples, a horizon of 3.0 s at 10 Hz, from the preceding 32 samples (3.2 s) of eight signals: speed, acceleration, state of charge (SOC), battery current, battery voltage, ambient temperature, road grade and auxiliary power. Splits are by trip: 55,125 training windows from 19 trips and 29,252 validation windows from 7 trips.

Three safeguards were fixed before any model was fitted. Battery power is voltage times current and both are inputs, so inputs end at sample 32 and targets begin at sample 33, which an automated test asserts. A ridge regression with 257 parameters scored an $R^{2}$ of 0.4018 on real targets and $-0.0044$ on shuffled ones. Persistence holds the last value. It gives 13.219 kW of root-mean-square error (RMSE) at 3 s, and gate G4 requires 10% below that, or 11.897 kW.

## Accuracy Against Cost

The ladder runs, in order of cost, from persistence to linear regression, gradient-boosted trees (XGBoost) [@chen2016], a one-layer long short-term memory network (LSTM) [@hochreiter1997] and a two-layer Transformer encoder [@vaswani2017]. Table @tab:forecast-ladder and Fig. @fig:forecast-cost give the result. Each neural model is scored at its best validation epoch, so its error is slightly optimistic.

Table: tab:forecast-ladder | Forecast error at 3 s on validation trips (host-simulated) and cost on the ESP32-S3. Latency is target-measured where stated and otherwise estimated from operation counts. | width=page
| Model | Error at 3 s (kW) | Gain over persistence (%) | Size (KB) | Latency (ms) | Share of 40 ms budget (%) |
|---|---|---|---|---|---|
| Persistence | 13.219 | 0 | 0 | 0 | 0 |
| Linear regression | 11.308 | 14.5 | 7.5 | 0.26 (estimated) | 0.6 (estimated) |
| XGBoost | 11.290 | 14.6 | about 3,658 | not applicable | not applicable |
| LSTM | 11.120 | 15.9 | 20.4 | 35.07 (target-measured) | 88 |
| Transformer | 11.029 | 16.6 | 17.9 | 36.46 (target-measured) | 91 |

Every fitted model passes G4, by at least 14.5%. That settles little, because linear regression had already cleared the bar before the larger models existed, so the pass shows that a forecast is possible and says nothing in favour of a Transformer. Linear regression gives 87% of the Transformer's gain for 1.2% of its estimated compute. XGBoost is about twelve times over the 300 KB memory budget and stays as an offline reference. Seed spread within a model, 0.038 to 0.174 kW, is as large as the gaps between the top three.

![fig:forecast-cost](paper/figures/fig-forecast-cost.png){width=col}
Caption: Forecast error at 3 s against time per forecast. Open markers are estimates from operation counts; filled markers are target-measured on the ESP32-S3 (vendor-framework build). XGBoost has no latency figure and sits at the right edge.

## Cost on the Target

The first Transformer cost, 22.28 ms, was the multiply-accumulate count divided by the throughput measured on the target. The same network in 8-bit C then took 36.46 ms per forward pass on the vendor-framework build, 91% of the 40 ms budget of gate G5, and 35.03 ms on the Arduino core (target-measured). The measurement was 64% above the estimate. Softmax, which needs 1,024 exponentials per head in each of four heads and two layers, and layer normalisation together account for 7.89 ms of the 14.18 ms gap, and the rest is not explained in the record. The LSTM has no softmax and was further off, 19.84 ms estimated against 35.07 ms measured, so the optimism lies in the method. Not the architecture. Operation counts can rank models. They should not set budgets. The timed code uses fixed weights, so it times the graph and says nothing about what a trained model would predict.

Rounding weights and activations to 8 bits [@jacob2018] raised the error of the final-epoch model from 11.051 kW to 11.156 kW, a loss of 0.95%, and shrank the stored model 3.6 times, from 71.7 KB to 20.2 KB (host-simulated). The timed graph needs 28,894 bytes, 9.4% of the memory budget. Gate G5 is not closed in full. The converted model has not been run through an embedded runtime on the target, so the 8-bit accuracy is a host figure only.

Two further studies, both run on the host, added nothing to accuracy. A physics-informed loss [@raissi2019] left the error unchanged, 11.057 kW against 11.052 kW, though it cut the share of steps where power disagrees with voltage times current by more than 500 W from 24.5% to 2.5%; consistency improved and accuracy did not. Distillation from a larger teacher [@hinton2015] did not help. The students were worse by 0.20% and 0.89%, and the sign changed between seeds.
