# The Transformer at the G1 configuration, and ablation A1

Week 5 of the schedule: the candidate model, sized by the compute budget rather
than by ambition, and the ablation that asks whether physics-informing earns
its place.

Measured 2026-08-31 on the BMW i3 archive. 55,125 training windows over 19
trips, 29,252 validation windows over 7. Test trips are sealed. Configuration
is the trimmed row of `docs/g1-compute-budget.md`: sequence 32, `d_model` 32,
2 layers, feed-forward width 64. That row was chosen because it fits the 40 ms
G5 latency budget, and training a different one would make the budget
decorative.

## Arms

| Arm | Outputs | Loss | Parameters |
|---|---|---|---|
| `plain-1ch` | battery power | data only | 18,366 |
| `plain-4ch` | power, current, voltage, charge | data only | 21,336 |
| `pi-4ch` | the same four | data plus residuals | 21,336 |
| `pi-4ch-r2` | the same four | plus charge conservation | 21,336 |

`plain-4ch` and `pi-4ch` differ only in the loss. That is what makes A1 a test
of physics-informing rather than of capacity, and the matched count is asserted
in `tests/forecast/test_models.py` rather than arranged by hand.

`plain-1ch` exists because the four-channel arms receive supervision on three
channels the LSTM never saw. Comparing a four-channel model against a
one-channel one would confound the architecture with the extra targets, so the
ladder comparison uses the one-channel arm.

## Result

At 3.0 s, three seeds per arm.

| Arm | RMSE, one model | RMSE, 3-seed mean | R^2 | vs persistence |
|---|---|---|---|---|
| Persistence | 13.219 kW | — | 0.183 | — |
| Ridge | 11.308 kW | — | 0.402 | 14.5% |
| LSTM | 11.120 kW | 11.007 kW | 0.433 | 15.9% |
| **Transformer `plain-1ch`** | **11.029 kW** | **10.926 kW** | **0.442** | **16.6%** |
| Transformer `plain-4ch` | 11.057 kW | 10.954 kW | 0.439 | 16.4% |
| Transformer `pi-4ch` | 11.052 kW | 10.952 kW | 0.439 | 16.4% |
| Transformer `pi-4ch-r2` | 11.542 kW | 11.515 kW | 0.380 | 12.9% |

The Transformer is the best forecaster in the ladder, on one model and on a
seed mean. It is also the narrowest margin in the ladder: 0.8% over the LSTM
and 2.5% over a linear solve. Seed spread within an arm is 0.038 to 0.174 kW,
which is the same order as the gaps between arms, so the ordering of the top
three is supported but not commanding.

Every fitted arm passes G4. The weakest of them clears the 10% bar by four
points.

## Ablation A1: does physics-informing help

**No, and that is a reportable answer.** Spec 3.2 pre-accepted it.

```
plain     11.098   11.073   11.001     mean 11.057 kW
informed  11.114   11.101   10.940     mean 11.052 kW      +0.0%
```

Five watts of difference on eleven kilowatts, at matched parameter count and
matched seeds. The residual loss does not make the forecast more accurate.

**What it does buy is consistency, and by a wide margin.**

| | violation rate | mean absolute residual |
|---|---|---|
| r1 electrical, plain | 0.245 | 372.6 W |
| r1 electrical, informed | **0.025** | **139.4 W** |
| r3 terminal voltage, plain | 0.913 | 8.40 V |
| r3 terminal voltage, informed | **0.726** | **5.00 V** |

Tolerances are 500 W on r1 and 2 V on r3, stated in `scripts/run_transformer.py`
rather than defaulted in a library, because a number that decides what counts
as violating physics belongs in the report.

A tenfold reduction in electrical-consistency violations for no accuracy cost
is worth having on its own terms. A model whose predicted power, current and
voltage disagree with each other by 373 W on a quarter of its steps is not
wrong about power, but it is not describing a battery either, and the
controller downstream reads more than the power channel. The honest statement
of A1 is that the physics term is a consistency mechanism, not an accuracy
mechanism, and the paper should claim it as one.

## Charge conservation, and why it is switched off

Spec 4.2's second residual is `dSoC/dt + I/(3600*Q)`. It is disabled by
default, and the reason is a property of the dataset rather than of the law.

**The median 3.0 s horizon in this archive contains exactly one distinct SoC
value.** The logged charge channel holds across 95.8% of consecutive 10 Hz
samples and moves in bursts, with gaps of one sample when it moves and 75 or
more when it does not, up to 59 seconds. Logged charge change over a typical
horizon is 0.00, against a coulomb-implied 2.2e-4.

So the data loss pushes predicted charge to stay flat, because flat is what the
channel records, while the residual pushes it to fall by the integral of the
predicted current. They disagree, and the disagreement is caused by the logging
rate. That was the argument; `pi-4ch-r2` is the measurement.

```
r2 off   11.114   11.101   10.940     mean 11.052 kW
r2 on    11.614   11.540   11.472     mean 11.542 kW      -4.4%
```

Switching it on costs 4.4% of accuracy. It reduces its own mean residual by a
factor of 8.6, from 4.47e-3 to 5.18e-4, and moves its violation rate only from
0.988 to 0.966. It also gives back some of r1's gain, the electrical violation
rate rising from 0.025 to 0.074, because the network is now spending capacity
reconciling two targets that cannot both be met.

Charge conservation is a real constraint and it is not being dismissed. It is
testable over minutes, which is the trip-energy check G2 already makes. It is
not testable over three seconds on a channel with this resolution.
`evpil.forecast.physics.r2_charge_pointwise` keeps spec 4.2's literal form so
the measurement can be reproduced.

## One residual was substituted, and here is the reason

Spec 4.2 writes the third residual as a power-balance inequality,
`relu(P_mech/eta_max + I^2*R - P)`. It needs future mechanical power, which is
not a channel of the canonical schema, is not available at inference, and could
only be reconstructed by putting the plant inside the training loop, which
would make the forecaster depend on the model G2 validated separately.

What replaces it is the Thevenin relation the project already built and
validated: `V - (OCV(SoC) - I*r0)`. It constrains the same three channels, it
is computable from the model's own outputs, and it is an equality the logged
data supports. It carries one assumption with it: the OCV curve is a
representative 96s NCA characteristic rather than an i3 measurement (CAVEATS
note 5), so r3 imports that assumption into the loss.

## The weight was tuned on validation

| lambda | RMSE at 3.0 s | r1 violation | r3 violation |
|---|---|---|---|
| 0.01 | 11.117 kW | 0.399 | 0.913 |
| **0.10** | **11.114 kW** | **0.121** | **0.727** |
| 1.00 | 11.249 kW | 0.012 | 0.001 |

Chosen on validation RMSE, which selects 0.1. Worth noting what the table shows
either side of that: at lambda 1.0 the residuals are essentially eliminated,
r3 falling to a violation rate of 0.001, for 1.2% of accuracy. If the
downstream controller turns out to care more about a self-consistent state than
about the last percent of power accuracy, that trade is available and it is
cheap. The choice made here optimises the forecast, because the forecast is
what G4 gates.

## What it costs on the device

The full deployed graph, embedding and head included, rather than the
encoder-only figure G1 published.

| Arm | RMSE at 3 s | MACs | Latency | % of 40 ms | Size | Fits G5 |
|---|---|---|---|---|---|---|
| Ridge | 11.308 kW | 7,680 | 0.26 ms | 0.6% | 7.5 KB | yes |
| XGBoost | 11.290 kW | not a MAC workload | — | — | ~3,658 KB | **no** |
| LSTM, one model | 11.120 kW | 591,744 | 19.84 ms | 49.6% | 20.4 KB | yes |
| **Transformer `plain-1ch`** | **11.029 kW** | 664,512 | 22.28 ms | 55.7% | 17.9 KB | **yes** |
| Transformer `pi-4ch` | 11.052 kW | 667,392 | 22.38 ms | 56.0% | 20.8 KB | yes |

**The best forecaster fits, at 56% of the latency budget and 6% of the memory
budget.** That is the outcome the budget-first procedure was designed to
produce, and it is worth saying plainly that it was not guaranteed: the
plan-implied configuration would have needed 175.8 ms and did not fit at all.

The Pareto front is the result, per spec 7.2. Read across it: the ridge reaches
87% of the achievable skill for 1.2% of the compute; the LSTM reaches 96% for
89% of it; the Transformer takes the remainder. Whether the last 2.5% over a
linear solve is worth 22 ms of a 40 ms budget is a question the controller
ablation A3 answers, not this document.

## Limitations

- **Validation only.** Test trips are sealed.
- **Three seeds.** Enough to show the seed spread is smaller than the gap to
  persistence, not enough to separate the Transformer from the LSTM with
  confidence. Their intervals overlap almost entirely.
- **Latency is estimated, not measured.** Exact MAC counts divided by G1's
  measured throughput, excluding framework overhead and assuming the scalar
  int8 loop rather than ESP-NN vector kernels. G5 is the measurement.
- **int8 is not applied yet.** Sizes are parameter counts at one byte each, and
  post-training quantisation may cost accuracy. That is ablation A2.
- **Twelve epochs, one learning rate.** Every arm got the same budget, which
  makes the comparison fair but leaves all of them undertrained relative to
  what a full sweep would find.
- **A1 was run at one lambda.** The null result is at lambda 0.1. The sweep
  shows the accuracy cost stays under 1.2% out to lambda 1.0, so the conclusion
  is not sensitive to the choice, but it was not repeated at every weight with
  three seeds.

## Figures

- `figures/transformer-a1.png`: the Transformer against the ladder; every seed
  of A1; what the residual loss bought; and the weight's accuracy-consistency
  trade

## Reproducing

```bash
PYTHONPATH="src:." python3 scripts/run_transformer.py --lambda-grid 0.01 0.1 1.0
PYTHONPATH="src:." python3 scripts/report_deploy_cost.py
PYTHONPATH="src:." python3 scripts/plot_transformer.py
```

Per-step metrics are in `docs/transformer-a1.csv`, the summary and per-seed
results in `docs/transformer-a1.json`, and the cost table in
`docs/forecast-deploy-cost.csv`. The residuals are
`src/evpil/forecast/physics.py`.
