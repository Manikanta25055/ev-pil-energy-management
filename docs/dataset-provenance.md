# Dataset provenance

Two datasets, with different jobs. The i3 archive identifies and validates the
plant (gate G2). VED is an independent second source, held for the
cross-dataset generalisation claim in the paper; it is not part of the G2
verdict.

The split of duties is deliberate. Identifying and validating on the same
vehicle, logger and country answers "does the model fit?" but not "does it
transfer?", and that second question is the one a reviewer asks.

---

## Primary: BMW i3 real driving cycles

| Field | Value |
|---|---|
| Title | Battery and Heating Data in Real Driving Cycles |
| Authors | Matthias Steinstraeter, Johannes Buberger, Dimitar Trifonov |
| Publisher | IEEE DataPort |
| DOI | [10.21227/6jr9-5235](https://dx.doi.org/10.21227/6jr9-5235) |
| Published | 2020-10-19 |
| Access | Open access, but files are behind a free account login |
| Files used | `Measurement Data.zip` (35.69 MB), `readme.txt` |
| Files deliberately NOT used | `Simulation Data.zip` (300.02 MB) |
| Vehicle | BMW i3 (I01), 60 Ah |
| Downloaded | 2026-08-30 |
| Files received | 70 trip CSVs, `Overview.xlsx`, `readin.m`, `readme.txt` |
| Licence | Not stated on the landing page or in `readme.txt`. Listed as Open Access. Redistribution is therefore not assumed: `data/` stays git-ignored |

```bibtex
@data{6jr9-5235-20,
  doi = {10.21227/6jr9-5235},
  url = {https://dx.doi.org/10.21227/6jr9-5235},
  author = {Matthias Steinstraeter and Johannes Buberger and Dimitar Trifonov},
  publisher = {IEEE Dataport},
  title = {Battery and Heating Data in Real Driving Cycles},
  year = {2020}
}
```

`Simulation Data.zip` is excluded on purpose. It is the output of the authors'
own vehicle model, so validating this project's plant against it would measure agreement
between two models rather than agreement with a vehicle. Only measured data
enters the G2 verdict.

### Why this one is the primary

It is the only public archive that carries every channel the plant needs from
one instrumented BEV: speed, battery current and terminal voltage, SoC, ambient
*and* battery temperature, elevation, and the heating-circuit power that the
auxiliary sub-model is fitted against. Substituting any of these with an
assumption would move a fitted parameter into the assumptions column, and the
paper already carries more assumptions there than is comfortable (see the
CAVEATS block in `scripts/identify_params.py`).

### File format, as found

Three things a default `read_csv` gets wrong, all confirmed by reading the raw
bytes rather than by assumption:

- the separator is `;`, not `,`
- the encoding is cp1252, not UTF-8. The degree signs in `[°C]` headers raise
  `UnicodeDecodeError` under UTF-8
- headers carry typos. `TripB38` names its speed column `Velocity [km/h]]]`
  with three closing brackets, and `max. SoC [%)` closes with a parenthesis in
  every file. Two columns named `Temperature Vent right [°C]` differ only by a
  trailing space

All 70 files parse once those three are handled. **None failed to parse.**

### Real column names

The archive does not use one schema. Six distinct header layouts appear across
the 70 files, from 22 to 48 columns:

| Layout | Columns | Files |
|---|---|---|
| 1 | 28 | 12 category-A trips |
| 2 | 23 | 18 category-A trips |
| 3 | 24 | TripA11 (carries an `Unnamed: 23`) |
| 4 | 22 | TripA21 |
| 5 | 48 | 37 category-B trips |
| 6 | 48 | TripB38 (the `Velocity [km/h]]]` typo) |

Twenty-one columns appear in every file. The nine this project consumes are
present in all 70, so the layout differences do not restrict the usable set:

| Source column | Canonical | Conversion |
|---|---|---|
| `Time [s]` | `t_s` | none |
| `Velocity [km/h]` | `v_mps` | ÷ 3.6 |
| `Elevation [m]` | `elevation_m` | none |
| `SoC [%]` | `soc_frac` | × 0.01 |
| `Battery Current [A]` | `i_batt_a` | **negated**, see below |
| `Battery Voltage [V]` | `v_batt_v` | none |
| `Ambient Temperature [°C]` | `t_ambient_c` | none |
| `Battery Temperature [°C]` | `t_batt_c` | none |
| `Heating Power CAN [kW]` + `AirCon Power [kW]` | `p_aux_w` | summed, × 1000 |

`a_mps2` and `grade_rad` are derived, not read, even though the archive
supplies a `Longitudinal Acceleration [m/s^2]` column: the canonical
acceleration must be consistent with the canonical speed, and a logged
accelerometer channel is not.

### Battery current sign convention

**The archive logs discharge as negative.** The canonical schema is
positive-is-discharge, so the loader negates this column. Getting it wrong
inverts every power comparison in the project, so it was established from three
independent checks rather than from the header:

1. Correlation between `Motor Torque [Nm]` and `Battery Current [A]` is
   **−0.84 to −0.90** across trips: positive drive torque draws negative
   current.
2. Correlation between the per-sample SoC change and current is **+0.4 to
   +0.6**: SoC rises when current is positive, which makes positive current
   the charging direction.
3. Trip-mean battery power computed as V·I is **negative on every trip**
   (−4.6 to −9.9 kW), which for a vehicle that starts full and ends emptier
   can only mean the sign is inverted.

Peak magnitudes corroborate it. The negative excursions reach −404 A
(≈ 133 kW at pack voltage, matching the 125 kW rated motor plus transient
overshoot) while the positive ones stop near +144 A, consistent with a regen
ceiling far below drive power.

### Observed sample interval

**Exactly 0.1 s on every one of the 70 files**: minimum, median and maximum
inter-sample gap are all 0.100 s, with no dropped timestamps. The documented
10 Hz rate is confirmed rather than assumed.

### Files that failed to parse

None.

---

## Secondary: VED (Vehicle Energy Dataset)

| Field | Value |
|---|---|
| Title | Vehicle Energy Dataset (VED) |
| Authors | Geunseob Oh, David J. LeBlanc, Huei Peng |
| Venue | IEEE Transactions on Intelligent Transportation Systems, 2020 |
| DOI | [10.1109/TITS.2020.3035596](https://doi.org/10.1109/TITS.2020.3035596) |
| Source | https://github.com/gsoh/VED (branch `master`, directory `Data/`) |
| Access | Public, no credentials |
| Licence | Apache License 2.0 |
| Fleet | 383 personal vehicles, Ann Arbor, Michigan, Nov 2017 to Nov 2018 |
| BEV subset | 3 vehicles, 2013 Nissan Leaf, 24 kWh nameplate |
| Downloaded | 2026-08-30 |

```bibtex
@article{oh2020ved,
  author  = {Oh, Geunseob and LeBlanc, David J. and Peng, Huei},
  title   = {Vehicle Energy Dataset (VED), A Large-Scale Dataset for
             Vehicle Energy Consumption Research},
  journal = {IEEE Transactions on Intelligent Transportation Systems},
  year    = {2020},
  doi     = {10.1109/TITS.2020.3035596}
}
```

### Files taken

- `Data/VED_DynamicData_Part1.7z`
- `Data/VED_DynamicData_Part2.7z`
- `Data/VED_Static_Data_PHEV&EV.xlsx` (saved locally as
  `VED_Static_Data_PHEV_EV.xlsx`; the `&` is awkward in shell paths)
- `LICENSE`

`VED_Static_Data_ICE&HEV.xlsx` is not taken: it describes the gasoline and
hybrid fleet, which this project does not model.

### Columns, as the files actually name them

The repository README documents the ambient channel as
`Outside Air Temperature[DegC]`. **The files call it `OAT[DegC]`.** The loader
uses what the files say. The rest of the README's list is accurate:

```
DayNum, VehId, Trip, Timestamp(ms), Latitude[deg], Longitude[deg],
Vehicle Speed[km/h], MAF[g/sec], Engine RPM[RPM], Absolute Load[%],
OAT[DegC], Fuel Rate[L/hr], Air Conditioning Power[kW],
Air Conditioning Power[Watts], Heater Power[Watts], HV Battery Current[A],
HV Battery SOC[%], HV Battery Voltage[V], Short Term Fuel Trim Bank 1[%],
Short Term Fuel Trim Bank 2[%], Long Term Fuel Trim Bank 1[%],
Long Term Fuel Trim Bank 2[%]
```

Each `(VehId, Trip)` pair is one trip. `DayNum` counts days from
1 November 2017, so `DayNum = 1.5` is noon on that day. Trip identifiers in
this project are `VED_<VehId>_<Trip>`.

The mapping used, all of it read off the files:

| Source column | Canonical | Conversion |
|---|---|---|
| `Timestamp(ms)` | `t_s` | × 0.001, rebased to trip start |
| `Vehicle Speed[km/h]` | `v_mps` | ÷ 3.6 |
| `HV Battery SOC[%]` | `soc_frac` | × 0.01 |
| `HV Battery Current[A]` | `i_batt_a` | **negated** |
| `HV Battery Voltage[V]` | `v_batt_v` | none |
| `OAT[DegC]` | `t_ambient_c` | none |
| `Air Conditioning Power[Watts]` + `Heater Power[Watts]` | `p_aux_w` | summed, already watts |

`Air Conditioning Power[kW]` appears in the header but is empty on every
battery-electric row. The watts column is the populated one.

### The three battery-electric vehicles

`VED_Static_Data_PHEV&EV.xlsx` lists 27 plug-in vehicles, of which
`EngineType == "EV"` selects **VehId 10, 455 and 541**, all 3500 lb class. The
other 24 are plug-in hybrids and the remaining 356 vehicles in the fleet are
gasoline. On BEV rows every channel this project needs is **100% populated**,
which is not true of the fleet as a whole: on a mixed chunk the high-voltage
columns are present on about 9% of rows.

| Vehicle | Trips logged | Eligible |
|---|---|---|
| 455 | 293 | 257 |
| 10 | 201 | 178 |
| 541 | 10 | 8 |

### Battery current sign convention

**Negative is discharge, the same convention as the i3 archive** and the
opposite of the canonical schema, so the loader negates it. Three checks, all
on battery-electric rows:

1. Mean current while driving above 30 km/h is **−20.3 A**.
2. Mean current at rest is **−3.5 A**.
3. Correlation between per-sample SoC change and current is **+0.30**, making
   positive current the charging direction.

Pooled `V·I` over the subset is −5757 W, which for vehicles that start fuller
than they end can only mean the sign is inverted.

### Observed sample interval

**Not the 1 Hz usually quoted, and not regular.** The median gap between
samples is **400 ms**, but the distribution is multi-modal: 39% of samples
arrive less than 250 ms after the previous one and another 32% about a second
after. The 10th to 90th percentile range is 0.10 to 1.00 s.

This matters more than it looks. Differencing speed across a short, jittery
interval is what produces implausible acceleration, not the coarse average
rate: 3.6% of samples taken less than 250 ms apart exceed 5 m/s², against
0.04% of those about a second apart. Raw peaks reach **54 m/s²**. A 2013 Leaf
reaches 100 km/h in about 11.5 s, so 2.4 m/s² is sustained acceleration and
5 m/s² is already hard braking.

The loader bounds acceleration at ±10 m/s² **before** averaging it over a
3-sample centred window, so one dropout stays local instead of being smeared
across its neighbours. That removes 98.5% of the implausible tail (1.80% of
samples above 5 m/s² falls to 0.02%) and brings the spread to 0.83 m/s²,
against the i3 archive's 0.66. Widening to 5 or 7 samples buys almost nothing
beyond that while continuing to erase real dynamics.

### What VED does not have

| Missing | Consequence |
|---|---|
| `elevation_m` | **Recovered from a digital elevation model.** See the section below |
| `t_batt_c` | Falls back to ambient, which is right at key-on and increasingly wrong as the pack self-heats |
| A second heater channel | The i3 logs heater power twice on separate buses, so the two can be required to agree. VED logs each auxiliary channel once, so that instrument check has no counterpart here. A real gap in what can be verified, not an oversight |

### Elevation and gradient, recovered from a DEM

VED logs latitude and longitude but no elevation, so the gradient the road-load
model needs is sampled from a digital elevation model at each GPS fix.

| Field | Value |
|---|---|
| Source | USGS 3D Elevation Program, 1/3 arc-second seamless DEM |
| Tile | `n43w084`, from The National Map staged products |
| Licence | Public domain (a work of the United States Government) |
| Resolution | 0.00009259°, about **10.3 m** |
| CRS | EPSG:4269 (NAD83), geographic, so no reprojection is needed |
| Window kept | 1512 x 1836 cells covering 42.20 to 42.34 N, 83.82 to 83.65 W |
| Valid cells | 100.00% |
| Elevation range | 219.75 to 331.79 m |

`scripts/build_dem.py` reads only that window out of the 421 MB tile using
byte-range requests, so the whole file is never downloaded, and writes an 8.8 MB
array. `evpil.data.dem` then samples it with numpy alone, which keeps the
geospatial stack a build-time dependency rather than a runtime one.

Sampling is **bilinear**, not nearest neighbour. Nearest neighbour makes
elevation a staircase one cell wide, and differentiating a staircase gives a
gradient that is zero almost everywhere and enormous at the risers, which is
the same failure the i3 archive's raw 10 Hz elevation produced.

#### Checks that the sampling is right

Three, because an elevation model that is subtly mis-registered produces
plausible-looking numbers that are quietly wrong.

1. **Landmarks.** Sampled against published elevations: the University of
   Michigan Diag 268.0 m (about 270 m), the Huron River at Argo Dam 235.1 m
   (about 232 m), Ann Arbor Municipal Airport 252.1 m (about 256 m).
2. **Coverage.** 100.0000% of the 476,308 battery-electric GPS fixes fall
   inside the grid.
3. **Loop closure**, the strongest of the three. Nine eligible trips end within
   150 m of where they started, so their net elevation change must be zero.
   Measured: **mean +0.10 m, median −0.18 m, standard deviation 0.78 m**. The
   434 trips that do not return to their start scatter by 16.52 m for contrast.
   A vertical bias or a coordinate offset would not survive this.

#### Why the gradient is measured over 200 m of road

At urban speeds consecutive VED samples are about 4 m apart, well inside a
single 10.3 m DEM cell, so a per-sample difference asks the elevation model for
detail it does not contain. Gradient is therefore taken as the elevation change
across a fixed length of road divided by that length, which is what a road
gradient means. Sweeping the baseline over the eligible trips:

| Baseline | Grade sd | 99th percentile | Max | Steeper than 10% |
|---|---|---|---|---|
| 20 m | 0.0565 | 0.2312 | 1.5708 (vertical) | 5.19% |
| 50 m | 0.0325 | 0.1219 | 0.4404 | 1.89% |
| 100 m | 0.0258 | 0.0823 | 0.2467 | 0.28% |
| **200 m** | **0.0206** | **0.0587** | **0.1479** | **0.05%** |
| 300 m | 0.0181 | 0.0504 | 0.0997 | 0.00% |
| 500 m | 0.0152 | 0.0430 | 0.0649 | 0.00% |

US roads are designed to about 8% and rarely exceed 10%, so 200 m is the
shortest baseline that puts essentially the whole distribution inside what a
road can physically be. That is the same test used to choose the i3 archive's
smoothing window: pick the least smoothing that brings the data inside an
independent physical bound, so the bound stays a check rather than becoming the
thing doing the work. A 300 m baseline would clip the tail completely, at the
cost of averaging one side of the Huron valley against the other; Ann Arbor's
relief runs roughly 100 m over 1 to 2 km.

Distance is integrated from speed rather than taken from the GPS trace. The two
agree closely, with a median ratio of GPS path length to speed-integrated
distance of 0.976 across the 443 eligible trips, but the speed integral is zero
while the vehicle is stopped whereas GPS jitter keeps accumulating distance at
a standstill and would walk the baseline through a parked car.

#### What the gradient is worth

Not a rounding correction. Regressing logged traction power on the road-load
terms across all 458,319 samples, with and without the gradient term:

| | R² | RMSE |
|---|---|---|
| Rolling, aerodynamic and inertial terms | 0.446 | 8362 W |
| The same, plus the DEM gradient | **0.525** | **7741 W** |

Adding it explains **7.9 more points of variance** and cuts RMSE by 7.4%, and
its fitted coefficient is **0.779** against a theoretical 1.0, so it enters
close to the way `m·g·sin θ·v` says it should. A noise channel would fit near
zero and explain nothing. Integrated over the eligible trips, the magnitude of
the gradient power is **27.5%** of the magnitude of traction power: treating
Ann Arbor as flat discards roughly a quarter of the road-load signal.

Two limits remain. The 3DEP model describes bare ground, so it does not know
about bridges, overpasses or multi-level interchanges, where the sampled
elevation is whatever lies beneath the vehicle. And consumer GPS scatters
horizontally by roughly 3 to 5 m under open sky and more between buildings,
which on a slope turns directly into elevation error; the 200 m baseline is
what keeps that from reaching the gradient.

### Trip eligibility

VED fails differently from the i3, so the tests differ. Its battery-electric
channels are fully populated, so there is no missing-data test to run. What
VED has instead is time: a trip is whatever the logger bracketed, and some
brackets contain gaps of twenty minutes. A gap is not a measurement, and
interpolating across one invents driving that did not happen.

| Test | Threshold | Excluded |
|---|---|---|
| Trip duration | at least 120 s | 51 |
| Distance covered | at least 0.5 km | 6 |
| Longest gap in the timestamps | at most 30 s | 4 |
| Sample count | at least 60 | 0 |
| Net SoC change | not rising (no charging) | 0 |

**443 of 504 trips eligible**, 458,319 samples, 2243 km. Median trip is 465 s
and 4.1 km, which is a good deal shorter than the i3's: this is commuter
logging, not instrumented test driving.

### What VED adds that the i3 could not

The i3 eligible set is winter only, so every sample sits below the 21 °C cabin
setpoint and the cooling coefficient of the auxiliary model is unidentifiable.
VED spans **−15.5 °C to +36.0 °C**, with 27.7% of samples above the setpoint,
and closes exactly that gap.

| Auxiliary fit | i3 eligible set | VED battery-electric |
|---|---|---|
| Samples above the 21 °C setpoint | 0.0% | 27.7% |
| `k_heat_w_per_c` | 127.3 | 74.8 |
| `k_cool_w_per_c` | **0.0, unidentified** | **118.3** |
| R² against logged auxiliary power | 0.047 | **0.428** |

The measured load traces the expected V-shape about the setpoint: 2005 W below
freezing, 143 W between 10 and 21 °C, and back up to 820 W above 28 °C. The
i3's own fit is nearly worthless at R² = 0.047 because it only ever sees one
arm of that V.

Two cautions before this is used. The coefficients are a Nissan Leaf's, not a
BMW i3's, so they transfer as an order of magnitude and a shape rather than as
a calibration. And R² = 0.428 still leaves most of the variance unexplained,
because cabin heating depends on what the driver asked for and on how cold the
cabin started, neither of which ambient temperature reveals.

---

## Reproducing the local data tree

`data/` is git-ignored except for `splits.json` and `i3_params.json`: the
archives are large and redistribution terms are not ours to assume.

```
data/raw/i3/     extracted trip CSVs from Measurement Data.zip
data/raw/ved/    the two .7z parts, the PHEV/EV static sheet, and LICENSE
data/raw/ved/csv/  the 54 weekly files, extracted
data/raw/dem/    the 3DEP window, as GeoTIFF and as a numpy array
```

---

## Trip eligibility

The archive's `readme.txt` states that category A (summer) "does not contain
all measured data due to trouble with the measurement system", while category B
(winter) "is consistent". Acting on that warning by eye would make the G2
verdict unreproducible, so it is expressed as four mechanical tests in
`src/evpil/data/eligibility.py`, applied to every trip before any model is
fitted.

Fixing the rule before fitting is the point. Selecting trips after seeing which
ones the plant reproduces well would make the gate meaningless.

| Test | Threshold | Rationale |
|---|---|---|
| SoC channel present | ≥ 99% of samples | A trip missing a third of its SoC cannot support a terminal-SoC error criterion |
| Net SoC change | ≤ 0 pp | A rising SoC means the trip contains charging, which the plant does not model |
| Heater CAN vs LIN correlation | r ≥ 0.90 | The heater is measured twice on separate buses. Requiring the two to agree is an instrument check, not a model check |
| Heater CAN vs LIN difference | MAE ≤ 100 W | Catches channels that track in shape but are biased in level |

### Result: 33 of 70 trips eligible

| Reason | Trips |
|---|---|
| **Eligible** | **33** |
| Heater has no independent LIN channel to corroborate it | 26 (all category A) |
| Heater CAN and LIN disagree | 6 (TripA23, A24, A25, A28, A31, A32) |
| SoC missing for 12 to 60% of samples | 4 (TripB07, B09, B28, B34) |
| Trip contains charging (SoC rose +24.1 pp) | 1 (TripB04) |

The rule reproduces the readme's own A/B distinction without being told about
it: every category-A trip fails, and every category-B trip passes unless its
SoC channel dropped out or it contains a charge event. Category B's two heater
channels agree to r at least 0.94 and 36 to 100 W; category A's, where a second channel
exists at all, reach only r = 0.06 to 0.95 and 112 to 181 W.

### What excluding category A costs

This is a real restriction and it is stated rather than buried.

- **The validated envelope is winter only.** Eligible trips span −3.3 °C to
  +10.2 °C mean ambient. Nothing above 14 °C survives.
- **The cooling branch of the auxiliary model is unidentified.** Every eligible
  sample sits below the 21 °C cabin setpoint, so the cooling column of the
  design matrix in `fit_auxiliary` is identically zero and `k_cool_w_per_c`
  comes back as 0. The plant must not be applied above the setpoint without
  first identifying that coefficient on data that contains it.
- **Sample count is not the problem.** 33 trips at 10 Hz is 497,538 rows, which
  splits 19/7/7 with the temperature stratification intact.

The restriction cuts the way that favours the project rather than flattering
it: winter is when HVAC load is largest, range loss is worst, and predictive
energy management matters most. It is the harder half of the archive, not the
easier one.

---

## Signal handling applied at load

Every adjustment below is declared as a `Dialect` in
`src/evpil/data/i3_loader.py` rather than buried in branching code, so what was
done to the raw file can be read in one place.

| Adjustment | Value | Why |
|---|---|---|
| Battery current sign | negated | Archive convention is discharge-negative (evidence above) |
| `p_aux_w` composition | heater + AC, ×1000 | The canonical signal is total auxiliary electrical load; the archive splits it across two kW channels |
| `p_aux_w` clip | [0, 10 000] W | The i3's PTC heater is ~6 kW and its compressor ~3 kW. TripB02 carries a single 40 kW spike whose trip-mean still agrees with the LIN channel, so it is one bad sample, not a bad trip |
| SoC gap fill | interpolate, ≤ 100 samples | Eligible trips have at most 13 missing samples (1.3 s) before the first SoC frame appears on the bus. Longer gaps are left as NaN so the schema validator rejects the trip |
| Grade window | 101 samples (10.1 s), centred | See below |
| Grade speed floor | 2.0 m/s | Below this, `v·dt` is a few centimetres and divides a real elevation change by near-zero |
| Acceleration bound | ±10 m/s² | See below |

### Why grade needs a 10 second baseline

Road gradient does not change in 0.1 s, but differentiating the raw 10 Hz
elevation channel behaves as if it does. At 0.6 m/s the vehicle covers 6 cm per
sample, so a decimetre of elevation noise becomes a 90° slope. Differentiating
the raw signal produces grades up to **1.571 rad**, vertical, on 6 of the 33
eligible trips.

Averaging elevation over a centred window first fixes this, and the window
length was chosen by measurement rather than taste:

| Window | Worst grade across all eligible trips |
|---|---|
| 0.1 s (raw) | 1.571 rad, 6 trips exceed the schema's 0.35 rad bound |
| 5.1 s | 0.602 rad, 1 trip still exceeds it |
| **10.1 s** | **0.298 rad, no trip exceeds it** |
| 20.1 s | 0.156 rad |

10.1 s is the shortest window that brings every trip inside the schema bound on
its own. That matters: the bound then acts as an independent check that passes,
rather than as a clip doing the work silently. Widening to 20 s halves the peak
again, which would begin erasing real short hills. At highway speed 10.1 s is
already a 200 m baseline. Median per-trip peak grade is 0.028 rad (1.6°), which
is what ordinary road driving looks like.

This is not cosmetic. Grade enters road load as `m·g·sin θ`, so at 1270 kg a
0.03 rad slope is 373 N, the same order as rolling resistance.

### Why acceleration is bounded

Nine samples out of 497,538 exceed 5 m/s². The worst is TripB02 at t = 199.2 s,
where speed falls from 9.775 m/s to 0 in a single 0.1 s step while battery
current simultaneously drops from 140 A to 7 A, a bus dropout, not a
manoeuvre. The i3 reaches 100 km/h in 7.2 s (3.9 m/s²) and cannot brake much
past 1 g, so a ±10 m/s² bound is outside anything the vehicle does. It touches
**2 samples in 1 trip**.
