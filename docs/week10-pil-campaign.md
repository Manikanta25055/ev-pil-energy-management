# The week-10 PIL campaign

**Run 2026-09-21** on the Arduino build, `-DFAULT_INJECT=0
-DFALLBACK_ENABLED=1`, board on `/dev/cu.usbmodem101`. This is item 3 of
`docs/hardware-pending.md`, the last piece of hardware work the plan lists.

## 1. What it measures, and what it does not

Every controller result before this one holds the conditions fixed. Week 7's
baselines, week 8's SAC campaign and week 10's deployment all run the same four
cycles at the same ambient, the same starting charge and clean measurements.
That is the right way to compare two controllers and the wrong way to find out
whether the comparison survives contact with anything else.

This campaign varies the conditions. Spec section 6.5 trimmed the original
plan's thirteen variations to six axes, and this sweeps each of the six across
three levels, with both controllers run against every level on the chip:

| Axis | What moves | Levels |
|---|---|---|
| Driving condition | the cycle | UDDS (urban), HWFET (highway), US06 (aggressive mixed) |
| Road grade | a constant offset on the cycle's grade | +0.03 rad, 0, -0.03 rad |
| Battery state | starting charge | 0.85, 0.55, 0.25 |
| Sensor noise | multiplier on the measurement floor | 1x, 3x, 10x |
| Communication delay | latency injected on the host's reply | 0, 10 ms, 30 ms |
| Driver aggression | time-scaling of the reference | 1.0, 1.25, 1.5 |

That is 36 runs.

Each is a whole drive cycle at 100 Hz with the real control software on the
microcontroller, so the campaign costs about six hours of board time and
cannot be shortened by running faster than real time: the chip is the clock
master and a cycle takes as long as the cycle takes.

The arrangement is ablation A4's, with the fault removed. The board runs the
control stack; the host runs the validated plant of
`docs/g2-plant-validation.md`, stepped by the torque the board just commanded;
the reference is a drive cycle. A4 broke the link on purpose and asked what a
fault costs. This asks what ordinary variation costs while everything works.

## 2. Four decisions that shape what the numbers mean

**One axis moves at a time.** Every level inherits a single baseline and
overrides one field, and `tests/control/test_scenarios.py` asserts it. A
campaign that varied two at once would produce the same 36 rows and no
attributable result.

The cost of that choice is real and should be stated. Interactions are not
measured. This says what each variation does on its own, not what a cold
uphill motorway in the rain does to a controller that is already short of
charge, and the places where a controller actually fails are usually the
places where two things go wrong together.

**Sensor noise is on the measured channels only.** The state frame carries
eleven floats, of which `v_ref_mps` and `a_ref_mps2` are the reference the
controller is tracking rather than a measurement of the vehicle. Adding noise
to those would move the target, and the tracking error would then include error
the controller never made.

**Every scenario carries the noise floor, not just the noise axis.** The plant
and both controllers are deterministic. Without a seeded stochastic term in
every run, three seeds would return bit-identical results and the campaign
would report a standard deviation of exactly zero, which would be an artefact
presented as a measurement.

**Driver aggression is a time-scaling, not a speed-scaling.** The same speeds
arrive in the same order, sooner, so accelerations scale with the factor and
the cycle finishes earlier. Scaling the speeds would be a different cycle, and
the tracking error would be measured against a trajectory no regulation
defines.

## 3. Energy is reported on the comparable scale

`equivalent_wh_per_km` charges shed cabin heat back at what it saved, matching
`evpil.control.sim.Result.equivalent_wh`, the DP's comfort-priced arm and the
reinforcement-learning reward. All four are therefore on one scale.

Raw `wh_per_km` is reported beside it and must not be used to rank the arms. A
controller that turns the heating down in a Munich winter shows a lower raw
figure without having managed any energy, in the same way a controller that
drove slower would. The gap between the two numbers is how much comfort an arm
spent.

## 4. How the controller is selected, and how that is checked

The arm is a **compile-time** choice. `ems_task` branches on `HAVE_SAC_ACTOR`,
which `scripts/arduino_build.sh` sets from the presence of
`firmware/main/sac_actor_weights.h`; the frame protocol carries STATE,
ACTUATION, STEP_REQ and DIAG and has no command channel. So each arm is a
separate image and a separate invocation, and the campaign is ordered
controller-outermost: two flashes rather than thirty-six.

Nothing under `firmware/` is edited to do this. The generated weights header is
copied aside, removed for the rule build, and restored immediately, with
`git status firmware/` checked clean afterwards. The two arms build into
separate directories so a stale actor object cannot be linked into the rule
image.

None of which is trusted. `check_arm()` in `scripts/run_pil_campaign.py` stops
the campaign if `actor_steps` disagrees with `--controller`: the counter is
incremented only inside the `HAVE_SAC_ACTOR` branch, so the actor image cannot
report zero across a cycle and the rule image cannot report anything else. A
wrongly flashed arm would otherwise produce a comparison table of one
controller against itself, with a plausible small difference in it.

## 5. Reproducing it

```
# actor arm
./scripts/arduino_build.sh --flash -DFAULT_INJECT=0 -DFALLBACK_ENABLED=1
.claude/night/run_arm.sh actor docs/week10-pil-actor.json actor.log

# rule arm: same source, weights header moved aside for the build
cp firmware/main/sac_actor_weights.h /tmp/w.bak && rm firmware/main/sac_actor_weights.h
EVPIL_ARDUINO_DIR="$HOME/.cache/evpil-arduino-rule" \
    ./scripts/arduino_build.sh --flash -DFAULT_INJECT=0 -DFALLBACK_ENABLED=1
cp /tmp/w.bak firmware/main/sac_actor_weights.h
.claude/night/run_arm.sh rule docs/week10-pil-rule.json rule.log

# merge, then figure and report
python3 -c "import json;a=json.load(open('docs/week10-pil-actor.json'));\
b=json.load(open('docs/week10-pil-rule.json'));\
json.dump({'port':a['port'],'runs':a['runs']+b['runs']},\
open('docs/week10-pil-campaign.json','w'),indent=1)"
PYTHONPATH="src:." python3 scripts/plot_pil.py
PYTHONPATH="src:." python3 scripts/build_report.py
```

The campaign script runs one cell per process and re-execs, because resetting
the board and reopening the port from the same process reads zero bytes on this
machine (`src/evpil/link.py` documents the measurement). It resumes from the
file it has already written, so an interrupted arm costs only the cell in
flight.

## 6. Results

*To be written when both arms are complete. Nothing is recorded here that the
measurement files do not carry, and the report's table is generated from those
files rather than from this note.*
