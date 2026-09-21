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

36 runs, 2,282,832 control steps, `ctrl_late` **0** throughout. Every run of
the actor arm reported `actor_steps` greater than zero and every run of the
rule arm reported exactly zero, so each arm was measured on the image it
claims.

### 6.1 The timing result, which is what the campaign was for

The loop never missed its own deadline. Not once in 2.28 million control
steps, with a learned policy inside it, across six kinds of variation
including one that broke the host link badly enough to stop the car following
the cycle at all. That is the embedded claim this project set out to make and
it is now made at the widest scope available.

### 6.2 The energy result, which the campaign was not expecting

| Setting | Rule, Wh/km | Actor, Wh/km | Actor vs rule |
|---|---|---|---|
| driving_condition / highway | 154.01 | 154.14 | +0.09% |
| driving_condition / urban | 168.11 | 168.56 | +0.27% |
| road_grade / downhill | 79.67 | 75.85 | -4.79% |
| battery_state / low | 190.47 | 176.62 | -7.27% |
| battery_state / high | 190.66 | 176.52 | -7.42% |
| driving_condition / aggressive_mixed | 190.79 | 176.53 | -7.47% |
| battery_state / medium | 190.61 | 176.33 | -7.49% |
| road_grade / flat | 191.16 | 176.77 | -7.53% |
| comm_delay / none | 190.88 | 176.47 | -7.55% |
| driver_aggression / normal | 190.95 | 176.50 | -7.57% |
| sensor_noise / floor | 191.04 | 176.23 | -7.75% |
| sensor_noise / elevated | 192.22 | 176.92 | -7.96% |
| road_grade / uphill | 305.14 | 274.20 | -10.14% |
| sensor_noise / severe | 200.65 | 173.17 | -13.70% |
| driver_aggression / brisk | 196.83 | 168.21 | -14.54% |
| driver_aggression / aggressive | 203.26 | 159.34 | -21.61% |

Two settings excluded, `comm_delay/one_period` and `comm_delay/three_periods`,
where neither controller followed the cycle (tracking RMSE 32.8 to 45.9 m/s
against hundredths elsewhere) so Wh/km has no denominator worth dividing by.
Section 6.5 explains that axis.

**The actor is ahead in 14 of the 16 valid settings, by 8.28% on average.**
The two it loses are the two gentlest cycles.

### 6.3 Why this is not a contradiction of week 8

`docs/week8-sac.json` records `"cycle": "hwfet"` and
`"test_cycle_sealed": "us06"`. The 0.51% deficit the project has carried since
week 8 was measured **on the validation cycle**, with US06 sealed and never
spent. This campaign is the first comparison on it.

The highway row reproduces week 8 almost exactly:

| | week 8, offline | here, on the chip |
|---|---|---|
| HWFET, rule | 153.90 Wh/km | 154.01 Wh/km |
| SoC at end | 0.6900 | 0.6900 |

0.07% apart, from independent implementations on different machines. Week 8
was right about the highway. The highway is where the two controllers have
least to disagree about.

### 6.4 The mechanism, inferred and not observed

The actor draws a lower peak current in every valid setting. Battery loss goes
as the square of current, so shaving peaks saves energy, and saves more the
harder the car works. The ordering follows exactly:

| Axis, in order of demand | Actor advantage |
|---|---|
| driver_aggression: normal / brisk / aggressive | 7.57% / 14.54% / 21.61% |
| road_grade: downhill / flat / uphill | 4.79% / 7.53% / 10.14% |
| cycle: hwfet / udds / us06 | -0.09% / -0.27% / 7.47% |

Three independent axes, each monotonic in how hard the vehicle is driven. The
likely cause is the discharge power ceiling, which the actor sets and the rule
manager effectively does not, and which ablation A4 already pointed at from
the other direction.

**`p_limit_w` is not logged.** Only the current that follows from it is. So
this is a mechanism that fits every number in the campaign and has never been
observed directly. Adding that counter to the DIAG frame is the single highest
value change available to this project, and it should happen before this
result is published.

The sensor-noise axis adds a second, separate effect: the rule manager
degrades as noise rises (191.04, 192.22, 200.65) while the actor does not
(176.23, 176.92, 173.17). A threshold-switching controller chatters across its
thresholds when its inputs are noisy; a network output does not. That is a
robustness result and it is independent of the current argument.

### 6.5 What the communication-delay axis actually measured

Not link latency. The delay is a wait before every host reply and it
serialises with the host's own plant step, so at 10 ms on a 10 ms loop the
host cannot answer as often as it is asked and falls behind without bound
rather than settling one step late. `ctrl_late` stayed 0: the chip met every
deadline it owned. The axis measured host throughput.

The rationale written in `src/evpil/control/scenarios.py` is wrong about this
and has been left as written, with this correction recorded rather than folded
back, the same way the A4 prediction's errors were handled. Measuring latency
properly needs the delay applied to delivery while answers keep flowing, which
this rig cannot do.

### 6.6 How much a number here is worth

The baseline setting is a level of five separate axes, so it was run five
times per controller with a different noise draw each time. Those runs should
agree, and how far apart they land bounds what anything else may claim:

| | mean | spread | spread % |
|---|---|---|---|
| Rule, energy | 190.96 Wh/km | 0.13 | 0.07% |
| Actor, energy | 176.50 Wh/km | 0.17 | 0.10% |
| Tracking error | — | — | ~18% |

Energy repeats to about a tenth of a per cent, so the 7 to 21% differences
above are between fifty and two hundred times the noise. Tracking error does
not repeat nearly as well, so the tracking column separates nothing and no
ordering is claimed from it.

### 6.7 What this does not establish

One run per cell, so no figure carries an interval. Interactions are not
measured: one axis moved at a time. The mechanism is inferred from current,
not observed. And a reversal of a headline result deserves a repeat campaign
before publication, which this is not.

**This note reports what was measured. It does not settle what the project
should conclude, and that decision is not one a measurement campaign makes on
its own.**
