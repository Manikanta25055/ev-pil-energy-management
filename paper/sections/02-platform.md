# EXPERIMENTAL PLATFORM AND METHOD {#sec:platform}

Every result in the paper carries one of two labels. MEASURED means the quantity was recorded while the code ran on the microcontroller; SIMULATED means it came from the host alone.

## Processor-in-the-Loop Arrangement

The arrangement is processor-in-the-loop (PIL), not hardware-in-the-loop. The processor is real: an ESP32-S3 runs the control firmware, receives its inputs over a serial link and must answer before a wall-clock deadline [@esp32s3]. The vehicle, motor, inverter, battery, driver and sensors are simulated on a host laptop. Faults are injected in software.

Fig. @fig:platform-architecture shows one control period. The target is the clock master. Every 10 ms it stamps and sends a step request. The host builds a measurement from the plant state, adds seeded sensor noise to the measured channels and replies with a state frame of 11 floating-point values. The target runs its control code and returns an actuation frame of four values: torque, regeneration blend, power limit and auxiliary derate. The host advances the vehicle model by 10 ms with them and logs the outcome.

The firmware can run in a synchronous mode, which blocks inside the slot until the reply arrives, or in a pipelined mode, which requests the next state, acts on the latest one already held and reads replies for at most 1 ms. The pipelined mode is the default and the one reported here. It costs one period of age on the state used at each step, so the controller acts on a 10 ms old measurement.

![fig:platform-architecture](paper/figures/fig-platform-architecture.png){width=page}
Caption: Processor-in-the-loop arrangement. The host side is simulated; the target side is real. The forecaster was benchmarked on the target but is not part of the shipped image.

## Target Hardware and Firmware

The target is an ESP32-S3 with two Xtensa LX7 cores at 240 MHz and 8 MB of in-package PSRAM on an N8R8 development board; in the stand-alone compute benchmark, 344,268 bytes of internal heap were free at start-up. Firmware runs under FreeRTOS with four tasks. The speed loop runs at 100 Hz on core 0 at the highest priority; it combines a PID controller with a physics feedforward and, in some builds, a speed estimator and sensor-fault detector. Core 1 hosts an energy-management task at 10 Hz, an inference task at 10 Hz and a diagnostic task at 2 Hz, so that inference cannot delay control. A task watchdog guards the loops.

Which energy manager runs is a compile-time choice. The firmware builds the learned policy when its generated weight header exists and the rule-based manager otherwise; no frame can switch it. A campaign therefore needs one image per controller, and the choice is confirmed through the diagnostic counter that records how many outer steps the policy answered. That counter cannot be non-zero in the rule-based image.

Frames carry a sequence number, a microsecond timestamp and a 16-bit cyclic redundancy check. The diagnostic frame returns counters for late control steps, stale steps, reply timeouts, policy steps and worst-case execution times, with a 13-bin histogram of period deviation.

The firmware was first built with the vendor framework and later moved to the Arduino core, which produces a different binary from the same source. Every gate was measured again for that reason. Integer multiply-accumulate throughput on the Arduino core was 29.82 million per second. The forecaster benchmark fell from 36.46 to 35.03 ms, the policy rose from 0.121 to 0.123 ms, and the 99th-percentile period deviation stayed at 25 µs with no late control step on either build. The Arduino image contains radio stacks that cannot be removed. Nothing starts them, but supply current was not re-measured on this image.

## Acceptance Gates

Five gates were written, with pass criteria and an action on failure, before the experiment each one governs. Table @tab:platform-gates lists each gate with its result as recorded. The plant criterion was revised once, after its original pooled form failed on all seven validation trips: it was split into three parts, both original thresholds were kept, and one new threshold was added (Section @sec:plant). No other criterion was altered.

Table: tab:platform-gates | Acceptance gates, criteria fixed in advance and results as recorded. | width=page
| Gate | Question | Criterion fixed in advance | Result |
|---|---|---|---|
| G1 | Is the compute budget feasible? | 0.1 M multiply-accumulates in 20 ms or less on core 1 | Pass: 3.30 ms from measured throughput, margin 6.1x |
| G2 | Does the plant reproduce held-out trips? | Battery-power RMSE within 10% of mean power; final SOC within 2 points | Fails on 1 of 7 validation trips |
| G3 | Does the 10 ms loop close on the target? | 99th-percentile jitter at most 1 ms; zero dropped frames in 10 min | Timing passes (25 µs); frame criterion fails |
| G4 | Does a model beat persistence? | At least 10% lower RMSE at 3 s on validation | Pass: weakest fitted model 14.5% |
| G5 | Does the forecaster fit on the target? | Within 40 ms; model plus arena at most 300 KB | 36.46 ms (vendor build), 35.03 ms (Arduino core); 28,894 B |

In Table @tab:platform-gates, RMSE is root-mean-square error and SOC is state of charge. G1 and G5 are MEASURED on the target. G2 is SIMULATED against logged trips, with the failing trip missing the SOC bound by 0.45 points (Section @sec:plant). G4 is scored offline on validation data (Section @sec:forecast). The G5 figure times the deployed graph in scalar integer code with fixed weights; it does not run a converted trained model.

## Real-Time Behaviour

G3 was measured over ten minutes, 59,650 control loops, with the target keeping time against its own clock. On the first Arduino-core run every loop landed within 25 µs of its slot, the worst control computation took 61 µs and no loop was late against its own deadline. Fig. @fig:platform-jitter shows the distribution: all counts sit in the first bin, and the tolerance line lies far to the right of them.

![fig:platform-jitter](paper/figures/fig-platform-jitter.png){width=col}
Caption: Deviation of the control period from 10 ms on the Arduino-core build (MEASURED). Empty bins are marked 0. The five pooled runs use the shipped image with the learned policy.

The frame criterion fails. A dropped frame is counted whenever a reply does not arrive within the 1 ms read window, and the first run had 9. The link carried every frame intact: 121,208 frames were received with none malformed or lost, and the target counted no malformed frame. The record attributes the misses to the host, a general-purpose operating system answering late in short bursts. In the earlier synchronous loop the same cause produced 6 reply timeouts, with a worst round trip of 7,405 µs. A missed reply now means one step on a state one period older than intended, and torque is ramped down only when more than five consecutive steps are stale; this happened once in the first run.

The shipped image was repeated five times. Dropped frames per run were 16, 4, 6, 9 and 9, which is 44 in 298,250 loops, or 8.8 per run with a Poisson 95% interval of 6.4 to 11.8; the events cluster, so the true interval is wider. Late control steps were 0 in every run, the 99th-percentile deviation was 25 µs in every run and the policy answered 5,965 of 5,965 outer steps each time. The criterion was not loosened, and zero drops over ten minutes against a non-real-time host may not be reachable.

## Provenance and Repetition

Each result is tied to the file that produced it and to a label. Campaign cells carry fixed noise seeds: in the 36-run campaign, seed 0, 1 or 2 is paired with the three levels of each scenario axis, and both controllers receive the same draw. The plant and both controllers are deterministic, so without a seeded noise term the three seeds would return identical numbers. For the same reason a repeat with the same seed is not a repeat of anything driven by the noise draw; it replays the draw and varies mainly link timing. Repeats of the fault campaign add seed offsets of 100 and 200.

Anything written twice, in Python and in C, is checked by a parity test that drives both implementations through the same inputs and compares them step for step. This covers the frame format, the order of state fields, the speed controller, the estimator, the fault detector and the decoding of policy actions. The deployed policy matches its NumPy original to 2.12e-06 on the Arduino build with an identical weight checksum.

The host machine is kept idle during a campaign. Four rule-based cells first run beside other jobs recorded 21 to 54 dropped frames, while late control steps stayed at 0. Cells above 16 dropped frames are set aside and run again. In the later fault campaign, 8 cells were set aside for this reason.
