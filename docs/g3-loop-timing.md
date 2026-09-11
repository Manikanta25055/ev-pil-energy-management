# Gate G3: the 10 ms loop on hardware

**Verdict: FAIL on the frame criterion, PASS on timing by a factor of 40, in
both of the two loop designs measured.** The criterion was not revised. The
measurements and their diagnosis are below, and the decision they call for is
recorded in the spec rather than taken here.

Measured 2026-08-31 on the ESP32-S3 described in `docs/hardware-inventory.md`,
over a ten-minute continuous run.

## What the gate asks

Spec 8.2: the 10 ms loop closes end-to-end with p99 jitter at most 1 ms and
zero dropped frames over a ten-minute run.

## Result

```
59,650 control loops over 10.0 minutes

  jitter p50            within    25 us
  jitter p99            within    25 us     limit 1000 us
  jitter p99.9          within    25 us
  control WCET                    16 us
  worst round trip              7,405 us    MCU timeout at 9,000 us

  MCU reply timeouts                  6
  MCU malformed frames                0
  host frames lost                    0
  host frames malformed               0
```

The timing distribution is not close to its limit. **59,648 of 59,650 loops
landed within 25 microseconds of their slot and the other two within 50.**
Nothing reached the third bin. The gate allows 1000 microseconds.

The frame criterion fails on six reply timeouts.

## Which side failed

The evidence separates them cleanly.

The link carried everything. Zero malformed frames at either end, zero
sequence gaps on 121,255 host-received frames. Nothing was corrupted and
nothing was lost in transit.

The microcontroller met its deadline every time. Its control body runs in 16
microseconds against a 10,000 microsecond period, and its loop period never
deviated by more than 50.

**What failed six times is the laptop answering within the 9 ms the firmware
waits.** The worst measured round trip was 7,405 microseconds, so the host
routinely runs close to the limit, and six times it went over.

The six are not spread evenly. None for the first eight minutes, then six
inside one. That is the operating system doing something else, not a steady
overload.

## Two host-side faults found and fixed before this run

Both would have produced a wrong verdict rather than an obvious failure.

**Sequence numbers were tracked across all frame types at once.** The control
loop and the diagnostics task each run their own counter, so every alternation
between them read as a gap. The first run of this campaign reported 1,566 lost
frames on a link that lost none. G3 is stated as zero lost frames, so that
counter decides the verdict.

**The host polled instead of waiting.** It slept 200 microseconds between
checks for incoming bytes, and a measured `time.sleep(0.0002)` on this machine
takes 304. That latency is spent inside the firmware's 9 ms reply window.
Waiting in the kernel instead cut the worst round trip from 8,576 to 7,405
microseconds and removed the timeouts from a two-minute run entirely. It did
not remove them from ten minutes.

## What this measures about the design

The firmware sends a request and blocks for the reply inside the same 10 ms
slot. That couples its deadline to the scheduling tail of a general-purpose
operating system. macOS is not a real-time host, and a synchronous
request-reply loop makes the microcontroller wait on it.

Spec 4.5 anticipated the host's timing being untrustworthy and made the MCU the
clock master, which is why the jitter figure is 25 microseconds and not
milliseconds. That mitigation protects the *measurement*. It does not decouple
the *loop*.

Spec 8.2's prescribed actions on a G3 failure are to switch transport or
re-scope the loop to 20 ms. Neither addresses what was measured. The transport
lost nothing. Doubling the period would halve the miss rate at best, and would
leave the coupling exactly where it is.

## The fix was built and measured

The control task now requests the next state, acts on the most recent state it
already holds, and reads replies without waiting. Both modes are compiled from
the same source behind `CTRL_PIPELINED` in `firmware/main/tasks.h`, so the
comparison is a rebuild and both remain measurable.

| Over 59,650 loops, ten minutes | Synchronous | Pipelined |
|---|---|---|
| Jitter p99 | within 25 us | within 25 us |
| `rtt_max_us` (see note) | 7,405 us | 77 us |
| Reply timeouts | 6 | 0 |
| Steps on a stale state | not applicable | 8 |
| Malformed or lost frames | 0 | 0 |

**Correction, 2026-09-11.** This section used to say "the round trip falls by
a factor of 96". That compares two different quantities. The firmware computes
`rtt_max_us` as the time from stamping and sending the current request to
reading a reply (`firmware/main/tasks.c`). In the synchronous loop the reply
read is the answer to that request, so 7,405 us is a real round trip. In the
pipelined loop the reply read is the answer to the *previous* request, usually
already buffered, so 77 us is how long it took to read a waiting reply, not a
round trip. The real pipelined round trip was not measured. What stands is the
reason for the change: the loop no longer waits for the host inside its own
slot. Timing is unchanged, which is the expected result: the loop was never the
problem.

**Eight events remain, and the gate still fails.** What changed is what an
event costs. In the synchronous loop a miss meant the control task had spent
9 ms of its 10 ms slot waiting and received nothing, so the loop itself was at
risk. In the pipelined loop a miss means the controller acted on a state one
period older than intended and the loop was never in danger. Same criterion,
different failure.

Zero over ten minutes at 100 Hz against a general-purpose operating system may
simply not be reachable. That is worth stating as a finding rather than
treating as a defect to be engineered away.

One implementation note, because it wasted a build. `link_read_frame` treats a
zero timeout as an already-expired deadline and returns without reading
anything, so the first pipelined build marked every one of 11,650 steps stale.
The poll is now bounded at 1 ms of the 10 rather than zero.

## The decision this calls for

Recorded in the spec's open items for G3 to settle, not taken here.

The fix that matched the diagnosis has been built and is measured above. It
decouples the control period from host latency, and eight events in 59,650
loops survive it.

What the gate should now distinguish is the question it was trying to ask. A
loop that misses its own deadline is a defect, and there are zero of those: the
control task met every deadline in both modes. A host that answers late is a
property of running the plant on macOS, and there are eight of those, bounded
and handled. Reading both as the same failure makes the criterion unable to
tell a working system from a broken one.

It is worth noting that this is already the project's own subject matter.
Claim C5 is deadline-aware execution with quantified degradation, and ablation
A4 is deadline-miss handling on against off. A rig that never missed a deadline
would leave A4 with nothing to measure. Six misses in 59,650 loops is a
measured miss rate to design that handling against, and the fallback path is
already scheduled for Week 7.

What must not happen is the criterion being loosened to fit the result. The
plant validation criterion was revised once at G2 with the reason recorded, and
that permission is spent. This one stays as written until the fix is built and
the run repeated.

## Figures

- `figures/g3-jitter.png`: the loop-period distribution over ten minutes, and
  its cumulative form against the gate limit

## Reproducing

```bash
./scripts/g3_campaign.sh 10
PYTHONPATH="src:." python3 scripts/plot_g3.py
```

The reset and the measurement run as separate processes on purpose. Measured on
this machine: resetting through esptool and then opening the port from a
separate process reads frames every time, and doing both from one process reads
zero bytes every time, at any baud and after any delay. Separately, the first
connection after a reset always reads nothing and the second reads the full
stream, so `SerialLink.open` retries and reports how many attempts it took.

Per-bin counts are in `docs/g3-jitter-histogram.csv` and the full record in
`docs/g3-loop-timing.json`.
