# Gate G1: int8 compute budget

**Verdict: PASS**, with 6.1x margin on the floor.

Measured 2026-08-30 on the ESP32-S3 identified in `docs/hardware-inventory.md`.

## Raw measurement

```
EVPIL-BOARD cores=2 rev=2 cpu_mhz=240
EVPIL-BOARD internal_free=344268
EVPIL-BOARD psram_size=0
EVPIL-G1 n=64   reps=2000 us=4424   mmac_per_s=28.93
EVPIL-G1 n=256  reps=2000 us=17255  mmac_per_s=29.67
EVPIL-G1 n=1024 reps=2000 us=68682  mmac_per_s=29.82
EVPIL-G1 n=4096 reps=2000 us=274395 mmac_per_s=29.85
```

Throughput rises with `n` and then flattens, exactly the loop-overhead
amortisation the plan predicted. Per the plan, the **n=1024 row is the working
figure**: large enough that loop overhead has amortised, small enough to stay
cache-resident.

**Working throughput: 29.82 MMAC/s.**

## Config table

MAC counts are for the encoder stack only (input embedding and output head
excluded); feed-forward width is 2x d_model.

| Config | seq | d_model | layers | MACs | params | Latency | Verdict |
|---|---|---|---|---|---|---|---|
| Plan-implied | 64 | 64 | 2 | 5,242,880 | 65.5 k | **175.8 ms** | Exceeds the whole 100 ms period |
| **Trimmed** | 32 | 32 | 2 | 655,360 | 16.4 k | **22.0 ms** | **Fits: 55% of the 40 ms G5 budget** |
| Aggressive | 32 | 16 | 1 | 98,304 | 2.0 k | **3.3 ms** | Fits with room to spare |

## Gate evaluation

**G1 floor** — the aggressive config must run 0.1 M MACs in 20 ms or less:
measured **3.30 ms**, a **6.1x margin**. PASS.

**G5 budget** (Phase 2, deployed forecaster within 40 ms on core 1): the
**trimmed config fits at 22.0 ms, using 55% of the allowance**. The
plan-implied config does not fit and is abandoned.

## Decision for Phase 2

**Target the trimmed config: seq 32, d_model 32, 2 layers, ~16 k int8
parameters.**

This is the middle row, not the floor, and it is the right call for three
reasons:

1. It fits the deployed budget with 45% headroom, leaving room for the input
   embedding, output head and framework overhead this measurement excludes.
2. This figure is a **lower bound** (see below), so the real margin is larger.
3. The aggressive config remains the fallback if the excluded overheads turn
   out to be larger than expected.

The plan's fallback ladder (spec section 7.3) is not needed. The budget-first
inversion did its job: the plan-implied architecture would have missed its
deadline by 1.8x, and that is now known in week 1 rather than week 10.

## Why this figure is conservative

Four reasons the deployed number should be **better** than 29.82 MMAC/s:

1. **Scalar C loop.** No ESP-NN vector kernels, no SIMD. The S3's 128-bit
   vector ISA is precisely what ESP-NN's int8 kernels exploit, and it is
   unused here.
2. **Single core.** The measurement uses one core; `infer` gets core 1 to
   itself.
3. **No dual-issue or unrolling tuning.** A plain accumulate loop.
4. **Not the real graph.** Phase 2 measures an actual TFLite-Micro graph,
   which adds framework overhead but gains optimised kernels.

Treating this as a floor is deliberate. A model sized against a conservative
number and then found to run faster is a good outcome; the reverse is not.

## Measurement caveats

- **Built with the Arduino core, not ESP-IDF.** The ESP-IDF build works but
  takes ~30 min from cold on this machine (and needed a git workaround, see
  `docs/hardware-inventory.md`). The measurement needs no RTOS, driver or task
  set, so it was run standalone via `firmware/arduino_g1/arduino_g1.ino`, a
  numerically identical port of `firmware/main/bench_mac.c`.
- **Optimisation level was equalised.** The Arduino core builds sketches at
  `-Os` while our `sdkconfig.defaults` sets `CONFIG_COMPILER_OPTIMIZATION_PERF`
  (`-O2`). The benchmark function carries
  `__attribute__((optimize("O2")))` so the two are comparable. This is not
  identical to a full `-O2` translation unit, so treat the figure as
  approximate to within a few percent.
- **`psram_size=0` is a build setting, not a hardware finding.** This sketch's
  FQBN did not enable PSRAM. The board really does have 8 MB (esptool reports
  `Embedded PSRAM 8MB`); see `docs/hardware-inventory.md`. It makes no
  difference here, since both benchmark arrays total 8 KB and live in internal
  SRAM.
- **344 KB internal heap free** with PSRAM disabled. The trimmed config's
  16.4 k int8 parameters are negligible against that, so weights can stay in
  fast internal SRAM rather than PSRAM. This matters: octal PSRAM is far
  slower, so keeping the hot path in SRAM is the right default.
- `rev=2` from `esp_chip_info` and `revision v0.2` from esptool are the same
  silicon revision reported in different units.

## Reproducing

```bash
cd "firmware"
arduino-cli compile --fqbn "esp32:esp32:esp32s3:CPUFreq=240,CDCOnBoot=default,FlashSize=8M" arduino_g1
arduino-cli upload -p <port> --fqbn "esp32:esp32:esp32s3:CPUFreq=240,CDCOnBoot=default,FlashSize=8M" arduino_g1
```

`CPUFreq=240` is essential — the entire measurement scales with clock. The
`CDCOnBoot` setting depends on which USB socket is used: `cdc` for the native
USB port, `default` for the UART bridge port. Output was captured from the UART
port at 115200 baud.
