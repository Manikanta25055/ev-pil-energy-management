# Measurement round after the panel review (plan, fixed 2026-10-14 before any run)

The reframed manuscript (paper/, round 2) answers the panel's text items. Five
items need data. This plan fixes, before any run, what is measured, how, and
what each outcome does to the paper. A result that goes against the paper's
current claim changes the claim; the criteria below are not revised after the
data are seen. Anything decided later is recorded as a post-hoc change in the
paper's Table 3.

Source of the items: paper/reviews/2026-10-14/editorial-decision.md.

## Order and constraints

Host jobs run first, one at a time (8 GB machine). Board jobs run after, with
the machine kept quiet (no host simulation during a board run). Before each
board job: check `pgrep -fl "run_pil|run_arm|chain_after|finalize"` and the
Codex agent's handoff; board on the native USB port; build with arduino-cli;
confirm the compiled arm from the diagnostic counters (`actor_steps`,
`speed_est_mode`); pass build switches explicitly in both directions. Long
board campaigns run under a relaunch wrapper because the board drops off the
bus under reset-per-run. Any controller written in both Python and C gets a
parity test before its board run.

Board rules fixed before the first board run: every arm runs the rule-based
manager unless it is the learned arm; a run with more than 16 dropped frames
and tracking under 1 m/s is set aside and taken once more, the rule the
corrected campaign used (paper Table 3); the low-pass arm uses
`SPEED_FILTER_ALPHA=0.1`, the value the existing tuning on the training cycle
chose for ten times the noise floor (`docs/week11-speed-arms-tuned.json`),
and the baseline loop is built with `SPEED_FILTER_ALPHA=1.0` passed
explicitly. The twelve distinct conditions for B2 are: urban, highway and the
nominal US06 (driving-condition axis), uphill and downhill, SOC high, medium
and low, noise 3x and 10x, driver aggression 1.25 and 1.5.

## H1. Headroom bound on the corrected plant (host, panel R1/S1 basis)

The dynamic-programming (DP) optimum in the paper (rules within 0.01% to 0.16%)
was computed before the plant fix (week 7). Re-run `scripts/run_control_baselines.py`
on the corrected plant, same cycles, SOC 0.80, 12 C, SOC grid 161, to a new file
`docs/2026-10-14-control-baselines-corrected.json`.

Decision: the paper reports the new gaps. If every rule-to-DP gap stays at or
below 0.5%, the headroom argument stands with the new numbers. If any gap
exceeds 0.5%, the "no honest gain was available" claim is weakened in the
abstract, Section V and Section IX to the measured gap.

## H2. Bias-aware detector on the 70 logged trips (host, panel R4)

The first detector failed on the logged acceleration channel (flagged 99% of
the time). The bias-aware detector was never replayed there. Replay it, with
its tuned settings unchanged, on all 70 logged i3 trips (no injected fault),
as `scripts/check_accel_channel.py` did for the first detector, at the logs'
10 Hz, to `docs/2026-10-14-bias-aware-logged-replay.json`.

Detail fixed before the run (2026-10-14, after H1 started, before any H2
code ran): the detector is the Python `BiasAwareFaultKalman` with its default
(tuned) settings and the B5 noise constants from
`docs/week11-speed-arms-tuned.json`, fed logged speed and logged
acceleration. Two passes: (a) at the logs' 10 Hz, like the first detector's
replay, primary; (b) speed and acceleration interpolated to 100 Hz with the
campaign's speed-noise floor added (seed 0), secondary. Logged speed is
exactly repeated while the car stands still, which a sensor with noise never
does; alarms from the frozen-reading test below 0.5 m/s are therefore counted
separately and not charged to the criterion. All other alarms count.

Decision, against its registered limit (under one false alarm per clean hour):
report alarms per hour and share of time flagged. Below 1 per hour: the paper
says the detector held on logged data at 10 Hz, with the rate caveat. At or
above: the paper says it did not, and the detector's usable claim is limited
to simulated channels.

## H3. Plant sensitivity of the ranking (host, panel R7)

Paired comparison of the rule-based manager and the deployed learned policy
(corrected retraining, seed 3) on the host, on US06 and HWFET, one parameter
changed at a time: rolling coefficient at the published coastdown value
(0.00878) and at the fitted value; rotational inertia factor 0 and 0.1706;
regeneration ceiling at 0.8x and 1.2x; drivetrain efficiency minus and plus 3
points. Same noise seed for both arms. Output
`docs/2026-10-14-plant-sensitivity.json`.

Decision: if the sign of learned-minus-rule energy is unchanged in every
variant, the paper says the ranking was insensitive to these parameters over
the tested ranges. If any variant flips the sign, the paper reports which, and
the corrected comparison is stated as conditional on the identified plant.

## H4 and B1. Low-pass baseline for the Kalman result (host, then board; panel S4)

A first-order low-pass on the speed reading is the obvious cheaper
alternative to the two-state Kalman estimator. Host: add the arm to the speed
estimator set, choose its smoothing constant on the training cycles (WLTC3B,
UDDS) at ten times the noise floor, fixed before any US06 run. Board: a new
firmware estimator mode mirroring the Python filter, with a parity test; then
US06 at the noise floor and at 10x, baseline loop, Kalman and low-pass, noise
seeds 100 and 200 (12 runs, about 2 h). Output `docs/2026-10-14-lowpass-pil.json`.

Decision: report the 10x energy loss of each arm against its own floor runs,
with both seeds. If the low-pass recovers at least as much as the Kalman
estimator, the paper credits filtering in general, not the Kalman structure.
The added Kalman seeds also give the 9.44 to 0.24 Wh/km result its spread.

## B2. Corrected campaign repeats (board, panel R2; overnight)

Two more noise seeds (offsets 100 and 200) for each of the 12 distinct
conditions of the corrected campaign (the nominal US06 condition once), both
arms: 48 runs, about 8.7 h of board time. Requires a `--seed-offset` option in
`scripts/run_pil_campaign.py` (with a test). Output
`docs/2026-10-14-pil-repeats.json`; statistics by extending
`scripts/paper_table5_stats.py`.

Decision: with three seeds per condition, take the per-condition mean paired
difference. The paper's verdict "the learned policy used more energy" stands
if the exact Wilcoxon signed-rank test over the 12 conditions gives two-sided
p below 0.05 with a positive median. Otherwise the verdict becomes "no
measurable difference" and the abstract, Section V and Section X change.

## B3. Extra clean hours for the bias-aware detector (board, optional)

Three more clean hours on the target (no fault), to tighten the false-alarm
bound from about 3 per hour. Output `docs/2026-10-14-bias-aware-clean.json`.
Run only if board time remains after B2.

## After the runs

Update the affected paper sections with the new numbers (writers), re-audit
(fact auditors), rebuild and render, and add any post-hoc change to Table 3.
