# What ships on the device: the actor, and no forecaster

**Date:** 2026-09-02
**Decision:** taken by the supervisor. Parked decision 4 in the design spec's
open-items table, which had been waiting on decision 1.
**Firmware:** `firmware/main/tasks.c` (`ems_task`), `firmware/main/actor.c`
**Data:** `docs/week10-fullstack.json`

The deployed controller is the SAC actor trained **without** the forecast, and
no forecaster runs on the device. This closes item 2 of
`docs/hardware-pending.md`: the full stack is on the board and measured.

Ablation A3 found the forecast made no difference to control, and G5 measured
the forecaster at 35 ms of a 40 ms budget. It cost almost the whole outer loop
and bought nothing the controller used, so it does not ship.

---

## 1. The policy that ships

`data/actors/sac-without-forecast-seed3.npz`, exported to
`firmware/main/sac_actor_weights.h`, checksum written into the binary.

Seed 3 of five, chosen on the validation cycle (HWFET) at 154.07 Wh/km. US06
stays sealed. Choosing on validation is what a validation cycle is for;
choosing on the sealed cycle would be selection on the test set, and this
project has spent its one permitted criterion revision already.

The choice of the **without-forecast arm** is not cosmetic. Both arms have the
same eight inputs: the forecast is two channels of the observation, not extra
width. With `use_forecast=False` the environment holds those two at zero, and
the without-forecast actor was trained that way. Deploying a with-forecast
actor while shipping no forecaster would feed it two permanently dead channels
it had never seen at zero during training. It would run, return actions in
range, and be a controller nobody trained.
`tests/control/test_actor_export_pipeline.py` asserts the deployed actor is a
no-forecast one, so that pairing cannot be broken quietly.

## 2. The firmware had never run either model

Worth recording, because "put the trained policy on the chip" sounds like a
configuration change and was not one. Before this week:

- `infer_task` ran a fixed busy-loop, commented "Dummy load standing in for the
  forecaster. Phase 2 replaces this."
- `ems_task` computed the rule action on **both** branches, commented "Week 8
  replaces this branch with the exported SAC actor. Until then both paths
  produce the rule action, so the fallback counter says how often the policy
  would have been unavailable rather than how often a policy existed."

So `ems_fallback_steps` had been counting an opportunity rather than an event,
and no measurement before this one involved a learned policy in the loop.

Four things had to be built.

**The state frame was missing an observation.** The policy observes pack
temperature. The frame carried ten floats and `t_batt_c` was not among them,
and nothing on the microcontroller can derive it: it is a plant state the host
owns. The frame is eleven floats now, 44 bytes.
`tests/firmware/test_state_frame_parity.py` parses `tasks.c` and fails if the
host's field order and the firmware's assignments diverge, because a frame of
the right size with the fields in the wrong order is accepted and makes the
controller act on a grade it thinks is a speed.

**The action decode had to travel with the weights.** The policy emits three
numbers in [-1, 1] which an affine map turns into a regen blend, a power limit
and an auxiliary derate. The bounds are now emitted into the generated header
by the exporter rather than defined in the firmware, and
`write_c_header` requires them, so a header that cannot decode an action is not
a thing the exporter can produce. This is the divergence that hides best: every
value a wrong map produces is still inside its physical range, so the
controller runs, the energy figure is plausible, and nothing raises.
`tests/control/test_decode_c_parity.py` drives the C and the Python decode over
the same inputs, corners and out-of-range values included.

**The diagnostics had to say what the policy did.** Two counters joined the
DIAG frame: `actor_steps`, the outer steps the policy answered, and
`actor_wcet_us`, its worst inference on silicon. Without the first, a run
cannot say how much of itself the learned controller was actually driving.
Without the second, an energy number would ship without its on-device cost.

**The actor had to be wired into `ems_task` with the rules behind it.** When
inference is late the rule action is used and `ems_fallback_steps` increments,
which is what that counter was always meant to record.

## 3. Measured on the board

10 minutes, Arduino-core build, the same G3 harness as every other loop-timing
run.

| | Value | |
|---|---|---|
| Control loops | 59,650 | |
| Outer steps the actor answered | **5,965** | every one of them |
| Steps the rules had to cover | **0** | `ems_fallback_steps` |
| Loops late against their own deadline | **0** | `ctrl_late` |
| Actor worst inference | **825 us** | 0.8% of the 100 ms outer period |
| Control task WCET | 64 us | |
| Jitter p50 / p99 / p99.9 | 25 / 25 / 25 us | unchanged by the actor |
| Frames the chip did not get in time | 5 | the criterion G3 fails on |
| Verdict | FAIL | G3, on the same criterion as always |

The actor answered 5,965 of 5,965 outer steps and the rules never took over.
Adding a neural policy to the loop moved neither the jitter distribution nor
`ctrl_late`, which stayed at zero.

**The worst inference is a cold start, not contention.** 825 us is 6.4x the
0.123 ms the bench reports, and the first explanation to reach for is
preemption. It is not: `ems_task` runs at priority 8 on core 1, above
`infer_task` at 5 and `diag_task` at 1, so nothing of ours preempts it. The
number that settles it is that `actor_wcet_us` read **exactly 825 us after one
minute and exactly 825 us after ten**, over 565 inferences and then 5,965. A
contention effect would almost certainly have found a worse case in ten times
the samples. A first-call cost cannot: it happens once, when the code and the
19.3 KB of weights are read from flash into cache.

So the deployment cost has two numbers and both are worth quoting. The first
inference after a reset costs about 825 us. Every one after that costs about
0.123 ms, and 0.128 ms at worst. Against a 100 ms outer period the cold one is
0.8% and the warm one is 0.12%.

## 4. What this does not claim

**The actor is slower than the controller it replaces, in energy terms.** The
without-forecast arm finishes at 154.68 +- 0.69 Wh/km against the rule
manager's 153.90, a gap of 0.51%, with the 95% interval entirely on the worse
side. Deploying it does not make the car more efficient and this note does not
say it does. What the deployment demonstrates is that a learned policy of this
size runs inside the loop's timing budget on this hardware, with its cost
measured rather than estimated. The energy result stays what week 8 found, and
it is a negative one.

**A dummy load still stands in for a model that will not ship.** `infer_task`
runs its fixed busy-loop, 783 us in this campaign, and that load represents the
forecaster. The forecaster is now not deployed, so core 1 is carrying a phantom
and the true deployed stack has more headroom than the numbers above show.
Removing it is a one-line change and it was **not** made, because that load is
also the vehicle for `-DFAULT_INJECT=1`, which is how week 7 triggered the
inference-overrun path and how ablation A4 was measured. Changing it would
change the conditions under which those results were taken, and this project
does not make that kind of change quietly. It is an open item, not an
oversight.

**G3 still fails**, on the same criterion, for the same reason as on every
other build: the host does not always answer in time. The distinction that
matters is intact. The loop never misses its own deadline, with a neural
network now inside it.

## 5. Reproducing

```bash
python3 scripts/verify_actor.py --export \
    --actor data/actors/sac-without-forecast-seed3.npz
./scripts/arduino_build.sh --flash
./scripts/g3_campaign.sh 10 /dev/cu.usbmodem1101 \
    --out-json docs/week10-fullstack.json
```
