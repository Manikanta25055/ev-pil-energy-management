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

## 6. What is being re-run

1. Five seeds of SAC per arm retrained on the corrected plant:
   `docs/week11-sac-corrected.json`, actors in `data/actors-corrected/`.
2. The 36-run PIL campaign on the board against the corrected plant:
   `docs/week11-pil-corrected-{rule,actor}.json`.

Results are appended below when they exist.
