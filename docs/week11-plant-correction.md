# Correction: the power ceiling did not limit the vehicle

**Date:** 2026-10-06
**Fix:** commit `82ca2fe`, `src/evpil/plant/plant.py`
**Data:** `docs/week11-plant-correction.json`, from
`scripts/run_plant_correction.py`, which runs the pre-fix plant out of the
repository history beside the corrected one
**Tests:** `tests/plant/test_plant.py`, four new cases
**Withdraws:** the energy result of `docs/week10-pil-campaign.md` sections 6.2
to 6.4, the matching paragraph of `docs/hardware-pending.md`, and the
"Does it reproduce?" headline of the repeat campaign.

## 1. What was wrong

`Plant.step` capped the battery power it billed at `p_limit_w`, and at the
pack's current limit, but computed acceleration from the torque before either
cap. A binding ceiling therefore reduced the energy charged and left the
vehicle's motion untouched.

SIMULATED on the plant as it stood before the fix, constant ceiling,
regeneration fully on, US06, starting charge 0.80, ambient 12 degC:

| Ceiling | Wh/km | Distance | Tracking RMSE |
|---|---|---|---|
| 250 kW | 190.39 | 12.888 km | 0.0013 m/s |
| 80 kW | 189.85 | 12.888 km | 0.0013 m/s |
| 60 kW | 187.31 | 12.888 km | 0.0013 m/s |
| 40 kW | 174.85 | 12.888 km | 0.0013 m/s |
| 20 kW | 114.68 | 12.888 km | 0.0013 m/s |
| 5 kW | 8.05 | 12.888 km | 0.0013 m/s |

A 5 kW ceiling drove the whole of US06, to the metre, on 8 Wh/km.

## 2. Why this is the week-10 result

The learned controller's action space puts the ceiling between 40 kW and
125 kW. On the chip it scored 176.4 Wh/km on US06 against 190.6 for the rules,
at the same distance and the same tracking error. A constant 40 kW ceiling on
the old plant scores 174.85, and the deployed actor simulated on the old plant
scores 176.71.

Three things in the campaign's own tables were pointing at this:

- The actor finished **below the dynamic-programming optimum** (190.39), at
  equal tracking. An optimum is not something a controller beats by 7%.
- The advantage grew with demand on three independent axes (aggression,
  grade, cycle), which is where the ceiling binds for longest.
- It vanished on HWFET and UDDS, where demand stays under the 40 kW floor and
  the ceiling cannot bind at all.

Section 6.4 of the campaign note read the same three facts as peak-current
shaving. That explanation was labelled inferred, and it was wrong.

## 3. The fix

Traction receives what the pack actually delivered, less the auxiliary load;
the torque is reduced to match and acceleration is computed from the reduced
torque. The auxiliary load is served first. A limit that does not bind leaves
every output bit-identical, which a test asserts.

## 4. What the corrected plant says

SIMULATED, same conditions as section 1:

| Cycle | Controller | Wh/km | Distance | Tracking RMSE | Worst error |
|---|---|---|---|---|---|
| US06 | always-regen, 250 kW | 190.39 | 12.888 km | 0.0013 m/s | 0.017 m/s |
| US06 | always-regen, 60 kW | 190.31 | 12.886 km | 0.0687 m/s | 1.158 m/s |
| US06 | always-regen, 40 kW | 189.80 | 12.815 km | 0.5157 m/s | 3.751 m/s |
| US06 | always-regen, 20 kW | 180.57 | 11.845 km | 2.9224 m/s | 9.464 m/s |
| US06 | always-regen, 5 kW | 156.16 | 4.453 km | 16.1464 m/s | 25.647 m/s |
| US06 | rules | 190.47 | 12.888 km | 0.0013 m/s | 0.017 m/s |
| US06 | deployed actor (seed 3) | 190.71 | 12.824 km | 0.4815 m/s | 3.652 m/s |
| WLTC 3b | rules | 175.99 | 23.266 km | 0.0006 m/s | 0.006 m/s |
| WLTC 3b | deployed actor (seed 3) | 176.53 | 23.266 km | 0.0286 m/s | 0.485 m/s |
| HWFET | rules | 153.90 | 16.507 km | 0.0003 m/s | 0.004 m/s |
| HWFET | deployed actor (seed 3) | 154.07 | 16.507 km | 0.0003 m/s | 0.004 m/s |
| UDDS | rules | 167.93 | 11.990 km | 0.0007 m/s | 0.009 m/s |
| UDDS | deployed actor (seed 3) | 168.32 | 11.990 km | 0.0007 m/s | 0.009 m/s |

- A low ceiling now costs tracking and distance, as it should.
- The rules and the always-regen reference are unchanged to the last digit:
  their ceiling never bound, so nothing about them was ever affected.
- The deployed actor on US06 is 0.13% **worse** than the rules on energy and
  falls 3.65 m/s behind the cycle at worst. It was trained on the plant that
  paid it to lower the ceiling.

## 5. What stands and what does not

**Withdrawn.** "The actor uses less energy than the rule manager in 14 of 16
settings, by 8.28% on average", and the same claim in the repeat campaign.

**Unaffected.** Every timing result: zero late control steps in 2.28 million,
actor worst-case inference of 825 us, jitter. These are measured on the chip
and do not depend on the plant's energy bookkeeping. Week 7's dynamic program
and week 8's HWFET comparison also stand, because no ceiling bound in either.

**Needs re-measuring.** The actor arm of ablation A4 and of both PIL
campaigns, since the actor's ceiling bound in them. The sensor-noise
observation (rules degrade with noise, 191 to 201 Wh/km) is on the rule arm,
whose ceiling did not bind, and is re-checked in the corrected campaign.

## 6. What was re-run

1. Five seeds of SAC per arm retrained on the corrected plant:
   `docs/week11-sac-corrected.json`.
2. The 36-run PIL campaign on the board against the corrected plant, and the
   A4 sweep: section 7.

## 7. The campaign on the corrected plant, MEASURED

**Run 2026-10-06 to 2026-10-07** on the board, Arduino build,
`-DFAULT_INJECT=0 -DFALLBACK_ENABLED=1`. Data: `docs/week11-pil-corrected.json`
(36 runs; the two arms are also kept separately as `-rule.json` and
`-actor.json`). The learned arm is the actor retrained on the corrected plant:
five seeds per arm, 154.86 +- 0.51 Wh/km on HWFET for the
no-forecast arm against 153.90 for the rules, seed 3 chosen on validation
(`docs/week11-sac-corrected.json`).

2,282,832 control steps, 0 late.

| Setting | Rules, Wh/km | Learned, Wh/km | Learned vs rules | Rules: tracking RMSE, m/s | Learned: tracking RMSE, m/s |
|---|---|---|---|---|---|
| driving_condition / urban | 168.13 | 169.30 | +0.70% | 0.0131 | 0.0156 |
| driving_condition / highway | 153.96 | 154.40 | +0.29% | 0.0036 | 0.0035 |
| road_grade / uphill | 305.26 | 305.21 | -0.02% | 0.0390 | 0.2366 |
| road_grade / flat | 190.75 | 191.43 | +0.36% | 0.0150 | 0.2287 |
| road_grade / downhill | 79.30 | 83.83 | +5.71% | 0.0101 | 0.1931 |
| sensor_noise / floor | 190.75 | 191.81 | +0.55% | 0.0205 | 0.2295 |
| sensor_noise / elevated | 191.33 | 192.90 | +0.82% | 0.0145 | 0.2175 |
| sensor_noise / severe | 201.55 | 210.53 | +4.45% | 0.0548 | 0.1921 |
| comm_delay / none | 190.73 | 191.76 | +0.54% | 0.0144 | 0.2299 |
| comm_delay / one period | 349.52 | 378.26 | +8.22% (excluded) | 31.4772 | 25.6688 |
| comm_delay / three periods | 359.78 | 339.20 | -5.72% (excluded) | 43.3592 | 30.3715 |
| driver_aggression / normal | 190.99 | 191.98 | +0.52% | 0.0276 | 0.2281 |
| driver_aggression / brisk | 197.16 | 197.38 | +0.11% | 0.0450 | 0.3306 |
| driver_aggression / aggressive | 204.46 | 204.75 | +0.14% | 0.0981 | 0.5042 |
| driving_condition / aggressive mixed | 191.41 | 191.48 | +0.03% | 0.0436 | 0.2262 |
| battery_state / high | 190.93 | 191.37 | +0.23% | 0.0263 | 0.2332 |
| battery_state / medium | 191.00 | 191.63 | +0.33% | 0.0265 | 0.1955 |
| battery_state / low | 190.80 | 191.20 | +0.21% | 0.0206 | 0.1678 |

**The learned controller uses less energy than the rule manager in
1 of the 16 valid settings, and +0.94% on average.** The week-10 campaign
reported less in 14 of 16 and 8.28% on average. The one setting it wins
(uphill, -0.02%) is smaller than the gap between two identical campaigns.

It also follows the cycle less well. On every US06-based setting its tracking
error is about 0.2 m/s where the rules hold 0.02 to 0.05, and 0.50 against
0.10 under aggressive driving. The ceiling it sets now costs it speed, which
is what the ceiling should always have cost.

The two link-delay settings are excluded for the reason given in
`docs/week10-pil-campaign.md` section 6.5: neither controller follows the
cycle in them, in any campaign.

Four rule cells were first taken while other jobs were loading the laptop
(21 to 54 dropped frames). They were run again on a quiet machine and the
first takes are kept, unmerged, in `docs/week11-pil-corrected-rule-disturbed.json`.

### The link-outage sweep (ablation A4) again

Same eight lengths and eight paired onsets as `docs/week9-a4.md` sections 10
and 11, with the retrained actor in the loop. Data:
`docs/week11-a4-{on,off}-{len}s.json`. Peak speed error in m/s.

| Outage | Handling on, median | Handling off, median | Handling on, worst | Handling off, worst |
|---|---|---|---|---|
| 0.2 s | 0.060 | 0.059 | 0.228 | 0.182 |
| 0.5 s | 0.171 | 0.103 | 0.571 | 0.202 |
| 1 s | 0.353 | 0.157 | 1.341 | 0.370 |
| 2 s | 0.674 | 0.496 | 3.203 | 1.486 |
| 3 s | 0.915 | 0.812 | 5.189 | 1.408 |
| 4 s | 1.211 | 1.548 | 6.670 | 3.727 |
| 5 s | 1.638 | 1.440 | 7.396 | 7.971 |
| 10 s | 3.715 | 5.328 | 13.275 | 18.187 |

The worst case still changes hands between 4 s and 5 s, and the 10 s row is
still the handling's strongest. These files are a separate campaign from the
week-9 ones, on a different plant and a different actor, and are not pooled
with them.

## 8. Why the rule arm moved

It did not. Early in the corrected campaign a few US06 cells of the rule arm
read 0.1 to 0.3% above the repeat campaign, and that was noted as something to
look at, since the correction should not touch a controller whose ceiling does
not bind.

`scripts/check_rule_arm.py` compares the three campaigns that ran the same 18
rule cells with the same seeds (`docs/week11-rule-arm-check.json`). Across the
16 valid cells the corrected arm differs from the repeat campaign by
+0.07% on average, with a 95% interval of -0.03 to +0.17, and 0.46% at
worst. The two week-10 campaigns, which differ by nothing but the day, differ
by 0.16% in size and 0.57% at worst. The interval contains zero and the
worst cell is inside the spread between identical campaigns.

The early impression came from four cells, three of which were the disturbed
ones.
