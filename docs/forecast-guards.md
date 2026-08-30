# Guards and baselines, run before any forecaster is trained

Spec 6.4 lists three checks that have to happen before a model is fitted, and
spec 8.2 sets gate G4 as a percentage below a baseline. This document reports
all three checks and the baseline they are stated against.

Measured 2026-08-31 on the BMW i3 archive, 19 training and 7 validation trips
from `data/splits.json`. Test trips remain sealed.

Windows are 32 input samples (3.2 s at 10 Hz) predicting 30 future samples
(3.0 s), the configuration G1 sized against the measured 29.82 MMAC/s. Stride 5
gives 55,125 training and 29,252 validation windows.

## Guard 1: leakage audit

Three things were checked, each against the tensors rather than against the
intent that produced them.

| Check | Result |
|---|---|
| Target absent from the feature channels | `p_batt_w` is not one of the 8 inputs |
| No trip on both sides of a split | Checked on the group label attached to every window |
| Inputs disjoint from targets | Inputs end at sample 32, targets start at 33 |

The second is the direct fix for the predecessor work's row-level splitting.
Checking `data/splits.json` would confirm what was intended; checking the group
labels carried by the windows confirms what was built, and those are not the
same claim. `evpil.data.guards.assert_disjoint_groups` is what makes it.

The third deserves a note, because battery power is terminal voltage times
current and both channels are inputs. That is not a leak: the model sees
current and voltage up to sample 32 and is asked about power from sample 33
onward, which is the forecasting problem as stated. It would become a leak the
moment a window's inputs and targets shared a sample, so the window geometry
enforces the gap and `tests/forecast/test_windows.py` asserts it holds on the
sample index rather than on a comment.

## Guard 2: shuffled-label control

Ridge regression on flattened windows, 257 parameters, trained twice.

```
ridge on real labels      R^2 = +0.4018
ridge on shuffled labels  R^2 = -0.0044
```

The shuffled run collapses to chance, which is what an honest pipeline does.

The real-label run is reported alongside for a reason. A shuffled-label control
on a pipeline that cannot learn anything returns zero as well, and returns it
for a reason that has nothing to do with leakage. The control only carries
information when the same wiring demonstrably learns from unshuffled labels,
and this one does.

The learner is deliberately weak. A leak is a property of the wiring, so a
linear map is enough to find one, and cheap enough to re-run on every change to
the data path.

## Guard 3: persistence baseline

Persistence predicts that battery power stays at its last observed value.
Validation windows, per horizon step, never pooled across the horizon.

| Step | Seconds | Persistence RMSE | Drift RMSE | Persistence R^2 |
|---|---|---|---|---|
| 1 | 0.1 | 0.863 kW | 0.589 kW | 0.9965 |
| 5 | 0.5 | 3.878 kW | 3.633 kW | 0.9296 |
| 10 | 1.0 | 6.814 kW | 8.076 kW | 0.7828 |
| 20 | 2.0 | 10.787 kW | 17.300 kW | 0.4556 |
| 30 | 3.0 | 13.219 kW | 26.172 kW | 0.1826 |

Mean absolute target power over the same windows is 10.8 kW, so at 3.0 s
persistence errs by more than the signal's own average magnitude. That is what
makes the horizon worth predicting.

Bootstrapping over trips rather than windows, persistence at 3.0 s is
13.219 kW with a 95% interval of [10.594, 16.463] kW. Per trip it ranges from
7.441 kW on TripB12 to 19.422 kW on TripB32. Consecutive windows overlap by 27
of 32 samples and come from the same driver on the same road, so resampling
windows would have produced a far narrower interval describing nothing.

**Drift is worse than persistence beyond about half a second**, and twice as
bad by 3.0 s, its R^2 crossing zero at 1.8 s. Extrapolating the recent slope of battery power is actively
harmful: the signal reverts rather than continues, because throttle and brake
inputs are the thing being predicted and they do not trend. This is a small
result but a useful one, since linear extrapolation is the first thing anyone
reaches for.

Ten percent below persistence at 3.0 s puts the G4 bar at **11.897 kW**.

## What the bar is worth

The same 257-parameter ridge, now scored across the full horizon.

| Step | Seconds | Ridge RMSE | Skill over persistence | Ridge R^2 |
|---|---|---|---|---|
| 1 | 0.1 | 0.842 kW | 2.5% | 0.9967 |
| 5 | 0.5 | 2.617 kW | 32.5% | 0.9680 |
| 10 | 1.0 | 5.425 kW | 20.4% | 0.8623 |
| 20 | 2.0 | 9.296 kW | 13.8% | 0.5957 |
| 30 | 3.0 | 11.308 kW | 14.5% | 0.4018 |

**G4 is already passed, by a linear map fitted in one matrix solve.** 14.5%
against a required 10.0%.

This is worth knowing now rather than in Week 4. As written, G4 asks whether
some model beats persistence by 10%, and the answer is yes before any of the
proposed models exist. A Transformer that clears the same bar will have
demonstrated nothing a linear regression did not, and reporting it as a passed
gate would overstate what was tested.

Two consequences.

The first is a reporting one and is not optional: every model in the comparison
is reported against the ridge as well as against persistence. The ridge costs
one solve, so there is no argument for leaving it out, and its presence is what
converts "beats the naive baseline" into a statement with content.

The second is a recommendation to be decided at G4 rather than here. The
useful form of the gate is skill over the *strongest cheap baseline*, not over
the naive one. Restating it as 10% over the ridge would put the bar at
10.177 kW at 3.0 s. That is a change to a gate threshold and belongs in the
spec with a recorded reason, not in a results document, so it is raised here
and left open.

Note also the shape of the ridge's skill curve: it peaks at 0.3 s (37.8%),
falls to a trough at 2.2 s (13.7%), then recovers slightly. Nothing in the
horizon is uniformly easy or uniformly hard, which is the argument for spec
6.2's insistence on per-step reporting. A single pooled number would have shown
none of this.

## Limitations

- **Validation only.** Test trips are sealed and these numbers do not touch
  them. Nothing here may be quoted as a test result.
- **Stride 5.** Windows are sampled every 0.5 s rather than every 0.1 s, to
  keep the tensors inside 8 GB. Denser striding adds overlapping and highly
  correlated windows, so it would raise the count without adding much
  evidence, but the baseline numbers would shift slightly.
- **The ridge is not tuned.** One ridge coefficient, no feature engineering,
  no validation sweep. It is a floor, and a tuned tabular model will sit above
  it. That direction makes the point stronger, not weaker.
- **Seven validation trips.** The bootstrap interval on persistence spans
  10.6 to 16.5 kW, which is wide because seven trips is few. Any claimed
  improvement smaller than that spread needs the per-trip table, not the mean.

## Figures

- `figures/forecast-guards.png`: RMSE and R^2 against horizon for all three
  arms, and the ridge's skill over persistence against the G4 bar

## Reproducing

```bash
PYTHONPATH="src:." python3 scripts/run_guards.py
PYTHONPATH="src:." python3 scripts/plot_guards.py
```

Per-step numbers for all three arms are in `docs/forecast-baselines.csv`.
Window construction is `src/evpil/forecast/windows.py`, the baselines are
`src/evpil/forecast/baselines.py`, and the metrics are
`src/evpil/forecast/metrics.py`.
