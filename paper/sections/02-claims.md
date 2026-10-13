# Claims for Section III (sec:platform)

| Number | Fragment | Source | Label |
|---|---|---|---|
| 10 ms, 100 Hz | control period | firmware/main/tasks.h CTRL_PERIOD_MS | MEASURED |
| 11 floats, 44 B; 4 values, 16 B | state and actuation frames | tasks.h STATE_PAYLOAD_BYTES, ACT_PAYLOAD_BYTES; src/evpil/protocol.py | n/a |
| 1 ms read window; 5 stale steps to limp | pipelined read, limp | tasks.c link_read_frame(...,1); tasks.h STALE_LIMIT_STEPS | n/a |
| two LX7 cores, 240 MHz, 8 MB PSRAM, N8R8 | target | docs/hardware-inventory.md; docs/g1-compute-budget.md raw lines | MEASURED |
| 344,268 B | free internal heap | docs/g1-compute-budget.md EVPIL-BOARD internal_free | MEASURED |
| core 0 / core 1; 10 Hz, 10 Hz, 2 Hz | tasks | tasks.c xTaskCreatePinnedToCore; tasks.h periods | n/a |
| 13 bins | histogram | tasks.h JITTER_N_BINS | n/a |
| 29.82 million/s | G1 throughput, both builds | docs/g1-arduino.json, g1-compute-budget.md | MEASURED |
| 36.46 to 35.03 ms | forecaster benchmark | docs/g5-latency.md; docs/g5-arduino.json | MEASURED |
| 0.121 to 0.123 ms | policy latency | docs/week10-arduino-port.md | MEASURED |
| 25 µs, 0 late | p99, ctrl_late both builds | docs/g3-loop-timing.json, g3-loop-timing-arduino.json | MEASURED |
| 3.30 ms, 6.1x | G1 margin | docs/g1-compute-budget.md | MEASURED |
| 1 of 7, 0.45 points | G2 | docs/g2-plant-validation.md (2.45 vs 2.00 pp, TripB08) | SIMULATED |
| 10%, 2 points | G2 criterion | docs/g2-plant-validation.md | SIMULATED |
| 14.5%, 10% | G4 weakest arm, criterion | docs/forecast-ladder.md | SIMULATED |
| 28,894 B, 300 KB | G5 memory | docs/g5-latency.md | MEASURED |
| 59,650 loops, 61 µs, 9 dropped, 1 limp | first Arduino run | docs/g3-loop-timing-arduino.json | MEASURED |
| 121,208 frames, 0 bad, 0 lost | host side | same, host block | MEASURED |
| 6 timeouts, 7,405 µs | synchronous loop | docs/g3-loop-timing.json / .md | MEASURED |
| 16,4,6,9,9; 44; 298,250; 8.8; 6.4 to 11.8 | repeats | docs/g3-repeat-arduino-1..5.json; docs/week10-arduino-port.md | MEASURED |
| 5,965 of 5,965 | policy steps | same repeat files actor_steps | MEASURED |
| 36 runs; seeds 0,1,2; offsets 100, 200 | campaign | docs/week10-pil-campaign.md; src/evpil/control/scenarios.py; scripts/run_b7_pil.py | MEASURED |
| 2.12e-06, same checksum | actor parity | docs/week10-arduino-port.md | MEASURED |
| 21 to 54 dropped frames, 4 cells | disturbed | docs/week11-plant-correction.md | MEASURED |
| 16 frames, 8 cells | set aside | docs/week14-fused-backup-traffic-repeats.md | MEASURED |

## Mismatches
- BRIEF says 99.9% within 25 µs; JSON shows all 59,650 loops in the first bin (p99.9 25 µs). Text says every loop.
- Period range (9,729 to 10,001 µs) in the JSON is a since-boot extreme including start-up; the gate uses the differenced histogram (scripts/run_g3.py). Not quoted.
- G3 "dropped" = rx_timeouts + rx_bad + stale_steps + host frames_dropped; host frames_dropped is 0 in all runs, so all events are late replies seen by the target.
- stale_worst (277 to 288) is a since-boot maximum including start-up; not quoted.
- G5 36.46 ms is the vendor-framework build; Arduino build is 35.03 ms. Both given.
- "Dropped" counts: report gives 3 (vendor) and 9 (Arduino); not compared as a rate change (record: open).

## Gaps
- G5 is the deployed graph with fixed weights, not a converted trained model (docs/g5-latency.md); stated in text.
- Supply current on the Arduino image not measured; stated.
- Jitter figure is from the CSV files; no external (logic analyser) timing was used in these records.

## Linter and words
prose_lint: 1245 prose words, 65 sentences, clean, no machine-writing tells. Body words excluding headings, table and caption lines: about 1190.
