# Build toolchain: arduino-cli against an ESP-IDF firmware

**Raised:** 2026-09-02, by instruction: build with `arduino-cli`, not with
`./scripts/idf.sh`. **Status: OPEN. Nothing has been ported.**

Recorded here rather than acted on, because the change is not a swap of one
build command for another and its cost lands on measurements that are already
in the paper.

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

## The question to settle

Two readings of the instruction, with very different scope:

1. **Flash and monitor with arduino-cli, keep building with the IDF.** Cheap,
   changes no measurement, and gets rid of the fragile part -- the IDF sitting
   under a path with spaces, in a directory named for a C6, with a
   non-executable `tools/idf.py`, which is the whole reason
   `scripts/idf.sh` exists. Note that flashing an IDF-built app still wants
   `esptool` with the bootloader and partition table, so this means
   `arduino-cli upload` is not a drop-in either; `esptool.py` is.
2. **Port the firmware to the Arduino core.** A rewrite of `main.c` and
   `tasks.c`, a new home for the build switches, and a re-measurement campaign
   for G1, G3 and G5 before anything can be cited.

Reading 1 is assumed until told otherwise, and even it is not free. Nothing
has been changed either way.
