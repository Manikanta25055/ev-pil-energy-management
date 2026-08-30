# Hardware Inventory

Resolves the open hardware question in spec section 7.4 and Task 1 Step 6 of the
Phase 1 plan.

Recorded 2026-08-30.

## Connected board

Detected with `esptool.py --port /dev/cu.usbmodem5B5E0544021 --no-stub chip_id`
under ESP-IDF v5.4:

```
Chip is ESP32-S3 (QFN56) (revision v0.2)
Features: WiFi, BLE, Embedded PSRAM 8MB (AP_3v3)
Crystal is 40MHz
MAC: 1c:db:d4:46:24:e8
```

| Item | Value |
|---|---|
| Chip | ESP32-S3, QFN56 package, revision v0.2 |
| Cores | 2 x Xtensa LX7 @ 240 MHz (128-bit vector ISA) |
| PSRAM | **8 MB, embedded (in-package)** |
| Crystal | 40 MHz |
| Serial port | `/dev/cu.usbmodem5B5E0544021` |
| MAC | `1c:db:d4:46:24:e8` |
| ESP-IDF | v5.4, at `~/Desktop/Espressif 32 C6 Dev-Kit/esp-idf-v5.4` |

## Variant: N8R8, not the base N8

The spec flagged this as the single fact affecting the model budget more than
any other. It is now settled: `Embedded PSRAM 8MB` in the esptool output means
this is an **R8** part, i.e. an ESP32-S3-DevKitM-1-**N8R8** (8 MB flash, 8 MB
octal PSRAM), not the base N8 with no PSRAM.

**Consequence for Phase 2: memory is not a constraint.** The spec's worst case
assumed roughly 400 KB of usable internal SRAM, which would have capped the
Transformer hard. With 8 MB of PSRAM available, even the plan-implied
configuration (seq 64, d_model 64, ~66 k int8 parameters) fits with four orders
of magnitude to spare.

**MACs remain the binding constraint**, exactly as spec section 7.1 predicted.
Gate G1 is therefore still the decisive measurement, and nothing about the
model-sizing procedure changes: budget first, then model.

## Two caveats before treating PSRAM as free

1. **PSRAM must be enabled explicitly.** `CONFIG_SPIRAM` is not set by default,
   and `firmware/sdkconfig.defaults` as committed does not enable it. Until it
   is, the 8 MB is invisible to the application and `esp_psram_get_size()`
   returns nothing. The `EVPIL-BOARD psram=` line printed by `main.c` reflects
   the sdkconfig setting, not the silicon, so it will read `no` until the
   option is turned on.

2. **PSRAM is much slower than internal SRAM.** Octal PSRAM runs over a serial
   bus at a fraction of internal-SRAM bandwidth and is cached. Model weights on
   the inference hot path should therefore stay in **internal SRAM**, with
   PSRAM used for bulk or cold data. Treating PSRAM as equivalent to SRAM would
   understate inference latency.

   This is stated as a known device characteristic, **not** as something
   measured here. Quantify it during G1/G5 by benchmarking identical weight
   buffers placed in internal SRAM versus PSRAM. The difference is itself a
   result worth reporting: "where the weights live" is exactly the kind of
   embedded detail that simulation-only papers cannot speak to.

## Toolchain note

`idf.py` and 13 other files under `esp-idf-v5.4/tools/` are mode 644 rather than
755 — the exec bit was lost, typical of an archive extracted without preserving
permissions. `source export.sh` consequently ends with
`env: idf.py: Permission denied`.

Two options, either is fine:

```bash
# Permanent fix
chmod +x "$IDF_PATH"/tools/*.py

# Or invoke through the interpreter, leaving the installation untouched
python "$IDF_PATH/tools/idf.py" build
```

Builds in this project so far have used the second form.

## Related open items

| Item | Status |
|---|---|
| Board variant / PSRAM (spec section 9) | **Resolved: N8R8, 8 MB PSRAM** |
| G1 int8 MAC throughput | Outstanding — needs a flash and run |
| i3 dataset access | Outstanding |
| BMW i3 parameters | Resolved, see `scripts/identify_params.py` REFERENCES |
