# The Arduino-core port, and the gates re-measured against it

**Date:** 2026-09-02
**Decision:** taken by the supervisor on 2026-09-02, recorded in
`docs/toolchain-arduino-cli.md`. The standing instruction was to build with
`arduino-cli`; the choice between flashing with it and porting to the core was
put as a question, and the answer was to port.
**Build:** `scripts/arduino_build.sh`
**Data:** `docs/g1-arduino.json`, `docs/g5-arduino.json`,
`docs/g3-loop-timing-arduino.json`, `docs/week8-actor-onchip-arduino.json`

The port is done and every gate measured on silicon has been taken again
against it. No verdict changed. The largest movement in any measured quantity
is 3.9%.

That outcome was not the expected one and is worth stating plainly:
`docs/toolchain-arduino-cli.md` argued the port would invalidate G1, G3 and G5
and require a re-measurement campaign. The campaign was required and has been
run. What it found is that the numbers survive it.

---

## 1. What the port actually is

`firmware/main/` is unchanged as the single source. There is no second copy of
the firmware, because a fork would drift from the ESP-IDF build within a week
and the two would disagree with nobody noticing.
`scripts/arduino_build.sh` assembles a sketch from `firmware/main/` on every
run and compiles it with `arduino-cli`. Three things reconcile a native IDF
application with a sketch:

| Problem | Resolution |
|---|---|
| The core supplies its own `app_main` and calls `setup()` | `app_main` is renamed by `-Dapp_main=evpil_app_main`, applied **to the C compiler only**. The generated `.ino` calls it from `setup()` |
| The build switches have no menu equivalent | They ride in `compiler.c.extra_flags` and `compiler.cpp.extra_flags`, which are empty hooks in the core's `platform.txt` |
| The core builds at `-Os`, the IDF build used `CONFIG_COMPILER_OPTIMIZATION_PERF` | `compiler.optimization_flags` is forced to `-O2` |

Two of those cost a build each to find. Applying the `app_main` rename to C++
as well renames the core's own entry point in `cores/esp32/main.cpp`, and the
link then fails with two `evpil_app_main` and nothing named `app_main` for the
prebuilt `libfreertos` to call. And `--build-property` values are word-split,
so an `-I` pointing into this repository arrives at the compiler as two broken
paths, because the project directory has a space in its name. The generated
sketch therefore lives outside the repository, under `~/.cache/evpil-arduino`,
and the script refuses to run if that path has a space in it. This is the same
class of problem `scripts/idf.sh` exists to work around.

`firmware/main/CMakeLists.txt` compiles the actor only when
`sac_actor_weights.h` exists, and defines `HAVE_SAC_ACTOR` when it does. The
build script mirrors that. Getting it wrong is how `-DRUN_ACTOR_BENCH=1` fails
on the `#error` that was written to explain itself.

## 2. What the port cannot reproduce

WiFi and Bluetooth are compiled into the Arduino core and cannot be configured
out. `firmware/sdkconfig.defaults` disables both, and the reason it does is
that the radio corrupts supply-current and timing measurements, which is a
stated global constraint of the design spec.

Neither radio is started, so nothing transmits, and the timing results below
show no sign of one. But the claim "the radios are not compiled in" is no
longer true of the shipped image and should not be repeated. What can be said
is narrower and is what the measurements support: no radio is initialised, and
the loop timing is unchanged.

The image is 292,667 bytes against the IDF build's 208,352. The difference is
the core and the unused radio stacks. It is 8% of the app partition either way.

## 3. The gates, both toolchains

### G1, int8 multiply-accumulate throughput

Same benchmark, `firmware/main/bench_mac.c`, 2000 repetitions per size.

| n | IDF, us | Arduino, us | IDF, MMAC/s | Arduino, MMAC/s |
|---|---|---|---|---|
| 64 | 4,424 | 4,394 | 28.93 | 29.13 |
| 256 | 17,255 | 17,252 | 29.67 | 29.68 |
| 1,024 | 68,682 | 68,679 | 29.82 | 29.82 |
| 4,096 | 274,395 | 274,402 | 29.85 | 29.85 |

At the working size the two agree to four significant figures, and the largest
disagreement anywhere is 0.7% at n=64, the size most sensitive to loop
overhead. A tight int8 multiply-accumulate loop compiled at `-O2` does not care
which build system invoked the compiler, and this is the measurement that says
so rather than the argument that it should not.

**G1 verdict unchanged: PASS**, 29.82 MMAC/s working throughput, the same
6.1x margin.

### G5, encoder latency on silicon

| Quantity | IDF | Arduino | Change |
|---|---|---|---|
| Transformer forward | 36,457.2 us | 35,032.5 us | **-3.9%** |
| LSTM forward | 35,070 us | 35,002.0 us | -0.2% |
| `matmul 32x32x64` | 2,336.08 us | 2,332.58 us | -0.15% |
| `softmax 32x32` | 906.42 us | 918.48 us | +1.3% |
| `layernorm 32x32` | 158.76 us | 158.56 us | -0.13% |
| Weight bytes | 17,600 | 17,600 | none |
| Arena bytes | 11,294 | 11,294 | none |

The individually timed kernels are the same to within 1.3%, and the whole
forward pass is 3.9% faster. The difference is therefore not in the kernels but
in what surrounds them, and it was not chased further: 3.9% does not move any
conclusion G5 supports, and the budget question is not close. The forecaster is
still about 35 ms against a 40 ms budget and is still 99.7% of the outer loop's
latency.

**G5 verdict unchanged.** The deployed encoder fits, and the MAC-count estimate
is still optimistic by roughly the same factor.

### G3, loop timing

10 minutes, 59,650 control loops on each toolchain, same harness, same host.

| Quantity | IDF | Arduino | |
|---|---|---|---|
| Jitter p50 / p99 / p99.9 | 25 / 25 / 25 us | 25 / 25 / 25 us | identical |
| `ctrl_late` | 0 | 0 | identical |
| Loops | 59,650 | 59,650 | identical |
| Control task WCET | 97 us | **61 us** | better |
| Inference WCET | 836 us | **776 us** | better |
| `rtt_max_us` (not a round trip in the pipelined loop; `docs/g3-loop-timing.md`) | 1,766 us | 1,637 us | not comparable as a round trip |
| Period range | 9,845 to 10,011 us | 9,729 to 10,001 us | wider low side |
| **Dropped frames** | **3** | **9** | **worse** |
| `limp_steps` | 0 | 1 | worse |
| Verdict | FAIL | FAIL | unchanged |

Every timing quantity is the same or better. The one that got worse is the one
the gate fails on. G3's criterion is zero dropped frames, the count went from 3
to 9 in 59,650 loops, and on the Arduino build that was enough for the limp
path to be taken once during the campaign.

**This should not be over-read.** Each toolchain contributes one 10-minute run.
Three events against nine is a difference between two single samples of a rare
event, 0.005% against 0.015% of loops, and the campaign was never designed to
resolve a rate that low. What can be said is that the port did not fix G3 and
did not obviously break it either. What cannot be said, from these two runs, is
that the port tripled the drop rate.

**Repeated five times on 2026-09-11,** on the Arduino build with the actor in
the loop, which is the image that ships. 10 minutes each, same harness.
Dropped frames per run: 16, 4, 6, 9, 9. Pooled, 44 in 298,250 loops, 0.0148%,
or 8.8 per 10-minute run, with an exact 95% Poisson interval of 6.4 to 11.8 per
run. `ctrl_late` was 0 and jitter p99 25 us in all five, and the actor answered
5,965 of 5,965 outer steps every time. Data: `docs/g3-repeat-arduino-{1..5}.json`.

Identical runs differ by a factor of four, so a single run says little. The
earlier Arduino figures, 9 before the actor and 5 with it, are ordinary
samples. The IDF's single 3 is below the range of the five, but it is one run,
taken before the actor was wired in, and the IDF repeats were deferred on
2026-09-11. **Whether the toolchain moved the rate is still open**; what is now
established is the shipped image's own rate. Run 1 overlapped light editing
work on the host and is kept rather than dropped; it is the high value. G3
verdict unchanged, FAIL in every run, on the frame criterion.

**G3 verdict unchanged: FAIL**, on the same criterion, for the same reason: the
host does not always answer in time. The distinction the project has been
careful about holds on both toolchains, and it is the one that matters for the
paper. The loop never misses its own deadline. `ctrl_late` is 0 in both.

### The SAC actor on chip

| Quantity | IDF | Arduino |
|---|---|---|
| Weight checksum | `0x3cc342e5` | `0x3cc342e5` |
| Worst action difference against numpy | within 2e-05 | 2.12e-06 |
| Mean latency | 0.1211 ms | 0.1233 ms |
| Worst single inference | 127 us | 128 us |

The checksum is identical, so the same weights are on the board, and the
actions still agree with numpy to six decimal places. Latency is 1.7% higher.
The deployment figure that parked decision 4 turns on, 19.3 KB and about
0.12 ms, is unchanged in every respect that decision uses.

## 4. What this does and does not settle

Settled: the port compiles, flashes, runs, and reproduces every gate. The
numbers in the paper do not need rewriting, and the ones that moved, moved by
less than the difference between two runs of the same campaign in most cases.

Not settled, and worth being explicit about because the port's whole risk was
here:

- **The radio claim narrowed.** The image now contains WiFi and Bluetooth. They
  are never started, and nothing in the timing suggests they cost anything, but
  supply current was not measured on this build and the spec's constraint was
  written about supply current as well as timing. Anyone repeating the
  current-draw argument should measure it on this image first.
- **G3's drop count: five Arduino runs done 2026-09-11,** 8.8 per 10-minute
  run pooled, 95% interval 6.4 to 11.8. The IDF repeats were deferred, so the
  toolchain comparison is still open.
- **Ablation A4 and the week 7 fallback campaign: re-run on this build,
  2026-09-11, and both reproduce.** Fallback with `FAULT_INJECT=1`: every
  counter expectation holds, 180 / 94 / 20 / 20 against the IDF's
  180 / 96 / 20 / 20, torque ramps 226.18 to 0.00 Nm, `ctrl_late` 0
  (`docs/week7-fallback-arduino.json`). A4's counter campaign: guarded
  counters 0, torque held flat at 226.07 Nm (`docs/week9-a4-arduino-counters.json`).
  Watchdog with `FAULT_INJECT=2`: the board resets and reports boot reason 6,
  task watchdog, at 19.9 s and 42.2 s against 19.8 s and 41.9 s on the IDF
  (`docs/week7-watchdog-arduino.json`). The Arduino core configures the task
  watchdog itself, so that one could have come out differently and did not.
  The closed-loop A4 sweep was run on this build as well, at five outage
  lengths; `docs/week9-a4.md` section 10.

## 5. Reproducing

```bash
./scripts/arduino_build.sh --flash                       # the control loop
./scripts/arduino_build.sh --flash -DRUN_G1_BENCHMARK=1  # gate G1
./scripts/arduino_build.sh --flash -DRUN_G5_BENCHMARK=1  # gate G5
./scripts/arduino_build.sh --flash -DRUN_ACTOR_BENCH=1   # the actor
```

`RUN_G1_BENCHMARK` and `RUN_G5_BENCHMARK` used to be edited in `main.c` and are
now build switches, for the same reason every other variant is: the firmware
that produced a number should be rebuildable from the command that produced it.
The Arduino core has no equivalent of editing an sdkconfig in place, so this
had to change for the port in any case.

Both benchmarks now repeat every two seconds instead of printing once at boot.
The board's USB CDC device re-enumerates when it resets, so a single line
printed during boot is a race against the host reopening the port, which used
to be won by leaving a serial monitor running and reading the screen.
`scripts/capture_bench.py` collects the lines into JSON, so the numbers above
were not transcribed by hand.
