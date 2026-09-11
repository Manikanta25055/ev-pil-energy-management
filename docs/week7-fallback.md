# Week 7: the watchdog and the fallback path, taken on hardware

**Date:** 2026-08-31
**Firmware:** `firmware/main/tasks.c`, `firmware/main/control.c`
**Scripts:** `scripts/run_fallback.py`, `scripts/g3_campaign.sh`
**Data:** `docs/week7-fallback.json`, `docs/week7-watchdog.json`,
`docs/g3-loop-timing.json`

Spec 4.4 says that if inference overruns its budget the control task falls
back to rule-based regeneration and a counter increments, and that misses
appear in the results rather than being silently absorbed. Week 7 builds that
path and then takes it, on the board, on purpose.

A fallback path that has never been taken is a claim, not a result.

---

## 1. Three failures, three responses, three counters

Collapsing these into one "fault" state is how a controller ends up limping
because a diagnostic task was late.

| Failure | Detected by | Response | Counter |
|---|---|---|---|
| The 100 ms outer loop has not published a setpoint | its setpoint timestamp is older than 300 ms | the rule-based manager runs inside the 10 ms control task | `ctrl_fallback_steps` |
| The plant state is older than 5 control periods | consecutive reads that returned nothing | torque ramps out at 10 Nm per step, integrator frozen | `limp_steps` |
| Inference overran its 40 ms budget | the task's own timing | the energy manager emits the rule action for that outer step | `ems_fallback_steps` |
| A task stops running altogether | FreeRTOS task watchdog, 2 s | panic and reset | `boot_reason` |

The control task asks how *old* the outer loop's last answer is rather than
whether the outer loop is alive. That is a question with an answer even when
the answer is "the task is gone".

The watchdog is a liveness guard and is deliberately not a deadline monitor.
Its timeout is 2 s against a 10 ms loop, two orders of magnitude apart,
because deadlines are counted in software at microsecond resolution and a
watchdog that fires on a late loop would reset a working vehicle.

Limping freezes the integrator. An integrator fed a stale error charges up
against a vehicle that has already moved on, and the recovery when the link
returns is then worse than the outage was.

---

## 2. Measured on the board

Injection schedule and the counters it moved. Two of the three faults are
injected inside the firmware (`FAULT_INJECT=1`) because they cannot be caused
from outside it; the third the host causes itself, by not answering.

| Fault | Injected | Expected | Measured |
|---|---|---|---|
| Host goes silent, 1.0 s at 100 Hz | by the host | 101 stale steps, of which the first 5 are tolerated | `stale_steps` 101, `limp_steps` **96** |
| Outer loop stops publishing, 2.0 s | firmware | 2.0 s less the 300 ms staleness window, at 100 Hz | `ctrl_fallback_steps` **180** |
| Inference overruns, 2.0 s at a 100 ms period | firmware | 20 outer steps | `infer_deadline_misses` **20**, `ems_fallback_steps` **20** |

Every number is exactly what the schedule implies. Torque during the silent
window went from 226.18 Nm to **0.00 Nm** and stayed there, which is the ramp
doing what it is for: the actuation frames keep flowing, and what they carry
is a controller declining to act on a speed measurement it no longer trusts.

`ctrl_late`, the count of loops that missed their *own* deadline, stayed at
**0** throughout -- including while limping. The fallback path does not cost
the loop its timing.

**Watchdog** (`FAULT_INJECT=2`): the control task was made to stop yielding
after 20 s. The board reset, and the next DIAG frame reported boot reason
**task watchdog**. That is the only way a watchdog event can be reported at
all -- the firmware that would have reported it is the firmware that was
restarted -- which is why the reset reason is sent in every DIAG frame rather
than printed once at boot.

---

## 3. Gate G3, re-measured on the week 7 firmware

The loop changed this week: a real PID with a feedforward replaced the
placeholder proportional controller, the state frame grew from 8 floats to 10
to carry the reference, and the actuation frame grew from 3 to 4 to carry the
auxiliary derate. The loop the paper reports has to be the loop that was
measured, so G3 was re-run in full.

Ten minutes, 59,650 control loops, unchanged from the week 3 campaign.

| Quantity | Week 3 (pipelined) | Week 7 | Limit |
|---|---|---|---|
| jitter p99 | 25 us | **25 us** | 1000 us |
| jitter p99.9 | 25 us | **25 us** | -- |
| control-task WCET | -- | **97 us** | 10,000 us |
| `rtt_max_us` (see note) | 77 us | **799 us** | -- |
| loops late against their own deadline | not counted | **0** | -- |
| host answered late (stale steps) | 8 | **4** | 0 |
| reply timeouts | 0 | **0** | 0 |
| malformed frames | 0 | **0** | 0 |
| frames the host never saw | 0 | **0** | 0 |

The control task's worst case rose to 97 us because it now does real work: a
feedforward with two trigonometric calls, a filtered-derivative PID and the
anti-windup branch. That is 0.97% of the period.

**Correction, 2026-09-11.** This row used to be labelled "worst round trip",
and the text explained its rise from 77 to 799 us by the larger frames and the
extra host work. Both runs were pipelined, and in the pipelined loop
`rtt_max_us` times the read of the reply to the *previous* request against the
*current* request's timestamp, so it is not a round trip
(`docs/g3-loop-timing.md` has the detail). It is also a running maximum since
boot, which `scripts/run_g3.py` notes includes the start-up transient. The
explanation given for the rise is therefore not supported, and none is offered
here. It is not what the gate turns on.

**G3 still fails, on the same criterion and for the same reason, with the
evidence now sharper.** Four events in 59,650 loops, all of them the host
answering late, and zero of them the loop missing its own deadline. The week 3
report could not separate those two; the `ctrl_late` counter added this week
can, and it reads zero.

The criterion is not being loosened here. The decision the gate has to take is
recorded in the spec's open-items table, and it is the same one week 3 raised:
whether "zero dropped frames" should distinguish a controller that missed its
deadline from a general-purpose operating system that answered a millisecond
late.

---

## 4. Build switches

Variants are rebuilds rather than edits, so that the firmware the paper
reports is the firmware that was measured.

```bash
./scripts/idf.sh build                        # normal
./scripts/idf.sh -DFAULT_INJECT=1 build       # scheduled fault injection
./scripts/idf.sh -DFAULT_INJECT=2 build       # hang the control task
./scripts/idf.sh -DFALLBACK_ENABLED=0 build   # ablation A4, handling off
./scripts/idf.sh -DCTRL_PIPELINED=0 build     # the synchronous loop
```

`FALLBACK_ENABLED=0` is ablation A4, which is scheduled for week 9. The switch
exists now so that the ablation is a rebuild of this firmware rather than a
reconstruction of it later.
