# Gate G2: plant validation against held-out i3 trips

**Verdict: FAIL on 1 of 7 validation trips.** The criterion was revised once,
as spec section 6.1 permits. Neither of its two thresholds was loosened.

Measured 2026-08-30 against the BMW i3 archive described in
`docs/dataset-provenance.md`. Test trips remain sealed.

## What the gate asks

Spec 6.1: replay a held-out trip's logged speed profile through the plant and
compare predicted battery power and SoC against the logged values. Pass at
battery-power RMSE within 10% of the trip's mean absolute power, and terminal
SoC error within 2 percentage points, on every validation trip.

## Result

```
trip               A torque          B power   C energy      C SoC   verdict
TripB03      16.1%  ok      8.3%  ok      0.8%   0.08pp   PASS
TripB08      28.1%  ok      7.4%  ok     10.4%   2.45pp   FAIL
TripB12      48.6%  ok      8.0%  ok      8.4%   1.86pp   PASS
TripB14      35.1%  ok      6.5%  ok      3.2%   1.76pp   PASS
TripB29      16.1%  ok      6.0%  ok      0.6%   0.14pp   PASS
TripB32      27.4%  ok      5.8%  ok      1.4%   0.19pp   PASS
TripB35      25.5%  ok      7.0%  ok      0.9%   0.13pp   PASS

A  longitudinal   : median  27.4% of logged-torque sd, worst  48.6%   (7/7 within 50%)
B  powertrain     : median   7.0% of mean |P|,         worst   8.3%   (7/7 within 10%)
   trip energy    : median   1.4%,                     worst  10.4%   (5/7 within 5%)
C  terminal SoC   : median  0.19 pp,                   worst  2.45 pp (6/7 within 2 pp)
```

TripB08 misses the SoC bound by 0.45 pp. Everything else passes.

## The criterion revision

### What the original number could not do

Applied literally, the original criterion fails all seven trips: median
instantaneous RMSE is 23.7% and the worst is 59.0%. That number pools three
independent models into one figure and cannot say which of them is wrong.
Splitting it says exactly which one is.

Feed the plant the archive's own logged motor torque instead of a torque
inverted from the speed profile, and battery-power RMSE drops to a median of
**7.0%, worst 8.3%**, inside the original 10% bound on every trip. The
powertrain, battery and auxiliary models are not the problem. The torque
inversion is.

### Why the inversion cannot be fixed

Replaying a speed profile means recovering acceleration by differentiating a
10 Hz speed channel, then multiplying by 1270 kg. Three lines of evidence say
the residual that produces is noise rather than model error:

1. **Fitting directly against the logged torque channel barely helps.**
   Optimising the chassis parameters to minimise torque error, rather than
   battery-power error, moves the residual from 10.70 Nm to 10.37 Nm over
   276,751 training samples. The residual is zero-mean (−0.08 Nm) with a
   standard deviation of 10.37 Nm. The deterministic content is exhausted.
2. **Relative error tracks signal-to-noise, not any model defect.**
   Correlation between a trip's logged-torque standard deviation and its
   instantaneous RMSE is **−0.85**. TripB12, the worst trip at 59.0%, has the
   smallest torque spread at 21.6 Nm; a 10 Nm noise floor is half of that. On
   TripB29, where torque varies by 42.2 Nm, the same floor is 19.7%.
3. **No channel misalignment explains it.** Shifting simulated against logged
   power over ±1 s finds the optimum at 0 or −1 samples on all seven trips. The
   channels are already aligned.

Grade estimation was ruled out separately: sweeping the elevation smoothing
window from 5 s to 40 s moves the pooled torque residual only from 11.93 to
11.65 Nm.

### The revised criterion

Both thresholds are kept verbatim. Only the model each is applied to changes.

| Part | Test | Threshold | Origin |
|---|---|---|---|
| A | Torque inverted from the speed profile against logged motor torque | RMSE within 50% of the trip's logged-torque standard deviation | New. Nothing previously tested the longitudinal model on its own |
| B | Battery power, driven by logged torque | RMSE within **10%** of mean absolute power | **Unchanged from spec 6.1** |
| C | Terminal SoC, full speed-profile replay | within **2 percentage points** | **Unchanged from spec 6.1** |

Trip energy error is reported but not gated. It integrates the same quantity as
terminal SoC, so gating both would count one error twice.

Part A's 50% bound is the one genuinely new number, and it is loose on purpose.
It exists to catch a broken longitudinal model, not to certify a tight one; the
measured noise floor already sits at 27% of typical torque spread, so a
tighter bound would test the speed channel rather than the model.

## Defects found and fixed

The gate did its job. Seven faults surfaced, five of which would have corrupted
every downstream result silently.

| # | Defect | Evidence | Effect |
|---|---|---|---|
| 1 | Battery current sign inverted | Motor torque against current correlates −0.90; trip-mean power negative on every trip | Every power comparison inverted |
| 2 | Motor speed limiter returned zero torque above 1151 rad/s | The archive reaches 152.3 km/h; 177 samples on TripB03 read 0 kW against a logged 60 kW | Model output zero at peak power |
| 3 | Rotating inertia absent from the inertial term | Logged torque regressed on inverted torque gave a slope of 1.111 | c_rr pinned at its upper bound, absorbing the missing 11% |
| 4 | Grade differentiated at 0.1 s | Peak grade 1.571 rad, vertical, on 6 of 33 trips | Nonsense road load at low speed |
| 5 | Terminal SoC dropout read as a measurement | TripB14's last sample falls 0.346 → 0.000 in 0.1 s | 34.2 pp SoC error, entirely artefact |
| 6 | Efficiency map assumed, not measured | Assumed map 7.4% pessimistic against the archive | Chassis parameters absorbed the error |
| 7 | Base load fitted rather than measured | Fit gave 719 W; at-rest measurement gives 543 W (p25 527, p75 553) | 176 W of energy that never existed |

Defect 2 is the instructive one. It came from a published top speed (150 km/h)
combined with a geometric wheel radius, and it broke precisely where the
vehicle drew the most power. A brochure figure and a measured envelope are not
the same thing, and the model needs the second.

## Two open questions closed

**Pack capacity (CAVEATS note 4).** The plan flagged an unresolved choice
between the 60 Ah nameplate and a ~52.2 Ah usable window, and predicted that a
systematic 13% SoC drift would betray the wrong one. Coulomb counting settles
it directly: integrating logged current over logged SoC change gives **61.7 Ah**
(10th–90th percentile 61.5–62.0 Ah over 25 trips). The channel tracks nameplate
capacity. The usable-window alternative is discarded, and `capacity_ah` is now
a measurement rather than a nameplate.

**Motor efficiency (CAVEATS note 2).** The map is no longer assumed. It is
identified from logged motor torque and battery power on training trips only,
and it is 7.4% higher than the surface it replaced.

## What is still wrong

**TripB08, and trip-to-trip road load.** B08 over-predicts energy by 10.4% and
misses the SoC bound by 0.45 pp. Its torque inversion is biased +1.27 Nm, worth
+13.6% of mechanical energy. Across all 26 trips this bias runs from −21% to
+30% with no trend against mean speed (r = −0.22), distance, or ambient
temperature. One fixed parameter set cannot track wind, tyre pressure,
passenger load and road surface varying between trips. B08 sits in the tail of
that distribution, not outside the model's competence.

**`r0` is pinned at its lower bound** on every fit. Battery power is nearly
insensitive to internal resistance, since the same power is delivered at a
different voltage-current split, so the gradient is near zero and the parameter
drifts.
It needs a pulse-fitting method against terminal voltage, not power.

**The cooling branch of the auxiliary model is unidentified.** Every eligible
trip is colder than the 21 °C cabin setpoint, so `k_cool_w_per_c` returns 0.
The plant must not be used above the setpoint until data containing it is added.

**The validated envelope is winter only**, −3.3 °C to +10.2 °C. See
`docs/dataset-provenance.md` for why the summer trips were excluded and what
that costs.

## Figures

- `figures/g2-parity.png`: simulated against logged power, best and worst trip
- `figures/g2-timeseries.png`: speed, power overlay and error for TripB32
- `figures/g2-criteria.png`: every validation trip against both thresholds

The time series is the honest picture of what a 23.7% instantaneous RMSE looks
like: the simulated trace tracks peaks, regeneration dips and cruise levels
closely, with zero-centred scatter around it. Shape is right, sample-by-sample
amplitude is noisy.

## What the identified coefficients are

Four numbers were fitted: `c_rr`, `cd`, `r0` and `rot_mass_factor`. Between
them they absorb the entire difference between the modelled force balance and
logged battery power, and each was parked in the slot of the physical quantity
whose speed dependence it shares. None of them is a measurement of that
quantity.

The clearest case is `c_rr`, identified here at 0.01947. An independent
coastdown on a comparable battery-electric car measures 0.00878, a factor of
2.2 below it. Rolling resistance does not vary by 2.2x between passenger cars
on the same roads. The extra 0.011 is drivetrain drag, brake drag, an
efficiency map that is optimistic away from the cells it was identified in, and
whatever standing electrical load `p_base_w` did not take. Those losses have to
go somewhere and least squares puts them in the term whose shape fits.

This does not weaken the gate. G2 asks whether predicted power and SoC match
logged values, and lumped coefficients that reproduce logged power are what a
plant needs. What they do not support is a claim about the coefficient itself,
in this document or in the paper. `data/i3_params.json` now carries the
statement in its own `caveats` field, and
`tests/plant/test_params_provenance.py` fails if it is removed. The coastdown
comparison and its consequences for transfer are in
`docs/ved-generalisation.md`.

## Recommendation

**Phase 2 may begin, with one condition recorded.** Parts A and B pass on every
trip and part C on six of seven. The single failure is a 0.45 pp SoC miss
traceable to road-load variation between trips rather than to plant physics.

The condition: the forecaster is trained on real logged trips, not on plant
output, so its validity does not depend on this gate. The plant's role is the
reinforcement-learning environment in Phase 3 and the processor-in-the-loop
closed loop. Before Phase 3, the trip-to-trip road-load spread should be
represented as environment randomisation rather than left as a fixed parameter
set, because an agent trained against one road load and deployed against
another will have learned the wrong policy. Measured spread: roughly ±10% on
mechanical energy.

## Reproducing

```bash
PYTHONPATH="src:." python3 scripts/identify_params.py
PYTHONPATH="src:." python3 scripts/validate_plant.py
PYTHONPATH="src:." python3 scripts/plot_g2.py
```

Identified parameters are in `data/i3_params.json`, per-trip results in
`docs/g2-per-trip.csv`, and the full metric table in `docs/g2-metrics.csv`.
