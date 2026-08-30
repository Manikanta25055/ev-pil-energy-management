# The model ladder, with what each rung costs on the device

Spec 4.2's forecasting arms, scored on validation against gate G4, and costed
against the G5 compute budget that G1 measured. Test trips are not opened.

Measured 2026-08-31. 55,125 training windows over 19 trips, 29,252 validation
windows over 7. Windows are 32 input samples (3.2 s at 10 Hz) predicting 30
future samples (3.0 s) of battery power. Baselines and guards are in
`docs/forecast-guards.md`.

## Result

At the final horizon step, 3.0 s ahead, which is the step G4 is written
against.

| Arm | RMSE | R^2 | vs persistence | vs ridge |
|---|---|---|---|---|
| Persistence | 13.219 kW | 0.183 | (baseline) | −16.9% |
| Drift | 26.172 kW | −2.204 | −98.0% | −131.4% |
| Ridge, 7,710 weights | 11.308 kW | 0.402 | 14.5% | (baseline) |
| XGBoost, 15,103 trees | 11.290 kW | 0.404 | 14.6% | 0.2% |
| LSTM, one model | 11.120 kW | — | 15.9% | 1.7% |
| LSTM, mean of 5 seeds | 11.007 kW | 0.433 | 16.7% | 2.7% |

**G4 passes on all three fitted arms.** The gate asks for 10% over persistence
and the weakest of them returns 14.5%.

## Is the recurrent gain real

The gap between the LSTM and the ridge is 1.7% for one model. That is small
enough that a single training run could not have established it, so the arm was
run five times.

```
seed 0  11.137 kW     seed 3  11.117 kW
seed 1  11.123 kW     seed 4  11.170 kW
seed 2  11.054 kW
```

Spread across seeds is 0.117 kW; the distance from the worst seed to the ridge
is 0.138 kW. Every seed beats the ridge, by between 1.2% and 2.3%, and the LSTM
wins on 6 of the 7 validation trips. The gain is consistent. It is also small,
and both halves of that sentence belong in the paper.

Bootstrapping over trips, the final-step intervals are persistence
[10.594, 16.463], ridge [9.055, 14.049], XGBoost [9.005, 13.917] and LSTM
[8.844, 13.638] kW. They overlap almost entirely, because seven trips differ
from each other far more than four models differ from each other. The per-trip
table is the honest view and the interval is why: on TripB12 every arm scores
near 6.7 kW and on TripB32 every arm scores near 15.5. **Which trip you are on
matters more than which model you run.**

## Where in the horizon the gain lives

| Horizon | Ridge | LSTM | LSTM vs ridge |
|---|---|---|---|
| 0.1 s | 0.842 kW | 0.910 kW | −8.1% |
| 0.5 s | 2.617 kW | 2.772 kW | −5.9% |
| 1.0 s | 5.425 kW | 5.353 kW | +1.3% |
| 2.0 s | 9.296 kW | 8.965 kW | +3.6% |
| 3.0 s | 11.308 kW | 11.007 kW | +2.7% |

The LSTM is **worse than the ridge over the first second** and better after it,
crossing over at about 0.9 s. Near-term battery power is nearly determined by
the last observed sample, and a linear map reads that sample directly while the
LSTM has to pass it through a 64-unit hidden state that is being asked to serve
all 30 outputs at once. Further out, the last sample stops being enough and the
context the recurrence carries starts to pay.

This is a usable structure rather than a curiosity. The controller consumes the
forecast as a summary, the mean and max over the horizon (spec 4.3), which is
dominated by the far steps where the LSTM leads. It also says plainly what a
hybrid would look like if the near half ever matters: a linear head for the
first second and a recurrent one after it.

Pooling the horizon into one number would have hidden all of it, which is what
spec 6.2 asks per-step reporting to prevent.

## XGBoost adds nothing

15,103 boosted trees land 0.2% ahead of a 257-input linear solve. Within the
bootstrap interval that is nothing at all.

The reading is not that the arm was mistuned. Depth, learning rate and
regularisation were swept on validation and the variants land between 11.29 and
11.36 kW; early stopping fires between 58 and 216 rounds. A function class that
can represent arbitrary interactions, given 256 inputs and 55,125 windows,
finds no interaction worth 1% over a hyperplane. Whatever is predictable about
battery power 3 s ahead from this window is close to linear, and the rest is
the driver.

## What each rung costs on the ESP32-S3

The point of the project is a model that runs on the device, so accuracy without
cost is half a result. G1 measured **29.82 MMAC/s** int8 on one core. G5 asks
for the deployed forecaster within **40 ms on core 1** with model plus tensor
arena at most **300 KB**.

| Arm | RMSE at 3 s | MACs | Latency | % of 40 ms | Size | Fits G5 |
|---|---|---|---|---|---|---|
| Persistence | 13.219 kW | 0 | — | — | 0 | yes |
| Ridge | 11.308 kW | 7,680 | 0.26 ms | 0.6% | 7.5 KB | yes |
| XGBoost | 11.290 kW | not a MAC workload | — | — | ~3,658 KB* | **no** |
| LSTM, one model | 11.120 kW | 591,744 | 19.84 ms | 49.6% | 20.4 KB | yes |
| LSTM, 5 seeds | 11.007 kW | 2,958,720 | 99.22 ms | 248.0% | 102 KB | **no** |
| Transformer, G1 trimmed | not yet trained | 655,360 | 21.98 ms | 54.9% | 16 KB | yes |

\* estimated from node counts at 8 bytes per node, which is generous. Tree
traversal is branches and loads rather than multiply-accumulates, so no latency
is quoted for it: there is no measured throughput to divide by and inventing
one would dress a guess as a measurement.

Two rows change what can be claimed.

**XGBoost is not deployable.** At roughly 3.7 MB it exceeds the 300 KB budget
by more than twelve times, and that is against a deliberately optimistic node
encoding. It stays in the ladder as an offline reference, since it answers
"would a strong tabular model have done better" and the answer is no, but it
is not a candidate for the device, and no amount of accuracy would have made it
one. Better to know that now than after tuning it.

**The best LSTM number is not a deployable number.** The 11.007 kW figure is
the mean prediction of five separately trained models. That is an ensemble, it
costs five times the latency and five times the memory, and at 99 ms it misses
the 40 ms budget by a factor of two and a half. What can actually be flashed is
one model at 11.120 kW. The gap between the two is 1.0%, and reporting the
ensemble figure as though it were the deployed one would be the same class of
error as the predecessor work's ensemble weights.

The Transformer row is arithmetic over the G1 configuration, carried before the
model exists so that the Week 5 decision is made against a number. The cost
model reproduces G1's published table exactly for both the accepted and the
rejected configuration, and reproduces PyTorch's own parameter count for the
LSTM; both are asserted in `tests/forecast/test_deploy.py`.

## What this means for deployment

The ridge buys 14.5% over persistence for 0.26 ms and 7.5 KB, which is 0.6% of the
latency budget. The LSTM buys another 1.7% for 19.84 ms, which is **77 times
the compute for a seventh of the gain**. The Transformer, if it lands where the
LSTM did, would ask 22 ms for the same.

That is a Pareto front, and spec 7.2 already says the Pareto curve **is** claim
C4 rather than a compromise. The rungs are worth stating in the order the
project would descend them:

1. If the Transformer beats the LSTM by enough to matter, deploy it and report
   the front.
2. If it does not, the deployable choice is one LSTM at half the budget, and
   the finding is that a linear map reaches 87% of the achievable skill for
   1.3% of the compute.
3. If the on-device measurement at G5 turns out worse than these estimates,
   the ridge already fits with three orders of magnitude of headroom, and
   spec 7.3's rung 4, deploy a lightweight predictor and make the Pareto
   curve the headline, is reachable without any loss of result.

None of these is a failure state. The one thing that would be a failure is
arriving at Week 6 having tuned only for accuracy.

## Limitations

- **Validation only.** Test trips are sealed. Nothing here is a test result.
- **Latency figures are estimates, not measurements.** They divide exact MAC
  counts by a measured throughput. They exclude framework overhead, the input
  embedding, quantisation error and memory-bandwidth effects, and they assume
  the scalar int8 loop G1 measured rather than ESP-NN vector kernels, which
  makes them pessimistic in one direction and optimistic in another. **G5 is
  the measurement.** These size the decision beforehand.
- **The LSTM is one architecture, lightly tuned.** Hidden 64, one layer, twelve
  epochs, Adam at 1e-3. A wider or deeper variant might separate further from
  the ridge; it would also cost more, and the cost column is why that trade is
  now visible rather than assumed.
- **Seven validation trips.** The per-trip spread exceeds the between-model
  spread, so the ranking here is better supported for the large gaps
  (everything against persistence) than the small ones (LSTM against ridge).
- **int8 is not yet applied.** Sizes are parameter counts at one byte each.
  Post-training quantisation may cost accuracy; that measurement is ablation
  A2 in Week 6.

## Figures

- `figures/forecast-ladder.png`: RMSE against horizon; every arm measured
  against the ridge; per-trip RMSE at 3.0 s; and accuracy against estimated
  latency with the G5 budget marked

## Reproducing

```bash
PYTHONPATH="src:." python3 scripts/run_ladder.py
PYTHONPATH="src:." python3 scripts/report_deploy_cost.py
PYTHONPATH="src:." python3 scripts/plot_ladder.py
```

Per-step metrics for all five arms are in `docs/forecast-ladder.csv`, the
summary and per-seed results in `docs/forecast-ladder.json`, and the cost table
in `docs/forecast-deploy-cost.csv`. The arms are
`src/evpil/forecast/models.py` and the cost model is
`src/evpil/forecast/deploy.py`.

**One environment note that is not optional.** XGBoost and PyTorch each load
their own OpenMP runtime on macOS. Importing torch first makes a later XGBoost
fit segfault; fitting XGBoost first makes a large LSTM forward pass hang. Both
were reached by ordinary use here. `src/evpil/forecast/_openmp.py` fixes the
order and `tests/conftest.py` applies it to the whole test session; the
subprocess tests in `tests/forecast/test_openmp_order.py` prove both the fault
and the fix.
