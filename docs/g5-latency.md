# The forecaster on silicon: measured latency and int8 accuracy

Two halves of gate G5, measured separately because they can be.

G5 asks whether the forecaster runs on the device within 40 ms on one core,
with model plus tensor arena at most 300 KB. What is reported here is the
latency of the deployed graph shape measured on the chip, and the accuracy cost
of 8-bit arithmetic measured offline. What is not reported is a converted
TFLite-Micro model, because that toolchain is not installed. The distinction is
kept throughout: these two measurements decide whether deployment is worth
attempting, and they answer yes.

Measured 2026-08-31 on the ESP32-S3 in `docs/hardware-inventory.md`.

## Latency, measured rather than divided

```
EVPIL-G5 seq=32 d_model=32 layers=2 heads=4 horizon=30
EVPIL-G5 forward_us=36457.2 reps=50
EVPIL-G5 matmul32x32x64_us=2336.08 softmax32x32_us=906.42 layernorm32x32_us=158.76
EVPIL-G5 weight_bytes=17600 arena_bytes=11294
```

One forward pass takes **36.5 ms** against a 40 ms budget. Repeatable to 0.1
microseconds across resets and across reflashes.

| | Time | Share of the 40 ms budget |
|---|---|---|
| Measured, scalar int8 C | **36.46 ms** | 91% |
| Estimated from MAC count at G1 | 22.28 ms | 56% |

**The estimate was 64% low.** That is the result worth carrying into the paper,
and it is a direct consequence of how the estimate was built. Dividing a
multiply-accumulate count by a measured multiply-accumulate rate prices the
multiplies and nothing else.

What the multiplies do not include:

| Operation | Per call | Calls | Total |
|---|---|---|---|
| Softmax over a 32x32 score matrix | 906 us | 8 | 7.25 ms |
| Layer normalisation over 32x32 | 159 us | 4 | 0.64 ms |

Softmax alone is 20% of the forward pass and the MAC count assigned it zero.
There are four heads in each of two layers, each needing 1,024 exponentials, and
an exponential is not a multiply-accumulate.

The matmul rate itself validates G1. The 32x32x64 feed-forward matmul runs
65,536 multiply-accumulates in 2,336 microseconds, which is 28.1 MMAC/s against
G1's measured 29.82 on a synthetic loop. Within 6%, and in the direction real
memory access would push it.

## What this measurement is and is not

**It is** the real graph at the real shapes, in int8, with int32 accumulation
and requantisation between operations, on the real chip.

**It is not** the trained model. The weights are a fixed pattern, so this
measures how long the graph takes and says nothing about what it would predict.
Accuracy is the other half of this document.

**It is not** TFLite-Micro. A framework adds interpreter overhead, which would
make this slower. It also brings ESP-NN vector kernels, which would make the
matmuls substantially faster, and a lookup-table softmax, which would cut the
7.25 ms sharply. The two effects point in opposite directions and neither is
guessed at here.

**It is the slowest plausible implementation.** Scalar C, no vector
instructions, a floating-point `expf` per attention weight. That it fits at
36.5 ms with 9% of margin is therefore a lower bound on the real margin, not an
upper one.

## Memory

```
weights   17,600 bytes
arena     11,294 bytes
total     28,894 bytes    9.4% of the 300 KB budget
```

Memory is not close to binding, which is what the hardware inventory predicted
once the board was identified as an N8R8 with 8 MB of PSRAM. MACs were the
binding constraint, as section 7.1 of the design document argued, and the
measurement above confirms it.

## Accuracy at 8 bits, ablation A2

Every weight and every activation rounded to the values an 8-bit tensor can
hold, three seeds, scored on validation.

| | RMSE at 3.0 s | Against persistence |
|---|---|---|
| float32 | 11.051 kW | 16.4% |
| int8 | 11.156 kW | 15.6% |
| Persistence | 13.219 kW | — |

**Quantisation costs 0.95%.** The int8 model still clears G4's 10% bar with
half again as much margin as it needs, and it is 3.56 times smaller: 71.7 KB of
float32 weights become 20.2 KB.

The independently written cost model predicts 20,664 bytes for this
configuration and the quantised model measures 20,664 bytes. That agreement is
worth stating because the two were derived separately, one from shape
arithmetic and one from counting a real network's parameters.

Ten weight tensors were quantised and eight activation points calibrated. Both
counts are asserted in the tests, because the first version of this code got
them wrong in a way that flattered the result. It selected tensors by module
type, which silently missed `MultiheadAttention`'s input projection, 35% of the
weights, and it hooked `out_proj`, whose forward never runs because attention
applies it functionally. A quantisation sweep that leaves a third of the model
in float reports a cost that is far too low.

**Calibration used training windows only**, 4,096 of them spread evenly across
all 19 training trips. The design document names a calibration set built from
test data as a subtle and common leak, and the same argument covers validation:
the numeric ranges a deployed model uses must not be chosen with the data it is
about to be scored on.

## Verdict

Neither half of G5 is the full gate, which needs the trained weights running
through a real runtime on the device. Both halves say the same thing about
whether that is worth doing.

- Latency fits at 91% of budget, measured, on the slowest implementation.
- Memory fits at 9.4% of budget.
- 8-bit arithmetic costs under 1% of accuracy.

The remaining work for G5 proper is the converter and the runtime, and the risk
it carries is now bounded on both sides: interpreter overhead pushes the 36.5 ms
up, vector kernels and a table-based softmax push it down.

## What this changes

The cost table in `docs/forecast-deploy-cost.csv` reports estimates for every
arm. Those estimates are still the right way to rank models against each other,
because the missing overhead is roughly proportional across architectures. They
are no longer the right thing to quote as a latency. `evpil.forecast.deploy`
now carries both `ESTIMATED_ENCODER_US` and `MEASURED_ENCODER_US`, and a test
asserts the gap between them rather than tidying it away.

The LSTM was measured the same way, and it settles what the Transformer's gap
was evidence of.

| Arm | Estimated | Measured | Ratio |
|---|---|---|---|
| Transformer, seq 32, d_model 32, 2 layers | 22.28 ms | 36.46 ms | 1.64x |
| LSTM, hidden 64, 1 layer | 19.84 ms | 35.07 ms | 1.77x |

The LSTM has no softmax. If attention were the explanation, its estimate would
have been close. It is further off than the Transformer's, not closer: four
gates over 64 units on each of 32 timesteps is 8,192 sigmoid and tanh
evaluations, which is the same order of nonlinear work under a different name.

**The estimating method was optimistic, not the architecture.** That is a more
useful finding than a result about attention would have been, because it
applies to every arm in the ladder and to any arm added later.

It also changes the comparison between the two. Estimated, the LSTM looked 11%
faster than the Transformer. Measured, it is 4% faster, for 0.8% worse
accuracy. The choice between them is much closer than the estimates implied,
and it is close enough that the controller ablation A3 should decide it rather
than the forecasting numbers alone.

## Reproducing

Set `RUN_G5_BENCHMARK` to 1 in `firmware/main/main.c`, then:

```bash
cd firmware && python "$IDF_PATH/tools/idf.py" -p /dev/cu.usbmodem1101 flash
PYTHONPATH="src:." python3 scripts/run_a2.py
```

The benchmark is `firmware/main/bench_encoder.c`. Quantisation results are in
`docs/a2-quantisation.json` and per-horizon figures in
`docs/a2-quantisation.csv`. Remember to set the flag back to 0, or the board
runs the benchmark instead of the control loop.
