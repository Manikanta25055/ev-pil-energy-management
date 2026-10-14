# EXPERIMENTAL PLATFORM AND METHOD {#sec:platform}

Every result in the paper carries one of two labels. MEASURED means the quantity was recorded while the code ran on the microcontroller; SIMULATED means it came from the host alone. Table @tab:platform-gates lists every criterion fixed in advance with its outcome, and Table @tab:platform-revisions every rule or revision made after results were seen.

## Processor-in-the-Loop Arrangement

The arrangement is processor-in-the-loop (PIL), not hardware-in-the-loop. The processor is real: an ESP32-S3 runs the control firmware, receives its inputs over a serial link and must answer before a wall-clock deadline [@esp32s3]. A host laptop simulates the vehicle, motor, inverter, battery, driver and sensors. Faults are injected in software. The part is a general-purpose microcontroller, not an automotive-qualified one (Section @sec:discussion).

In each 10 ms period (Fig. @fig:platform-architecture) the target, as clock master, sends a step request. The host adds seeded sensor noise to the plant state and replies with a frame of 11 floating-point values. The target returns four: torque, regeneration blend, power limit and auxiliary derate. The host steps the model and logs the result.

The firmware can block inside the slot until the reply arrives (synchronous mode) or act on the latest state already held and read replies for at most 1 ms (pipelined mode). The pipelined mode is the one reported here. The controller therefore acts on a measurement 10 ms old.

![fig:platform-architecture](paper/figures/fig-platform-architecture.png){width=page}
Caption: Processor-in-the-loop arrangement. The host side is simulated; the target side is real. The forecaster was benchmarked on the target but is not part of the shipped image.

## Target Hardware and Firmware

The target has two Xtensa LX7 cores at 240 MHz and 8 MB of PSRAM, and its FreeRTOS firmware runs four tasks. The 100 Hz speed loop has core 0 and the highest priority. It combines a PID controller with a physics feedforward and, in some builds, a speed estimator and fault detector. Core 1 hosts the energy manager and an inference task at 10 Hz and a diagnostic task at 2 Hz, so inference cannot delay control.

Which energy manager runs is a compile-time choice: the firmware builds the learned policy when its generated weight header exists and the rule-based manager otherwise. A campaign therefore needs one image per controller, and a diagnostic counter of policy steps, which cannot be non-zero in the rule-based image, confirms the choice.

The firmware was first built with the vendor framework and later moved to the Arduino core, which yields a different binary from the same source, so every gate was measured again. Throughput stayed at 29.82 million integer multiply-accumulates per second. The forecaster took 35.03 ms instead of 36.46 ms; the policy took 0.123 ms instead of 0.121 ms. The Arduino image carries radio stacks that cannot be removed. Nothing starts them, but supply current was not re-measured on this image.

## Real-Time Behaviour

Gate G3 was measured over 59,650 control loops, ten minutes, against the target's own clock. On the first Arduino-core run every loop landed within 25 µs of its slot, the worst control computation took 61 µs and no loop missed its deadline (Fig. @fig:platform-jitter).

![fig:platform-jitter](paper/figures/fig-platform-jitter.png){width=col}
Caption: Deviation of the control period from 10 ms on the Arduino-core build (MEASURED). Empty bins are marked 0. The five pooled runs use the shipped image with the learned policy.

The frame criterion fails. A dropped frame is a reply that misses the 1 ms window. The first run had 9. The link itself was clean. All 121,208 frames arrived, none malformed or lost, and the record attributes the misses to the host operating system answering late in bursts. Torque is ramped down only after more than five consecutive stale steps. That happened once.

Five repeats of the shipped image gave 16, 4, 6, 9 and 9 dropped frames, or 8.8 per run with a Poisson 95% interval of 6.4 to 11.8; the events cluster, so the true interval is wider. Late control steps were 0 in every run. The criterion was not loosened. Zero drops against a non-real-time host may simply not be reachable.

A stale state could bias the energy comparison of Section @sec:ems. Across the 16 valid settings, the learned-minus-rules difference in dropped frames correlated with the energy difference at r = -0.03; no relation shows at this sample size, though a small effect is not excluded.

## Terms and Repetition

An arm is a controller under test, and a setting (or cell) is one scenario level; the campaign sweeps six factors one at a time from a US06 baseline, at three levels each, for 36 runs across two arms. The two nonzero communication-delay settings, four runs, were excluded afterwards (Table @tab:platform-revisions), leaving 32 runs in 16 valid settings. Five of the 16 are the same nominal US06 condition reached from different factors; the valid set holds 12 distinct conditions.

Energy is reported on the comparable scale: cabin heating that a controller sheds is added back at the energy it saved, and arms are ranked on the sum in Wh/km. Raw consumption would reward switching the heating off.

Seed 0, 1 or 2 is paired with the three levels of each factor and both arms receive the same draw, so within a factor the noise level is confounded with the seed, and the five nominal repeats hold at most three distinct draws. The plant and both controllers are deterministic, which means a repeat with the same seed replays the same noise draw and differs mainly in link timing, so it is not an independent repeat of anything the noise drives. The later fault campaign adds seed offsets of 100 and 200.

Anything written twice, in Python and in C, has a parity test that drives both through the same inputs; a policy network of the deployed shape, exported from an earlier seed, matches its NumPy original to 2.12e-06 with an identical weight checksum. The host is kept idle during a campaign.

## Criteria Fixed in Advance, and What Was Decided Afterwards

A criterion is written down before the experiment it governs. A result that misses it is reported as a miss. The version history gives the dates. The five gate criteria were committed on 2026-08-30 with the design specification, before the commit that records the first gate measurement later that day. The criteria for the speed estimator and the first fault detector were committed on 2026-10-06, before any arm was run. Those for the bias-aware detector were committed on 2026-10-08 in the same commit as its code, so they preceded every learned reviewer but not the detector itself, whose step threshold was tuned on training data only.

Table @tab:platform-gates holds every such criterion in the paper. Five are missed. They are G2, the zero-drop part of G3, the estimator's clean-tracking bound, the first detector's false-alarm limit and the bias-aware detector's simulated detection limit. The comparison of the two energy managers had no outcome criterion; its acceptance rule, dated 2026-09-21, required only that the 36 runs be recorded, and no later record adds one, so the comparison is descriptive (Section @sec:ems). Gate G4 was passed by a ridge regression before any proposed forecaster existed, which makes passing it weak evidence for the proposed model.

Table: tab:platform-gates | Every criterion fixed in advance in the paper, with the date of its record and its outcome. | width=page
| Id | Criterion fixed in advance | Fixed | Outcome | Label |
|---|---|---|---|---|
| G1 | 0.1 M multiply-accumulates in 20 ms or less | 2026-08-30 | Pass: 3.30 ms from measured throughput, margin 6.1x | MEASURED |
| G2 | Power RMSE within 10% of mean; final SOC within 2 points | 2026-08-30 | Fail on 1 of 7 trips: SOC 2.45 against 2.00 | SIMULATED |
| G3a | 99th-percentile period jitter of 1 ms or less | 2026-08-30 | Pass: 25 µs | MEASURED |
| G3b | Zero dropped frames in 10 min | 2026-08-30 | Fail: 4 to 16 per run | MEASURED |
| G4 | 10% lower RMSE than persistence at 3 s | 2026-08-30 | Pass: 14.5% for the weakest fitted model | SIMULATED |
| G5 | 40 ms or less; model plus arena 300 KB or less | 2026-08-30 | Timing and memory pass: 36.46 ms, 35.03 ms; 28,894 B. Converted model not yet run on target | MEASURED |
| Ablations | Null result accepted in advance for physics loss and for forecast in the policy state | 2026-08-30 | Both null; forecast ablation on the corrected model +0.262 Wh/km, interval -0.698 to +0.982 | SIMULATED |
| Speed estimator | Clean energy within 0.2% of the baseline loop | 2026-10-06 | Pass | MEASURED |
| Speed estimator | Clean tracking within 0.005 m/s of the baseline loop | 2026-10-06 | Fail: 0.0193 against 0.0104 m/s on UDDS | MEASURED |
| Speed estimator | At least half of the 10x-noise penalty recovered | 2026-10-06 | Pass: 9.44 to 0.24 Wh/km | MEASURED |
| Speed estimator | Tracking below 0.1 m/s in every cell | 2026-10-06 | Pass | MEASURED |
| First detector | No false alarm on a healthy sensor | 2026-10-06 | Fail: 1 false alarm on the target | MEASURED |
| Bias-aware detector | Every named fault flagged within 0.5 s; under 1 false alarm per clean hour | 2026-10-08 | Not met: 551 and 533 of 560 caught | SIMULATED |
| Bias-aware detector | Same limits on the target | 2026-10-08 | Met on cases run: 120 of 120 within 0.32 s; 0 alarms in 1 clean hour | MEASURED |

Table @tab:platform-revisions records each rule or revision made after results were seen. The re-run rule and the delay exclusion are judgement calls. The origin of the 16-frame threshold is not recorded; it equals the largest count among the five G3 repeats, but the record does not say it came from them.

Table: tab:platform-revisions | Rules and revisions made after results were seen. | width=page
| Change | Recorded | Prompt | Effect |
|---|---|---|---|
| G2 split into three parts | 2026-08-30 | Pooled form failed all 7 trips | Both thresholds kept, a torque bound added; gate fails 1 of 7 |
| Delay settings excluded | 2026-09-21 | Neither arm followed the cycle (25.7 to 43.4 m/s) | Rule: tracking error 1 m/s or more; 4 of 36 runs dropped |
| Re-run above 16 dropped frames | 2026-10-07 | Four rule cells run beside other jobs (21 to 54) | Looser than G3; 8 cells later set aside |
| Plant fix and added checks | 2026-10-06 | Anomalies in campaign tables, not a gate | 8.28% gain withdrawn; limit-invariance sweep and optimum check added |
| Second fault detector | 2026-10-08 | First detector assumed an acceleration channel that logged trips did not match | Offset state added; criteria recorded with it |
| Fused backup speed | 2026-10-09 | Checker with rule monitor failed on a heavier car | 18 candidates on one training cycle; rule fixed before runs |
