# Build toolchain: arduino-cli against an ESP-IDF firmware

**Raised:** 2026-09-02, by instruction: build with `arduino-cli`, not with
`./scripts/idf.sh`.
**Settled:** 2026-09-02. **Decision: port to the Arduino ESP32 core**, taken by
the supervisor when the two readings below were put as a question.

**The port is done and the re-measurement campaign it forces has been run.**
Results in `docs/week10-arduino-port.md`. Build with
`scripts/arduino_build.sh`. Every gate measured on silicon was taken again
against the Arduino build; no verdict changed and the largest movement in any
measured quantity is 3.9%.

The rest of this note is kept as written, before the port, because it is the
argument the decision was taken against. Two of its claims did not survive
contact with the measurements and are corrected here rather than edited out:

1. It said G1, G3 and G5 "have to be run again on the board before the paper
   can cite them". Correct, and they were. What it implied, that the numbers
   would move, was wrong. G1 agrees to four significant figures, G5 moves
   3.9%, and G3's verdict, its jitter distribution and its `ctrl_late` count
   are unchanged.
2. Its cost table is complete as a list of what needed re-measuring, except
   that it omits the SAC actor on chip. That was re-measured too: same weight
   checksum, same agreement with numpy, 1.7% slower.

One claim it made stands and matters more than it looks. The radios really
cannot be configured out of the Arduino core. Nothing starts them and the
timing shows no sign of them, but supply current was not re-measured on this
image, and the design spec's constraint is about current as well as timing.

## What is installed

| | |
|---|---|
| arduino-cli | 1.5.1 (Homebrew) |
| ESP32 core | `esp32:esp32` 3.3.7 (3.3.11 available) |
| ESP32-S3 FQBN | `esp32:esp32:esp32s3` |
| ESP-IDF | v5.4, at `~/Desktop/Espressif 32 C6 Dev-Kit/esp-idf-v5.4` |

Both toolchains are present and working. The IDF build succeeded on
2026-09-02, including in the A4 ablation configuration.

## Why this is not a one-line change

`firmware/` is a native ESP-IDF application, not a sketch. arduino-cli
compiles a `.ino` in a directory of the same name and does not consume any of
the following:

| What the firmware relies on | Where it lives | What arduino-cli does with it |
|---|---|---|
| IDF component build | `firmware/CMakeLists.txt`, `firmware/main/CMakeLists.txt` | not read |
| Radios off, and the rest of the sdkconfig | `sdkconfig.defaults` | not read; the Arduino core ships its own compiled-in config with WiFi and BT present |
| Ablation and fault-injection switches | `-DFAULT_INJECT=1\|2`, `-DFALLBACK_ENABLED=0`, `-DCTRL_PIPELINED=0` | no equivalent; arduino-cli has `--build-property` but no per-variant target |
| `app_main`, explicit task creation and core pinning | `main.c`, `tasks.c` | the core supplies its own `app_main` and starts `loopTask` on core 1 |

The radio point is not a detail. `sdkconfig.defaults` disables WiFi and
Bluetooth because the radio corrupts both supply-current and timing
measurements -- that is a stated global constraint of the design spec, and the
G1, G3 and G5 numbers were all taken under it.

## What it would cost

Every gate measured on the device was measured on the IDF build:

| Gate | Measured | Would need re-running |
|---|---|---|
| G1, int8 throughput | 3.30 ms, 6.1x margin, 2026-08-30 | yes |
| G3, loop timing | 59,650 loops, jitter p99 25 us, `ctrl_late` 0 | yes |
| G5, latency budget | actor 0.121 ms, forecaster 36.46 ms | yes |

A different scheduler configuration and a different compiled-in sdkconfig
produce different timing, so none of those numbers transfer across the port by
argument. They would have to be taken again, on the board, which is not
attached.

## The question that was settled

Two readings of the instruction were put to the supervisor, with very different
scope:

1. **Flash and monitor with arduino-cli, keep building with the IDF.** Cheap,
   changes no measurement.
2. **Port the firmware to the Arduino core.** A rewrite of the build, a new
   home for the switches, and a re-measurement campaign for G1, G3 and G5
   before anything can be cited.

**Reading 2 was chosen.** In the event the port needed no rewrite of `main.c`
or `tasks.c` at all: the Arduino core is ESP-IDF underneath, so every IDF
header the firmware uses is still there, and `tasks.c` already handled a task
watchdog that someone else had initialised, which is exactly the Arduino
situation. What it needed was a build script, three build-system
reconciliations, and the campaign. See `docs/week10-arduino-port.md`.
