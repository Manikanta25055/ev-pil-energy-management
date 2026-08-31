# Week 8: SAC over five seeds, ablation A3, and the actor on silicon

**Date:** 2026-08-31
**Scripts:** `scripts/run_sac.py`, `scripts/verify_actor.py`, `scripts/plot_sac.py`
**Data:** `docs/week8-sac.csv`, `docs/week8-sac.json`, `docs/week8-actor-onchip.json`
**Figure:** `docs/figures/week8-sac.png`

Week 7's dynamic program predicted this week's result from the structure of
the problem: with the speed trajectory fixed by the tracking constraint, the
optimal policy is a constant and a preview cannot help. The prediction was
written into the spec before these runs. The runs were done anyway, because a
predicted result is not a measured one, and because two independent methods
agreeing is worth more than either alone.

They agree.

---

## 1. The comparable scale, and why this table needs one

Every arm is reported twice. **Raw** is watt-hours per kilometre as measured.
**Comparable** adds back the cabin heating the controller switched off, valued
at exactly the energy that shedding it saved.

The second column is not bookkeeping. Every trained controller here beats the
rule-based one on the raw number and loses to it on the comparable one, and
the whole of the difference is cabin heat: the learned policies shed 48 to 50
Wh of it per run of a 16.5 km cycle. Turning the heater down in a Munich
winter is the same trade as driving slower, and this project rejected that
trade in its design document before any of it was measured.

| Controller | Raw Wh/km | Comparable Wh/km | Shed | vs rule |
|---|---|---|---|---|
| Rule-based (2 thresholds, 1 taper) | 153.90 | **153.90** | 0.0 Wh | — |
| DP optimum, comfort priced | 153.89 | **153.89** | 0.0 Wh | −0.01% |
| SAC, forecast in state | 151.88 | 154.92 ± 0.78 | 50.2 Wh | **+0.66%** |
| SAC, forecast removed | 151.74 | 154.68 ± 0.69 | 48.5 Wh | **+0.51%** |

Five seeds per arm, 200,000 training steps each, evaluated on complete runs of
the validation cycle (HWFET). The test cycle (US06) is still sealed. Bootstrap
95% intervals: with-forecast [154.35, 155.61], without-forecast [154.17,
155.23]. **Both intervals lie entirely above the rule-based baseline**, so the
learned controller is not merely no better — it is reliably slightly worse.

Speed-tracking RMSE is 0.00027 m/s in every arm, identical to three
significant figures. That is the inner loop doing its job: the outer loop
cannot buy energy by driving differently, so the comparison is of energy
management and of nothing else.

---

## 2. Ablation A3: the forecast makes no measurable difference

A3 removes the forecast from the controller's observation and changes nothing
else — same training, same evaluation, same seeds, same everything.

> **Forecast minus no forecast: +0.240 Wh/km, 95% CI [−0.669, +1.228].**
> The interval contains zero. A3 is null.

Per-seed differences: −0.78, +0.64, −1.02, +2.11, +0.24 Wh/km. The sign is not
even consistent across seeds.

The spec pre-accepted a null A3 (3.2, R3) as publishable. Week 7 upgraded that
from a possibility to a prediction with a reason: when the speed profile is
fixed, the optimal action does not depend on future power, so knowing future
power cannot help. This is that prediction, measured.

**What the null does and does not say.** It says a preview does not help *this*
controller on *this* problem, and it says so for a structural reason that would
apply to any controller with this action space. It does not say forecasting is
useless in embedded energy management generally — that claim would need a
problem in which the outer loop has authority the forecast could inform, which
is exactly what route (b) of the week 7 open item would build.

It also frees the 20.2 KB and 36.46 ms the forecaster occupies, which is most
of the G5 budget.

---

## 3. The actor on silicon

The chain from a trained policy to a running one has four links, and each is
checked against the one before it:

    PyTorch  →  numpy arrays  →  a generated C header  →  inference in C

| Check | Result |
|---|---|
| Geometry on the board | 8-64-64-3, 4,931 parameters — matches |
| Weights on the board are the weights that were trained | checksum `0x3cc342e5` — matches |
| Actions match the numpy reference | worst difference **2.12e-06**, tolerance 2e-05 |
| Footprint | **19.3 KB** of the 300 KB G5 budget (6.4%) |
| Latency, measured on silicon | **0.121 ms** of the 40 ms budget (0.3%) |

Verdict: **PASS**. The controller is, in embedded terms, free. The forecaster
it was meant to consume is not: that takes 36.46 ms of the same 40.

### The network is 64 wide because 256 does not fit

Stable-Baselines3 defaults to two hidden layers of 256, which is 68,867
parameters and **269 KB in float32** — 90% of the entire G5 memory budget that
the forecaster also has to fit inside. At 64 wide the actor is 4,931
parameters and 19.3 KB. Both figures were measured in a pilot run before the
campaign, which is the standing rule on this project: cost each arm at the
moment it is trained, not at the deployment gate.

### The MAC-count estimate is wrong in the other direction this time

Week 6 established that dividing a multiply count by a measured multiply rate
underestimated the Transformer encoder's real latency by 64%. For this actor
the same arithmetic predicts 0.161 ms against **0.121 ms measured** — it is 25%
*too pessimistic*.

The two are not in conflict. The encoder spends much of its time on softmax
and normalisation, which a MAC count scores at zero, and it moves more data
than stays in fast memory. The actor is 4,800 multiply-accumulates on operands
that stay resident, executed by an FPU that does a multiply and an add
together, so it beats a rate measured on a scalar int8 loop. The estimate is
unreliable **in both directions and by different amounts**, which is a stronger
argument for measuring than a consistent bias would have been.

---

## 4. A test that was passing without testing anything

Building the export chain uncovered a real fault in the parity test that
guards it, and it is worth recording because the failure mode is general.

`firmware/main/actor.c` had `#include "sac_actor_weights.h"`. A *quoted*
include is resolved against the including file's own directory **before** any
`-I` path. The host parity harness generates its own weights into a temporary
directory and compiles `actor.c` against them — but `actor.c` kept picking up
`firmware/main/sac_actor_weights.h` regardless of what the harness put on the
include path.

While no policy had been deployed, that file did not exist, the fallback found
the harness's header, and the test passed honestly. The moment a policy was
deployed, the test began comparing the deployed weights against a different
network's expected outputs — and the geometry check did not catch it, because
every seed produces an identically shaped 8-64-64-3 network.

Two fixes, both kept:

1. `actor.c` now uses `#include <sac_actor_weights.h>`, which searches only
   the include path, so the caller decides which weights are compiled.
2. The weights carry a CRC32 checksum, emitted into the header and **reported
   by `actor.c` itself** rather than by whatever else was compiled alongside
   it. Shape does not identify a network; the checksum does. It is checked by
   the host parity test and again against the board.

`tests/control/test_actor_c_parity.py::test_the_harness_compiled_the_weights_it_generated`
now pins it.

---

## 5. What week 8 settles, and what it does not

Two independent methods now agree that the outer energy-management loop, as
currently scoped, has no headroom worth a learned policy:

- the offline optimum says the best possible policy is a constant instruction;
- SAC, given five seeds and 200,000 steps each, finishes reliably *worse* than
  two thresholds and a taper.

Neither result depends on the other being correct.

This does not decide what to do about it. That is the open item raised in week
7 and still recorded in the spec for the professor: report it as a negative
result, widen the outer loop's authority to eco-driving, or add the thermal
and ageing constraints that would make the power split non-trivial. Week 8
adds evidence to that decision and does not take it.
