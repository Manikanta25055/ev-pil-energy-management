# Dataset provenance

Two datasets, with different jobs. The i3 archive identifies and validates the
plant (gate G2). VED is an independent second source, held for the
cross-dataset generalisation claim in the paper — it is not part of the G2
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
own vehicle model, so validating our plant against it would measure agreement
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
- the encoding is cp1252, not UTF-8 — the degree signs in `[°C]` headers raise
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
| `Battery Current [A]` | `i_batt_a` | **negated** — see below |
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

**Exactly 0.1 s on every one of the 70 files** — minimum, median and maximum
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
| Fleet | 383 personal vehicles, Ann Arbor, Michigan, Nov 2017 – Nov 2018 |
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

### Columns, as documented by the authors

Verified against the repository README before download; re-verified against the
extracted CSVs below.

```
DayNum, VehId, Trip, Timestamp(ms), Latitude[deg], Longitude[deg],
Vehicle Speed[km/h], MAF[g/sec], Engine RPM[RPM], Absolute Load[%],
Outside Air Temperature[DegC], Fuel Rate[L/hr], Air Conditioning Power[kW],
Air Conditioning Power[Watts], Heater Power[Watts], HV Battery Current[A],
HV Battery SOC[%], HV Battery Voltage[V], Short Term Fuel Trim Bank 1[%],
Short Term Fuel Trim Bank 2[%], Long Term Fuel Trim Bank 1[%],
Long Term Fuel Trim Bank 2[%]
```

Each `(VehId, Trip)` pair is one trip. `DayNum` counts days from
1 November 2017, so `DayNum = 1.5` is noon on that day.

### What VED does not have

Three canonical channels are absent, and each has a consequence:

| Missing | Consequence |
|---|---|
| `elevation_m` | No grade signal. Must be recovered by map-matching the GPS trace against a DEM, or the grade term must be zeroed and the resulting bias reported |
| `t_batt_c` | The battery temperature model runs open-loop. Ambient is the only thermal input |
| 10 Hz sampling | VED logs at roughly 1 Hz, so acceleration is a coarser difference and short transients are not resolved |

These are why VED is the secondary and not the primary. Reporting them here
rather than discovering them at review time is the point of this file.

### Observed sample interval

_Pending. To be confirmed from `Timestamp(ms)` when the BEV subset is extracted
for the generalisation experiment; VED plays no part in the G2 verdict._

---

## Reproducing the local data tree

`data/` is git-ignored except for `splits.json` and `i3_params.json`: the
archives are large and redistribution terms are not ours to assume.

```
data/raw/i3/     extracted trip CSVs from Measurement Data.zip
data/raw/ved/    the two .7z parts, the PHEV/EV static sheet, and LICENSE
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
| SoC missing for 12–60% of samples | 4 (TripB07, B09, B28, B34) |
| Trip contains charging (SoC rose +24.1 pp) | 1 (TripB04) |

The rule reproduces the readme's own A/B distinction without being told about
it: every category-A trip fails, and every category-B trip passes unless its
SoC channel dropped out or it contains a charge event. Category B's two heater
channels agree to r ≥ 0.94 and 36–100 W; category A's, where a second channel
exists at all, reach only r = 0.06–0.95 and 112–181 W.

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
the raw signal produces grades up to **1.571 rad** — vertical — on 6 of the 33
eligible trips.

Averaging elevation over a centred window first fixes this, and the window
length was chosen by measurement rather than taste:

| Window | Worst grade across all eligible trips |
|---|---|
| 0.1 s (raw) | 1.571 rad — 6 trips exceed the schema's 0.35 rad bound |
| 5.1 s | 0.602 rad — 1 trip still exceeds it |
| **10.1 s** | **0.298 rad — no trip exceeds it** |
| 20.1 s | 0.156 rad |

10.1 s is the shortest window that brings every trip inside the schema bound on
its own. That matters: the bound then acts as an independent check that passes,
rather than as a clip doing the work silently. Widening to 20 s halves the peak
again, which would begin erasing real short hills — at highway speed 10.1 s is
already a 200 m baseline. Median per-trip peak grade is 0.028 rad (1.6°), which
is what ordinary road driving looks like.

This is not cosmetic. Grade enters road load as `m·g·sin θ`, so at 1270 kg a
0.03 rad slope is 373 N, the same order as rolling resistance.

### Why acceleration is bounded

Nine samples out of 497,538 exceed 5 m/s². The worst is TripB02 at t = 199.2 s,
where speed falls from 9.775 m/s to 0 in a single 0.1 s step while battery
current simultaneously drops from 140 A to 7 A — a bus dropout, not a
manoeuvre. The i3 reaches 100 km/h in 7.2 s (3.9 m/s²) and cannot brake much
past 1 g, so a ±10 m/s² bound is outside anything the vehicle does. It touches
**2 samples in 1 trip**.
