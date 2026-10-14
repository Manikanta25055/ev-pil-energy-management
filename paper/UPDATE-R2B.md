# Update 2b: host results of the measurement round (2026-10-14)

Plan and its criteria: `docs/2026-10-14-measurement-plan.md` (committed before
the runs; commits 6adeddf, 67859d8, 8a6dda7). Board results (B1 low-pass, B2
repeats) arrive later in update 2c; do not anticipate them. All results below
are SIMULATED on the host. Same prose rules as BRIEF.md and REFRAME.md; run
the linter and measure script before and after; keep claims files current.
Do not build or render the paper: a board campaign is running and the machine
must stay quiet. No simulations, no heavy scripts.

## H1. Headroom on the corrected plant

`docs/2026-10-14-control-baselines-corrected.json` (script
`scripts/run_control_baselines.py`). Rule-based manager against the DP
optimum (comfort priced), corrected plant: WLTC3b 175.99 against 175.94
(0.03%), UDDS 167.93 against 167.67 (0.16%), HWFET 153.90 against 153.89
(0.01%), US06 190.47 against 190.39 (0.04%). Identical to the pre-fix values:
the discharge ceiling never binds in the DP solution, so the fix does not touch
it. Plan criterion (all gaps at or below 0.5%): met. Remove every statement
that the DP bound predates the correction or was not re-run; say it was re-run
on the corrected model and did not change.

## H2. Bias-aware detector on the 70 logged trips

`docs/2026-10-14-bias-aware-logged-replay.json` (script
`scripts/replay_b7_logged.py`). 70 trips, 30.4 h, no fault in the data,
detector settings unchanged.

- 10 Hz (the logs' rate; primary, as for the first detector): 30 alarms
  counted, 0.99 per hour (23 gross-jump, 7 step), plus 196 frozen-test alarms
  at standstill counted apart as fixed in the plan (logged speed repeats
  exactly at rest). The flag was up 59% of the driving time; 42 of 70 trips
  had no counted alarm.
- 100 Hz (interpolated, speed-noise floor added; secondary): 492 alarms, 16.2
  per hour, almost all from the step test; flag up 72% of the time.
- Post-hoc diagnostic (not in the plan; record it in Table 3): 10 Hz with the
  frozen test disabled: 1.9 alarms per hour (44 gross, 14 step), flag up 21%.

Reading: the count criterion (under 1 per clean hour) is met only narrowly at
10 Hz and only because the frozen-at-rest alarms were set aside; the flag
stays raised for most of the drive; at 100 Hz it fails by a factor of 16. The
detector does not hold on logged channels. Its 120 of 120 result stands only
for software-injected faults on a simulated acceleration channel. Caveats: the
logs are 10 Hz and the gross-jump test assumes 10 ms sampling; the 100 Hz pass
interpolates the logs. Section VII and the Discussion must say this plainly;
Table 2 gets a row for this criterion; Table 3 gets the post-hoc diagnostic.

## H3. Plant sensitivity of the ranking

`docs/2026-10-14-plant-sensitivity.json` (script
`scripts/plant_sensitivity.py`). Rule-based manager against the deployed
learned policy (corrected retraining, seed 3, no forecast), host loop, no
noise; the simulated vehicle varied one parameter at a time while the
controllers kept the nominal model. US06 and HWFET, seven variants each
(nominal; rolling coefficient at the published 0.00878; rotational factor 0;
regeneration ceiling x0.8 and x1.2; drivetrain efficiency minus and plus 3
points). The learned policy used more energy in all 14, by 0.12% (HWFET,
rotational factor 0) to 0.81% (HWFET, published rolling coefficient); nominal
+0.36% US06, +0.20% HWFET. The regeneration ceiling at x1.2 changes nothing
(it does not bind upward). Plan criterion (sign unchanged in every variant):
met. Replace every "no sensitivity study was run" with this result and its
limits (one policy seed, host loop without noise, one parameter at a time).

## Owners

- W2 (02-platform.md): Table 2 rows for H1, H2, H3 with date 2026-10-14 and
  outcome; Table 3 row for the H2 post-hoc diagnostic; the text count of
  missed criteria updated.
- W3 (03-plant.md): the limits subsection gets the H3 result.
- W4 (04-ems.md): the headroom subsection: DP re-run on the corrected model.
- W6 (06-estimation.md): bias-aware detector: H2 result, plainly.
- W7 (07-...md): Discussion: H1, H2, H3 where they change what is said
  (headroom wording, audit procedure, safety scope, limitations, future work
  no longer lists the sensitivity sweep as missing); the Conclusion only if a
  sentence there is now wrong.
