# Cross-dataset generalisation: the i3 plant against VED

**Verdict: the powertrain transfers, the chassis parameters do not, and the
residual is thermal.** Terminal SoC transfers well enough to use. Trip energy
does not transfer without substituting the target vehicle's own road load.

Measured 2026-08-30 on 89 held-out VED trips. The 89 VED test trips stay
sealed, as do the i3 test trips.

## What is being asked

G2 showed the plant reproduces held-out trips from the vehicle it was
identified on, which answers "does it fit?". A plant is used in Phase 3 as the
environment a policy trains inside, so the question that matters is "does it
transfer?". Nothing in G2 addresses that: same vehicle, same logger, same
country, same instrumentation.

The i3 plant was therefore rebuilt around a 2013 Nissan Leaf and run against
VED. Three arms, so that a failure can be attributed rather than merely
observed.

| Arm | Chassis | Powertrain | Battery | Under test |
|---|---|---|---|---|
| **A transfer** | i3-identified `c_rr`, `cd` | i3 efficiency map, i3 `rot_mass_factor`, i3 `r0` | Leaf, measured | everything at once |
| **B measured chassis** | Leaf's own coastdown [L1] | i3 efficiency map, i3 `rot_mass_factor` | Leaf, measured | the powertrain alone |
| **C re-identified** | fitted on VED training trips | i3 efficiency map | Leaf, measured | nothing: the ceiling |

Arm C is the control. It bounds how much of any error in A and B is the two
vehicles differing rather than the method failing.

## Result

| Arm | Trip energy, median | Energy bias | SoC, median | SoC within 2 pp |
|---|---|---|---|---|
| A transfer | 16.9% | **+14.6%** | 1.45 pp | 55 / 89 |
| B measured chassis | 14.4% | −9.0% | 0.99 pp | 64 / 89 |
| **C re-identified** | **13.4%** | −4.0% | **0.89 pp** | **67 / 89** |

Transferring everything costs **3.5 points of energy error** over identifying
in-domain, and 12 trips of the SoC criterion. Substituting the Leaf's own
measured road load recovers most of both: 2.5 of the 3.5 points, and 9 of the
12 trips.

## Instantaneous power cannot be scored on this dataset

The instantaneous figure is 96 to 104% of mean absolute power for every arm,
which looks catastrophic and means nothing. The floor was measured before
concluding anything from it.

Fitting each trip's observed power onto the road-load basis functions by
unconstrained least squares, with the coefficients free to be unphysical, no
model built from these signals can do better than the residual that leaves.
That floor is **77.7% of mean absolute power**. The i3's equivalent floor, with
that vehicle's own logged motor torque, was 7.0%.

The cause is in the sampling. VED's speed channel changes value about once per
second, so acceleration derived from it has a standard deviation of
0.82 m/s². At 1573 kg and 10 m/s that is **15.1 kW of inertial swing against a
9.7 kW mean signal**: the noise is larger than the thing being measured. Arm
C's fit puts this beyond doubt by driving `rot_mass_factor` to zero, its lower
bound, since deleting the inertial term outright beats including it.

G2 reached the same conclusion about the i3 for the same reason and set the
gate on energy and SoC instead. That decision carries over here, more strongly.

## What transfers

**The powertrain does.** Arm B keeps the i3's identified efficiency map and
rotational mass factor, changes only the chassis, and lands within 1.0 point of
the in-domain ceiling on energy and within 3 trips of it on SoC. An efficiency
map identified from one vehicle's logged torque describes the other well enough
to be worth carrying.

**The chassis parameters do not.** The i3's identified `c_rr` is **0.01947**.
The Leaf's rolling resistance, from the coastdown in [L1], is **0.00878**. A
factor of 2.2. That gap is not a Leaf-versus-i3 difference in tyres; it is that
the i3's fitted `c_rr` was never a rolling resistance. It is a lumped constant
loss term that absorbed drivetrain drag, bearing losses and whatever else the
model had no other home for, and calling it `c_rr` invited exactly the mistake
Arm A makes. Carried across, it over-predicts energy by 14.6%.

This is worth stating plainly in the paper. A parameter identified by fitting
is named after the physics it stands in for, not the physics it contains.

## What no arm fixes

Energy error slopes with ambient temperature in every arm, including the one
fitted on VED itself:

| Ambient | A transfer | B measured chassis | C re-identified |
|---|---|---|---|
| −20 to 0 °C | −1.9% | −21.9% | −15.8% |
| 0 to 12 °C | +13.0% | −13.5% | −6.5% |
| 12 to 24 °C | +31.3% | +3.1% | +10.5% |
| 24 to 40 °C | +40.9% | +10.1% | +15.6% |

A fixed parameter set cannot track it, which is why Arm C slopes too. The
arithmetic says where it comes from: VED's cold trips consume **239 Wh/km** and
its warm trips **133 Wh/km**, a 106 Wh/km penalty, but the logged auxiliary
channel accounts for only about 2 kW of the roughly 3.2 kW that penalty
implies. The missing kilowatt is battery heating, colder and stiffer tyres,
thicker driveline oil and a less efficient pack, none of which a plant with
temperature-independent `c_rr`, `r0` and drivetrain efficiency represents.

Arm A's slope is steepest because two errors happen to cancel at the cold end:
its inflated `c_rr` over-predicts everywhere, and the missing cold-weather load
under-predicts in the cold, and near 0 °C they meet. A model that is right for
compensating reasons is not right, and the middle column shows what happens
when only one of the two errors is removed.

## Limitations

- **Three vehicles, one city.** VED's battery-electric subset is 3 cars in Ann
  Arbor. Transfer to a Leaf is not transfer to any BEV.
- **The vehicles are not the one that was coastdown-tested.** [L1] describes a
  2013 Leaf SV; VED identifies its cars only as `EngineType` "EV" in a 3500 lb
  class. The coastdown describes the model, not the unit, and these particular
  packs Coulomb-count to 42 Ah against a 66.2 Ah nameplate, so they are not new.
- **No battery temperature channel**, so the pack thermal model runs on
  ambient. In a Michigan January that is wrong toward an optimistically warm
  pack, which is the direction that flatters the model.
- **Short trips.** Median 4.1 km. Energy error on a short trip is sensitive to
  its endpoints, and the 13.4% in-domain floor partly reflects that rather than
  the plant.

## What this changes downstream

Two things, both concrete.

The first is a naming and reporting fix: `c_rr` and `cd` as identified in
`data/i3_params.json` are lumped loss coefficients, not physical properties,
and the paper must not present them as measurements of rolling resistance or
drag. The Leaf coastdown gives an independent number to say so against.

The second is for Phase 3. G2 already recommended representing trip-to-trip
road-load variation as environment randomisation rather than a fixed parameter
set. This strengthens that and widens it: the spread that matters is not only
between trips in one vehicle but between vehicles, and it is temperature
dependent. A policy trained against one fixed road load at one temperature has
learned something narrower than it appears to have learned.

## Figures

- `figures/ved-generalisation.png`: energy error by arm, terminal SoC against
  the 2 pp criterion, and the temperature slope no arm removes

## Reproducing

```bash
PYTHONPATH="src:." python3 scripts/validate_ved.py
PYTHONPATH="src:." python3 scripts/plot_ved.py
```

Per-arm summaries are in `docs/ved-generalisation.csv`, per-trip results in
`docs/ved-per-trip.csv`, and the frozen VED split in `data/ved_splits.json`.
Leaf parameters and their sources are in `src/evpil/plant/leaf.py`.

[L1] Idaho National Laboratory / Intertek for the U.S. Department of Energy,
"2013 Nissan Leaf, Advanced Vehicle Testing, Baseline Testing Results",
Vehicle Technologies Program.
