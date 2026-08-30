# Phase 1: Plant and Link Foundation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a validated Python EV plant and a characterised real-time ESP32-S3 link, and measure the on-device compute budget that sizes every model built later.

**Architecture:** Two independent tracks. Track A (Tasks 1-7) establishes the ESP32-S3 firmware skeleton, measures int8 throughput, and closes a jitter-characterised 10 ms Processor-in-the-Loop link with the MCU as clock master. Track B (Tasks 8-16) builds a physics EV plant from composable, separately-tested modules and validates it against real BMW i3 driving logs. The tracks share nothing until Phase 2, so they may be executed in parallel by two people, or sequentially by one.

**Tech Stack:** Python 3.11, NumPy, SciPy, pandas, pytest, pyserial. ESP-IDF v5.x, FreeRTOS, C11. Digilent WaveForms for Analog Discovery 3 capture.

**Spec:** `docs/superpowers/specs/2026-08-30-ev-pil-energy-management-design.md`

## Global Constraints

Every task's requirements implicitly include this section. Values are copied verbatim from the spec.

- **Terminology:** This is **Processor-in-the-Loop (PIL)**, never "HIL". Applies to code comments, docstrings, variable names, and all written output.
- **Primary board:** ESP32-S3-DevKitM-1. The ESP32-C6 is not the primary platform.
- **WiFi and Bluetooth are disabled** in `sdkconfig.defaults`. The radio corrupts both supply-current and timing measurements.
- **Task-to-core pinning is mandatory:** `comm_rx`, `ctrl`, `comm_tx` on core 0; `infer`, `ems`, `diag` on core 1.
- **Control and communication period: 10 ms.** Inference and EMS: 100 ms. Diagnostics: 500 ms.
- **The ESP32 is the clock master.** The host never paces the loop.
- **Data sample rate: 10 Hz** (BMW i3 dataset native rate).
- **Test trips are touched exactly once, at the end of the project.** Not for hyperparameters, not for quantisation calibration, not for ensemble weights, not for sanity checks.
- **Splits are trip-level, never row-level.** No sample from a trip may appear on both sides of any split.
- **Every vehicle parameter carries a citation** recorded in `src/evpil/plant/params.py`.
- **Plant validation criterion (G2):** battery-power RMSE at most 10% of the trip's mean absolute power, and terminal SoC error at most 2 percentage points, on every held-out validation trip.
- **Link criterion (G3):** p99 jitter at most 1 ms and zero dropped frames over a 10-minute run.
- **Compute floor (G1):** 0.1 M MACs in 20 ms or less on core 1.

---

## File Structure

```
pyproject.toml                      Project metadata, deps, pytest config
src/evpil/
  protocol.py                       PIL frame pack/unpack, CRC-16, sequence tracking
  data/
    i3_loader.py                    BMW i3 CSV -> canonical DataFrame
    schema.py                       Canonical column names, dtypes, units
    splits.py                       Trip-level grouped splits, temperature stratification
    guards.py                       Leakage audit, shuffled-label control
  plant/
    params.py                       VehicleParams dataclass, every field cited
    longitudinal.py                 Road-load forces, tractive force, mechanical power
    battery.py                      Thevenin ECM, OCV table, Coulomb counting
    motor.py                        2-D efficiency map, torque and speed limits
    auxiliary.py                    HVAC / auxiliary electrical power
    regen.py                        Regenerative blending and current limits
    plant.py                        Assembly: reset() / step()
tests/
  test_protocol.py
  data/test_schema.py  data/test_i3_loader.py  data/test_splits.py  data/test_guards.py
  plant/test_longitudinal.py  test_battery.py  test_motor.py  test_auxiliary.py
              test_regen.py  test_plant.py
scripts/
  identify_params.py                Least-squares parameter identification from logs
  validate_plant.py                 G2 harness
  measure_link.py                   G3 harness, host side
firmware/
  CMakeLists.txt
  sdkconfig.defaults                WiFi/BT off, 240 MHz, unicore disabled
  main/
    CMakeLists.txt
    main.c                          Entry point, task creation, core pinning
    protocol.c / protocol.h         C mirror of src/evpil/protocol.py
    bench_mac.c / bench_mac.h       G1 int8 MAC micro-benchmark
    timing.c / timing.h             GPIO instrumentation for AD3 capture
    tasks.c / tasks.h               FreeRTOS task bodies
  host_test/
    Makefile                        Host-compiles protocol.c for unit testing
    test_protocol.c                 Same vectors as tests/test_protocol.py
```

Boundaries follow responsibility, not technical layer. Each plant module is a pure function of its inputs plus explicit state, so each is testable without the others. `protocol.py` and `protocol.c` are deliberately duplicated implementations validated against **shared byte vectors** — that redundancy is the point, since a silent encoding mismatch between host and target is the hardest class of bug to find over a serial link.

---

## Track A: Embedded

### Task 1: Project scaffolding and board identification

**Files:**
- Create: `pyproject.toml`
- Create: `src/evpil/__init__.py`
- Create: `firmware/CMakeLists.txt`
- Create: `firmware/sdkconfig.defaults`
- Create: `firmware/main/CMakeLists.txt`
- Create: `firmware/main/main.c`
- Create: `docs/hardware-inventory.md`
- Test: `tests/test_smoke.py`

**Interfaces:**
- Consumes: nothing
- Produces: an importable `evpil` package; a flashable ESP-IDF project named `evpil_fw`; `docs/hardware-inventory.md` recording the board's PSRAM status, which Task 2 and all later model-sizing work depend on.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_smoke.py
def test_package_imports():
    import evpil
    assert evpil.__version__ == "0.1.0"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_smoke.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'evpil'`

- [ ] **Step 3: Create the Python project**

```toml
# pyproject.toml
[project]
name = "evpil"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "numpy>=1.26",
    "scipy>=1.11",
    "pandas>=2.1",
    "pyserial>=3.5",
]

[project.optional-dependencies]
dev = ["pytest>=7.4", "pytest-cov>=4.1"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

```python
# src/evpil/__init__.py
"""Processor-in-the-Loop EV energy management."""

__version__ = "0.1.0"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pip install -e ".[dev]" && python -m pytest tests/test_smoke.py -v`
Expected: PASS

- [ ] **Step 5: Create the ESP-IDF project**

```cmake
# firmware/CMakeLists.txt
cmake_minimum_required(VERSION 3.16)
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(evpil_fw)
```

```cmake
# firmware/main/CMakeLists.txt
idf_component_register(SRCS "main.c"
                       INCLUDE_DIRS ".")
```

```
# firmware/sdkconfig.defaults
CONFIG_IDF_TARGET="esp32s3"
CONFIG_ESP_DEFAULT_CPU_FREQ_MHZ_240=y
CONFIG_FREERTOS_HZ=1000
CONFIG_FREERTOS_GENERATE_RUN_TIME_STATS=y
CONFIG_FREERTOS_USE_TRACE_FACILITY=y
CONFIG_ESP_TASK_WDT_EN=n
CONFIG_COMPILER_OPTIMIZATION_PERF=y
```

`CONFIG_FREERTOS_HZ=1000` gives 1 ms tick resolution, required for the 10 ms period. Runtime stats and the trace facility are needed by the `diag` task in Task 7. WiFi and Bluetooth are absent from the build by default in ESP-IDF v5 unless a component requests them; Task 7 adds explicit disabling once networking components could otherwise be pulled in.

```c
// firmware/main/main.c
#include <stdio.h>
#include "esp_chip_info.h"
#include "esp_psram.h"
#include "esp_system.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

void app_main(void)
{
    esp_chip_info_t info;
    esp_chip_info(&info);

    printf("EVPIL-BOARD cores=%d rev=%d\n", info.cores, info.revision);
    printf("EVPIL-BOARD internal_free=%u\n",
           (unsigned) esp_get_free_internal_heap_size());

#if CONFIG_SPIRAM
    printf("EVPIL-BOARD psram=yes size=%u\n", (unsigned) esp_psram_get_size());
#else
    printf("EVPIL-BOARD psram=no size=0\n");
#endif

    while (1) {
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}
```

- [ ] **Step 6: Flash and record the board identity**

Run from `firmware/`:

```bash
idf.py set-target esp32s3 && idf.py build && idf.py -p /dev/cu.usbmodem* flash monitor
```

Expected: three lines beginning `EVPIL-BOARD`. Record the actual output.

Then read the metal shield marking on the module itself. `ESP32-S3-MINI-1-N8` means no PSRAM. `N8R2` or `N8R8` means 2 MB or 8 MB PSRAM. The printed `psram=` line reflects `sdkconfig`, not hardware, so **the physical marking is the authority** — if they disagree, the marking wins and `CONFIG_SPIRAM` needs enabling.

Write `docs/hardware-inventory.md` with the module marking, the three `EVPIL-BOARD` lines verbatim, the ESP-IDF version from `idf.py --version`, and this sentence completed with the real number: "Usable internal SRAM for model weights plus tensor arena: ____ KB."

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml src/evpil/__init__.py tests/test_smoke.py firmware/ docs/hardware-inventory.md
git commit -m "feat: project scaffolding and board identification"
```

---

### Task 2: int8 MAC micro-benchmark (Gate G1)

**Files:**
- Create: `firmware/main/bench_mac.c`
- Create: `firmware/main/bench_mac.h`
- Modify: `firmware/main/main.c`
- Modify: `firmware/main/CMakeLists.txt`
- Create: `docs/g1-compute-budget.md`

**Interfaces:**
- Consumes: the flashable project from Task 1.
- Produces: `docs/g1-compute-budget.md` containing a measured MACs/second figure. **Every model architecture decision in Phase 2 reads this number.** Nothing downstream may proceed on an assumed value.

This task deliberately measures a plain int8 dot-product loop rather than a full TFLite-Micro graph. The goal is a throughput floor that is easy to interpret and cannot be confounded by framework overhead. Phase 2 measures the real graph; this measures whether the silicon is in the right order of magnitude at all.

- [ ] **Step 1: Write the benchmark**

```c
// firmware/main/bench_mac.h
#pragma once
#include <stdint.h>

/* Runs an int8 x int8 -> int32 accumulation of `n` MACs, `reps` times.
   Returns elapsed microseconds for all reps combined. */
uint32_t bench_mac_run(int n, int reps);

/* Prints one EVPIL-G1 line per size in the sweep. */
void bench_mac_report(void);
```

```c
// firmware/main/bench_mac.c
#include "bench_mac.h"
#include <stdio.h>
#include "esp_timer.h"
#include "esp_attr.h"

#define MAX_N 4096

static int8_t s_a[MAX_N];
static int8_t s_b[MAX_N];
static volatile int32_t s_sink;

static void fill(int n)
{
    for (int i = 0; i < n; i++) {
        s_a[i] = (int8_t) ((i * 7) & 0x7F) - 64;
        s_b[i] = (int8_t) ((i * 13) & 0x7F) - 64;
    }
}

uint32_t bench_mac_run(int n, int reps)
{
    if (n > MAX_N) n = MAX_N;
    fill(n);

    int64_t t0 = esp_timer_get_time();
    for (int r = 0; r < reps; r++) {
        int32_t acc = 0;
        for (int i = 0; i < n; i++) {
            acc += (int32_t) s_a[i] * (int32_t) s_b[i];
        }
        s_sink = acc;              /* volatile: prevents the loop being elided */
    }
    int64_t t1 = esp_timer_get_time();

    return (uint32_t) (t1 - t0);
}

void bench_mac_report(void)
{
    const int sizes[] = {64, 256, 1024, 4096};
    const int reps = 2000;

    for (int k = 0; k < 4; k++) {
        int n = sizes[k];
        uint32_t us = bench_mac_run(n, reps);
        double macs = (double) n * (double) reps;
        double mmac_s = macs / (double) us;   /* MACs/us == MMACs/s */

        printf("EVPIL-G1 n=%d reps=%d us=%u mmac_per_s=%.2f\n",
               n, reps, (unsigned) us, mmac_s);
    }
}
```

- [ ] **Step 2: Wire it into main and build**

```c
// firmware/main/main.c  -- add after the EVPIL-BOARD prints, before the while loop
#include "bench_mac.h"

    bench_mac_report();
```

```cmake
# firmware/main/CMakeLists.txt
idf_component_register(SRCS "main.c" "bench_mac.c"
                       INCLUDE_DIRS ".")
```

Run from `firmware/`: `idf.py build`
Expected: build succeeds with no warnings from `bench_mac.c`.

- [ ] **Step 3: Flash and capture the measurement**

Run: `idf.py -p /dev/cu.usbmodem* flash monitor`
Expected: four `EVPIL-G1` lines, one per size. Throughput should rise with `n` as loop overhead amortises, then flatten. Record all four lines verbatim.

- [ ] **Step 4: Evaluate Gate G1**

Create `docs/g1-compute-budget.md`. Take `mmac_per_s` from the `n=1024` row as the working figure — large enough to have amortised loop overhead, small enough to stay in cache. Compute:

```
latency_ms(config) = MACs(config) / (mmac_per_s * 1000)
```

Fill in this table with real numbers:

| Config | seq | d_model | layers | MACs | measured latency |
|---|---|---|---|---|---|
| Plan-implied | 64 | 64 | 2 | 5.24 M | |
| Trimmed | 32 | 32 | 2 | 0.66 M | |
| Aggressive | 32 | 16 | 1 | 0.10 M | |

**G1 passes if the aggressive config lands at 20 ms or less.** This is a feasibility floor, not the deployed budget — G5 in Phase 2 sets that at 40 ms.

Record the verdict explicitly, then state which config Phase 2 will target.

**If G1 fails:** stop and descend the fallback ladder in spec section 7.3. Tell the professor this week. Do not start Phase 2 model work on a config the silicon cannot run.

Note in the document that this is a scalar C loop, so ESP-NN's vector kernels should improve on it — the measured figure is a **lower bound**, and treating it as such is deliberate conservatism.

- [ ] **Step 5: Commit**

```bash
git add firmware/main/bench_mac.c firmware/main/bench_mac.h firmware/main/main.c firmware/main/CMakeLists.txt docs/g1-compute-budget.md
git commit -m "feat: int8 MAC micro-benchmark, gate G1 measured"
```

---

### Task 3: PIL frame protocol, Python side

**Files:**
- Create: `src/evpil/protocol.py`
- Test: `tests/test_protocol.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `CRC16_INIT: int`, `crc16_ccitt(data: bytes) -> int`
  - `FrameType` enum with `STATE = 1`, `ACTUATION = 2`, `STEP_REQ = 3`
  - `pack_frame(ftype: FrameType, seq: int, t_us: int, payload: bytes) -> bytes`
  - `unpack_frame(buf: bytes) -> tuple[FrameType, int, int, bytes]`
  - `pack_state(seq, t_us, values: Sequence[float]) -> bytes` (8 float32)
  - `pack_actuation(seq, t_us, values: Sequence[float]) -> bytes` (3 float32)
  - `BadFrame` exception
  - Task 4 mirrors these bytes exactly in C; Task 5 and 7 consume them over serial.

Frame layout, little-endian throughout:

```
offset  size  field
0       2     magic  = 0xE71C
2       1     type   (1 STATE, 2 ACTUATION, 3 STEP_REQ)
3       1     len    (payload bytes)
4       4     seq
8       4     t_us   (sender timestamp, microseconds)
12      len   payload
12+len  2     crc    CRC-16/CCITT-FALSE over bytes [0, 12+len)
```

STATE payload is 8 float32: `[v_mps, a_mps2, soc_frac, i_batt_a, v_batt_v, t_ambient_c, grade_rad, p_aux_w]`.
ACTUATION payload is 3 float32: `[torque_nm, regen_blend, p_limit_w]`.
STEP_REQ payload is empty.

At 100 Hz the traffic is 46 + 26 bytes per cycle, about 7.2 kB/s — the link is latency-bound, never bandwidth-bound.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_protocol.py
import struct
import pytest
from evpil.protocol import (
    BadFrame, FrameType, crc16_ccitt, pack_actuation, pack_frame,
    pack_state, unpack_frame,
)


def test_crc16_known_vector():
    # CRC-16/CCITT-FALSE of b"123456789" is 0x29B1 (standard check value).
    assert crc16_ccitt(b"123456789") == 0x29B1


def test_crc16_empty():
    assert crc16_ccitt(b"") == 0xFFFF


def test_pack_frame_layout():
    frame = pack_frame(FrameType.STEP_REQ, seq=7, t_us=123456, payload=b"")
    assert len(frame) == 14
    assert struct.unpack_from("<H", frame, 0)[0] == 0xE71C
    assert frame[2] == 3
    assert frame[3] == 0
    assert struct.unpack_from("<I", frame, 4)[0] == 7
    assert struct.unpack_from("<I", frame, 8)[0] == 123456


def test_roundtrip_state():
    values = [12.5, 0.75, 0.62, -18.0, 352.25, 21.0, 0.035, 480.0]
    frame = pack_state(seq=99, t_us=1_000_000, values=values)
    assert len(frame) == 46

    ftype, seq, t_us, payload = unpack_frame(frame)
    assert ftype is FrameType.STATE
    assert seq == 99
    assert t_us == 1_000_000

    got = list(struct.unpack("<8f", payload))
    assert got == pytest.approx(values, rel=1e-6)


def test_roundtrip_actuation():
    values = [145.0, 0.4, 30000.0]
    frame = pack_actuation(seq=1, t_us=5, values=values)
    assert len(frame) == 26

    ftype, seq, t_us, payload = unpack_frame(frame)
    assert ftype is FrameType.ACTUATION
    assert list(struct.unpack("<3f", payload)) == pytest.approx(values, rel=1e-6)


def test_corrupt_payload_rejected():
    frame = bytearray(pack_state(1, 1, [0.0] * 8))
    frame[20] ^= 0xFF
    with pytest.raises(BadFrame, match="crc"):
        unpack_frame(bytes(frame))


def test_bad_magic_rejected():
    frame = bytearray(pack_state(1, 1, [0.0] * 8))
    frame[0] ^= 0xFF
    with pytest.raises(BadFrame, match="magic"):
        unpack_frame(bytes(frame))


def test_truncated_frame_rejected():
    frame = pack_state(1, 1, [0.0] * 8)
    with pytest.raises(BadFrame, match="short"):
        unpack_frame(frame[:10])


def test_wrong_state_payload_length():
    with pytest.raises(ValueError, match="8 values"):
        pack_state(1, 1, [0.0] * 7)


def test_shared_vector_for_c_parity():
    """This exact frame is asserted byte-for-byte in firmware/host_test/test_protocol.c."""
    frame = pack_actuation(seq=0x01020304, t_us=0x0A0B0C0D, values=[1.0, 0.5, 0.25])
    assert frame.hex() == (
        "1ce7"      # magic 0xE71C, little-endian
        "02"        # type ACTUATION
        "0c"        # payload length 12
        "04030201"  # seq  0x01020304
        "0d0c0b0a"  # t_us 0x0A0B0C0D
        "0000803f"  # 1.0f
        "0000003f"  # 0.5f
        "0000803e"  # 0.25f
        "e9ba"      # crc 0xBAE9
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_protocol.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'evpil.protocol'`

- [ ] **Step 3: Write the implementation**

```python
# src/evpil/protocol.py
"""PIL frame protocol shared by the host plant and the ESP32-S3 firmware.

The C mirror lives in firmware/main/protocol.c and is validated against the
same byte vectors. A silent encoding mismatch between the two is the hardest
class of bug to find over a serial link, so the duplication is intentional.
"""

from __future__ import annotations

import struct
from collections.abc import Sequence
from enum import IntEnum

MAGIC = 0xE71C
HEADER_SIZE = 12
CRC_SIZE = 2
CRC16_INIT = 0xFFFF

_HEADER = struct.Struct("<HBBII")


class FrameType(IntEnum):
    STATE = 1
    ACTUATION = 2
    STEP_REQ = 3


class BadFrame(Exception):
    """Raised when a received buffer is not a valid frame."""


def crc16_ccitt(data: bytes) -> int:
    """CRC-16/CCITT-FALSE: poly 0x1021, init 0xFFFF, no reflection, no final xor."""
    crc = CRC16_INIT
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def pack_frame(ftype: FrameType, seq: int, t_us: int, payload: bytes) -> bytes:
    if len(payload) > 255:
        raise ValueError(f"payload too long: {len(payload)} bytes, max 255")

    head = _HEADER.pack(MAGIC, int(ftype), len(payload), seq & 0xFFFFFFFF,
                        t_us & 0xFFFFFFFF)
    body = head + payload
    return body + struct.pack("<H", crc16_ccitt(body))


def unpack_frame(buf: bytes) -> tuple[FrameType, int, int, bytes]:
    if len(buf) < HEADER_SIZE + CRC_SIZE:
        raise BadFrame(f"frame too short: {len(buf)} bytes")

    magic, raw_type, length, seq, t_us = _HEADER.unpack_from(buf, 0)
    if magic != MAGIC:
        raise BadFrame(f"bad magic: 0x{magic:04X}")

    total = HEADER_SIZE + length + CRC_SIZE
    if len(buf) < total:
        raise BadFrame(f"frame too short: need {total}, got {len(buf)}")

    (want,) = struct.unpack_from("<H", buf, HEADER_SIZE + length)
    got = crc16_ccitt(buf[: HEADER_SIZE + length])
    if want != got:
        raise BadFrame(f"crc mismatch: sent 0x{want:04X}, computed 0x{got:04X}")

    try:
        ftype = FrameType(raw_type)
    except ValueError as exc:
        raise BadFrame(f"unknown frame type: {raw_type}") from exc

    return ftype, seq, t_us, buf[HEADER_SIZE : HEADER_SIZE + length]


def pack_state(seq: int, t_us: int, values: Sequence[float]) -> bytes:
    """values: [v_mps, a_mps2, soc_frac, i_batt_a, v_batt_v, t_ambient_c,
    grade_rad, p_aux_w]"""
    if len(values) != 8:
        raise ValueError(f"STATE needs 8 values, got {len(values)}")
    return pack_frame(FrameType.STATE, seq, t_us, struct.pack("<8f", *values))


def pack_actuation(seq: int, t_us: int, values: Sequence[float]) -> bytes:
    """values: [torque_nm, regen_blend, p_limit_w]"""
    if len(values) != 3:
        raise ValueError(f"ACTUATION needs 3 values, got {len(values)}")
    return pack_frame(FrameType.ACTUATION, seq, t_us, struct.pack("<3f", *values))


def pack_step_req(seq: int, t_us: int) -> bytes:
    return pack_frame(FrameType.STEP_REQ, seq, t_us, b"")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_protocol.py -v`
Expected: 10 passed

- [ ] **Step 5: Print the shared vector for Task 4**

Run:

```bash
python -c "from evpil.protocol import pack_actuation; print(pack_actuation(0x01020304, 0x0A0B0C0D, [1.0, 0.5, 0.25]).hex())"
```

Expected output, already verified: `1ce7020c040302010d0c0b0a0000803f0000003f0000803ee9ba`

If it differs, the Python implementation has a bug. Task 4 asserts these
exact 26 bytes in C.

- [ ] **Step 6: Commit**

```bash
git add src/evpil/protocol.py tests/test_protocol.py
git commit -m "feat: PIL frame protocol, Python side"
```

---

### Task 4: PIL frame protocol, C side with host-run parity tests

**Files:**
- Create: `firmware/main/protocol.c`
- Create: `firmware/main/protocol.h`
- Create: `firmware/host_test/test_protocol.c`
- Create: `firmware/host_test/Makefile`

**Interfaces:**
- Consumes: the byte vector printed in Task 3 Step 5.
- Produces:
  - `uint16_t evpil_crc16(const uint8_t *data, size_t len)`
  - `int evpil_pack(uint8_t *out, size_t out_cap, uint8_t type, uint32_t seq, uint32_t t_us, const uint8_t *payload, uint8_t len)` returning bytes written or negative on error
  - `int evpil_unpack(const uint8_t *buf, size_t len, evpil_frame_t *out)` returning 0 on success or a negative `EVPIL_ERR_*` code
  - Task 5 and Task 7 call these from firmware.

Tests compile and run **on the development machine with plain gcc**, not on target. Protocol encoding has no hardware dependency, so testing it on target would be slower and no more informative.

- [ ] **Step 1: Write the failing test**

```c
// firmware/host_test/test_protocol.c
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "protocol.h"

static int failures = 0;

#define CHECK(cond, msg) do {                                  \
    if (!(cond)) { printf("FAIL: %s\n", msg); failures++; }    \
    else        { printf("ok:   %s\n", msg); }                 \
} while (0)

static void test_crc_known_vector(void)
{
    const uint8_t v[] = "123456789";
    CHECK(evpil_crc16(v, 9) == 0x29B1, "crc16 check value 0x29B1");
    CHECK(evpil_crc16(NULL, 0) == 0xFFFF, "crc16 of empty is 0xFFFF");
}

static void test_parity_with_python(void)
{
    /* Byte-for-byte identical to tests/test_protocol.py
       ::test_shared_vector_for_c_parity */
    float vals[3] = {1.0f, 0.5f, 0.25f};
    uint8_t payload[12];
    memcpy(payload, vals, 12);

    uint8_t frame[64];
    int n = evpil_pack(frame, sizeof frame, EVPIL_ACTUATION,
                       0x01020304u, 0x0A0B0C0Du, payload, 12);
    CHECK(n == 26, "actuation frame is 26 bytes");

    static const uint8_t expect[] = {
        0x1C, 0xE7,             /* magic  */
        0x02,                   /* type   */
        0x0C,                   /* len    */
        0x04, 0x03, 0x02, 0x01, /* seq    */
        0x0D, 0x0C, 0x0B, 0x0A, /* t_us   */
        0x00, 0x00, 0x80, 0x3F, /* 1.0f   */
        0x00, 0x00, 0x00, 0x3F, /* 0.5f   */
        0x00, 0x00, 0x80, 0x3E, /* 0.25f  */
        0xE9, 0xBA,             /* crc 0xBAE9 */
    };
    CHECK(memcmp(frame, expect, 26) == 0, "frame bytes match Python exactly");
}

static void test_roundtrip(void)
{
    uint8_t payload[12] = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12};
    uint8_t frame[64];
    int n = evpil_pack(frame, sizeof frame, EVPIL_ACTUATION, 42, 99, payload, 12);
    CHECK(n > 0, "pack succeeds");

    evpil_frame_t f;
    CHECK(evpil_unpack(frame, (size_t) n, &f) == 0, "unpack succeeds");
    CHECK(f.type == EVPIL_ACTUATION, "type preserved");
    CHECK(f.seq == 42, "seq preserved");
    CHECK(f.t_us == 99, "t_us preserved");
    CHECK(f.len == 12, "len preserved");
    CHECK(memcmp(f.payload, payload, 12) == 0, "payload preserved");
}

static void test_rejects_corruption(void)
{
    uint8_t payload[12] = {0};
    uint8_t frame[64];
    int n = evpil_pack(frame, sizeof frame, EVPIL_ACTUATION, 1, 1, payload, 12);

    frame[15] ^= 0xFF;
    evpil_frame_t f;
    CHECK(evpil_unpack(frame, (size_t) n, &f) == EVPIL_ERR_CRC, "corrupt payload -> ERR_CRC");

    frame[15] ^= 0xFF;
    frame[0] ^= 0xFF;
    CHECK(evpil_unpack(frame, (size_t) n, &f) == EVPIL_ERR_MAGIC, "bad magic -> ERR_MAGIC");

    frame[0] ^= 0xFF;
    CHECK(evpil_unpack(frame, 8, &f) == EVPIL_ERR_SHORT, "truncated -> ERR_SHORT");
}

int main(void)
{
    test_crc_known_vector();
    test_parity_with_python();
    test_roundtrip();
    test_rejects_corruption();

    printf("\n%s (%d failures)\n", failures ? "FAILED" : "PASSED", failures);
    return failures != 0;
}
```

```make
# firmware/host_test/Makefile
CFLAGS = -std=c11 -Wall -Wextra -Werror -O1 -I../main

test_protocol: test_protocol.c ../main/protocol.c
	$(CC) $(CFLAGS) -o $@ $^

.PHONY: check clean
check: test_protocol
	./test_protocol

clean:
	rm -f test_protocol
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd firmware/host_test && make check`
Expected: FAIL — compiler error, `protocol.h: No such file or directory`

- [ ] **Step 3: Write the implementation**

```c
// firmware/main/protocol.h
#pragma once
#include <stddef.h>
#include <stdint.h>

#define EVPIL_MAGIC        0xE71Cu
#define EVPIL_HEADER_SIZE  12
#define EVPIL_CRC_SIZE     2
#define EVPIL_MAX_PAYLOAD  255

#define EVPIL_STATE      1
#define EVPIL_ACTUATION  2
#define EVPIL_STEP_REQ   3

#define EVPIL_ERR_SHORT  (-1)
#define EVPIL_ERR_MAGIC  (-2)
#define EVPIL_ERR_CRC    (-3)
#define EVPIL_ERR_TYPE   (-4)
#define EVPIL_ERR_CAP    (-5)

typedef struct {
    uint8_t        type;
    uint32_t       seq;
    uint32_t       t_us;
    uint8_t        len;
    const uint8_t *payload;   /* points into the caller's buffer, not copied */
} evpil_frame_t;

uint16_t evpil_crc16(const uint8_t *data, size_t len);

int evpil_pack(uint8_t *out, size_t out_cap, uint8_t type,
               uint32_t seq, uint32_t t_us,
               const uint8_t *payload, uint8_t len);

int evpil_unpack(const uint8_t *buf, size_t len, evpil_frame_t *out);
```

```c
// firmware/main/protocol.c
#include "protocol.h"
#include <string.h>

uint16_t evpil_crc16(const uint8_t *data, size_t len)
{
    uint16_t crc = 0xFFFFu;
    for (size_t i = 0; i < len; i++) {
        crc ^= (uint16_t) data[i] << 8;
        for (int b = 0; b < 8; b++) {
            crc = (crc & 0x8000u) ? (uint16_t) ((crc << 1) ^ 0x1021u)
                                  : (uint16_t) (crc << 1);
        }
    }
    return crc;
}

static void put_u16(uint8_t *p, uint16_t v) { p[0] = (uint8_t) v; p[1] = (uint8_t) (v >> 8); }
static void put_u32(uint8_t *p, uint32_t v)
{
    p[0] = (uint8_t) v;         p[1] = (uint8_t) (v >> 8);
    p[2] = (uint8_t) (v >> 16); p[3] = (uint8_t) (v >> 24);
}
static uint16_t get_u16(const uint8_t *p) { return (uint16_t) (p[0] | (p[1] << 8)); }
static uint32_t get_u32(const uint8_t *p)
{
    return (uint32_t) p[0] | ((uint32_t) p[1] << 8)
         | ((uint32_t) p[2] << 16) | ((uint32_t) p[3] << 24);
}

int evpil_pack(uint8_t *out, size_t out_cap, uint8_t type,
               uint32_t seq, uint32_t t_us,
               const uint8_t *payload, uint8_t len)
{
    size_t total = EVPIL_HEADER_SIZE + (size_t) len + EVPIL_CRC_SIZE;
    if (out_cap < total) return EVPIL_ERR_CAP;

    put_u16(out + 0, EVPIL_MAGIC);
    out[2] = type;
    out[3] = len;
    put_u32(out + 4, seq);
    put_u32(out + 8, t_us);
    if (len && payload) memcpy(out + EVPIL_HEADER_SIZE, payload, len);

    uint16_t crc = evpil_crc16(out, EVPIL_HEADER_SIZE + (size_t) len);
    put_u16(out + EVPIL_HEADER_SIZE + len, crc);

    return (int) total;
}

int evpil_unpack(const uint8_t *buf, size_t len, evpil_frame_t *out)
{
    if (len < EVPIL_HEADER_SIZE + EVPIL_CRC_SIZE) return EVPIL_ERR_SHORT;
    if (get_u16(buf) != EVPIL_MAGIC)              return EVPIL_ERR_MAGIC;

    uint8_t type    = buf[2];
    uint8_t paylen  = buf[3];
    size_t  total   = EVPIL_HEADER_SIZE + (size_t) paylen + EVPIL_CRC_SIZE;
    if (len < total) return EVPIL_ERR_SHORT;

    uint16_t want = get_u16(buf + EVPIL_HEADER_SIZE + paylen);
    uint16_t got  = evpil_crc16(buf, EVPIL_HEADER_SIZE + (size_t) paylen);
    if (want != got) return EVPIL_ERR_CRC;

    if (type != EVPIL_STATE && type != EVPIL_ACTUATION && type != EVPIL_STEP_REQ) {
        return EVPIL_ERR_TYPE;
    }

    out->type    = type;
    out->seq     = get_u32(buf + 4);
    out->t_us    = get_u32(buf + 8);
    out->len     = paylen;
    out->payload = buf + EVPIL_HEADER_SIZE;
    return 0;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd firmware/host_test && make check`
Expected: every line begins `ok:`, final line `PASSED (0 failures)`

If `frame bytes match Python exactly` fails, the two implementations have diverged — fix before proceeding. Nothing downstream works if host and target disagree on encoding.

- [ ] **Step 5: Commit**

```bash
git add firmware/main/protocol.c firmware/main/protocol.h firmware/host_test/
git commit -m "feat: PIL frame protocol C mirror with host parity tests"
```

---

### Task 5: Serial transport and host round-trip

**Files:**
- Create: `firmware/main/link.c`
- Create: `firmware/main/link.h`
- Modify: `firmware/main/main.c`
- Modify: `firmware/main/CMakeLists.txt`
- Create: `src/evpil/link.py`
- Test: `tests/test_link.py`

**Interfaces:**
- Consumes: `evpil_pack` / `evpil_unpack` from Task 4; `pack_frame` / `unpack_frame` from Task 3.
- Produces:
  - Firmware: `void link_init(void)`, `int link_read_frame(uint8_t *buf, size_t cap, uint32_t timeout_ms)`, `int link_write(const uint8_t *buf, size_t len)`
  - Host: `class SerialLink` with `open()`, `close()`, `send(frame: bytes) -> None`, `recv(timeout_s: float) -> tuple[FrameType, int, int, bytes]`, and `stats` exposing `frames_ok`, `frames_bad`, `frames_dropped`.
  - Task 7 uses both sides to close the control loop.

Transport is UART1 at 921600 8N1 on GPIO17 (TX) and GPIO18 (RX), via an external USB-UART adapter. A compile-time switch selects USB-Serial-JTAG instead; Task 7's G3 measurement chooses between them on evidence.

UART is the default because its timing is governed by the ESP32's own peripheral clock, whereas USB-CDC timing is shaped by host USB scheduling. Given that the MCU is the clock master, the more deterministic transport is the better starting point.

- [ ] **Step 1: Write the failing host test**

```python
# tests/test_link.py
import pytest
from evpil.link import FrameAssembler
from evpil.protocol import BadFrame, FrameType, pack_actuation, pack_state


def test_assembler_yields_single_frame():
    asm = FrameAssembler()
    frame = pack_state(1, 100, [0.0] * 8)
    got = list(asm.feed(frame))
    assert len(got) == 1
    assert got[0][0] is FrameType.STATE
    assert got[0][1] == 1


def test_assembler_handles_split_across_chunks():
    asm = FrameAssembler()
    frame = pack_state(7, 200, [1.0] * 8)
    assert list(asm.feed(frame[:5])) == []
    assert list(asm.feed(frame[5:20])) == []
    got = list(asm.feed(frame[20:]))
    assert len(got) == 1
    assert got[0][1] == 7


def test_assembler_handles_two_frames_in_one_chunk():
    asm = FrameAssembler()
    chunk = pack_state(1, 1, [0.0] * 8) + pack_actuation(2, 2, [0.0] * 3)
    got = list(asm.feed(chunk))
    assert [g[1] for g in got] == [1, 2]


def test_assembler_resyncs_after_garbage():
    asm = FrameAssembler()
    frame = pack_state(9, 300, [2.0] * 8)
    got = list(asm.feed(b"\x00\xff\x13\x37" + frame))
    assert len(got) == 1
    assert got[0][1] == 9


def test_assembler_drops_corrupt_frame_and_recovers():
    asm = FrameAssembler()
    bad = bytearray(pack_state(1, 1, [0.0] * 8))
    bad[20] ^= 0xFF
    good = pack_state(2, 2, [0.0] * 8)

    got = list(asm.feed(bytes(bad) + good))
    assert [g[1] for g in got] == [2]
    assert asm.frames_bad == 1
    assert asm.frames_ok == 1


def test_assembler_counts_sequence_gaps():
    asm = FrameAssembler()
    list(asm.feed(pack_state(1, 1, [0.0] * 8)))
    list(asm.feed(pack_state(4, 4, [0.0] * 8)))
    assert asm.frames_dropped == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_link.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'evpil.link'`

- [ ] **Step 3: Write the host implementation**

```python
# src/evpil/link.py
"""Host side of the PIL serial link: byte-stream framing and a pyserial wrapper."""

from __future__ import annotations

import struct
import time
from collections.abc import Iterator

import serial

from evpil.protocol import (
    CRC_SIZE, HEADER_SIZE, MAGIC, BadFrame, FrameType, unpack_frame,
)

_MAGIC_LE = struct.pack("<H", MAGIC)


class FrameAssembler:
    """Turns an arbitrarily-chunked byte stream into whole frames.

    Resynchronises by scanning for the magic prefix, so a corrupt or partial
    frame costs at most one frame rather than desynchronising the link.
    """

    def __init__(self) -> None:
        self._buf = bytearray()
        self._last_seq: int | None = None
        self.frames_ok = 0
        self.frames_bad = 0
        self.frames_dropped = 0

    def feed(self, data: bytes) -> Iterator[tuple[FrameType, int, int, bytes]]:
        self._buf.extend(data)

        while True:
            start = self._buf.find(_MAGIC_LE)
            if start < 0:
                # Keep one trailing byte: magic may straddle the chunk boundary.
                del self._buf[: max(0, len(self._buf) - 1)]
                return
            if start > 0:
                del self._buf[:start]

            if len(self._buf) < HEADER_SIZE + CRC_SIZE:
                return

            total = HEADER_SIZE + self._buf[3] + CRC_SIZE
            if len(self._buf) < total:
                return

            candidate = bytes(self._buf[:total])
            try:
                ftype, seq, t_us, payload = unpack_frame(candidate)
            except BadFrame:
                self.frames_bad += 1
                del self._buf[:2]      # skip this magic, rescan from the next byte
                continue

            del self._buf[:total]
            self.frames_ok += 1

            if self._last_seq is not None:
                gap = (seq - self._last_seq - 1) & 0xFFFFFFFF
                if 0 < gap < 1000:     # ignore wraps and resets
                    self.frames_dropped += gap
            self._last_seq = seq

            yield ftype, seq, t_us, payload


class SerialLink:
    """Blocking serial transport around FrameAssembler."""

    def __init__(self, port: str, baud: int = 921600) -> None:
        self.port = port
        self.baud = baud
        self._ser: serial.Serial | None = None
        self.asm = FrameAssembler()
        self._pending: list[tuple[FrameType, int, int, bytes]] = []

    def open(self) -> None:
        self._ser = serial.Serial(self.port, self.baud, timeout=0)
        self._ser.reset_input_buffer()

    def close(self) -> None:
        if self._ser is not None:
            self._ser.close()
            self._ser = None

    def send(self, frame: bytes) -> None:
        assert self._ser is not None, "call open() first"
        self._ser.write(frame)

    def recv(self, timeout_s: float = 0.1):
        assert self._ser is not None, "call open() first"
        deadline = time.perf_counter() + timeout_s
        while True:
            if self._pending:
                return self._pending.pop(0)
            waiting = self._ser.in_waiting
            if waiting:
                self._pending.extend(self.asm.feed(self._ser.read(waiting)))
                continue
            if time.perf_counter() >= deadline:
                return None
            time.sleep(0.0002)

    @property
    def stats(self) -> dict[str, int]:
        return {
            "frames_ok": self.asm.frames_ok,
            "frames_bad": self.asm.frames_bad,
            "frames_dropped": self.asm.frames_dropped,
        }

    def __enter__(self) -> "SerialLink":
        self.open()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_link.py -v`
Expected: 6 passed

- [ ] **Step 5: Write the firmware transport**

```c
// firmware/main/link.h
#pragma once
#include <stddef.h>
#include <stdint.h>

#define LINK_UART_NUM   1
#define LINK_TX_GPIO    17
#define LINK_RX_GPIO    18
#define LINK_BAUD       921600
#define LINK_RX_BUFSZ   512

void link_init(void);

/* Reads one whole valid frame into `buf`. Returns bytes read, or a negative
   EVPIL_ERR_* code, or 0 on timeout. Resynchronises on magic. */
int link_read_frame(uint8_t *buf, size_t cap, uint32_t timeout_ms);

int link_write(const uint8_t *buf, size_t len);
```

```c
// firmware/main/link.c
#include "link.h"
#include "protocol.h"
#include "driver/uart.h"
#include "driver/gpio.h"
#include "esp_timer.h"
#include <string.h>

void link_init(void)
{
    const uart_config_t cfg = {
        .baud_rate  = LINK_BAUD,
        .data_bits  = UART_DATA_8_BITS,
        .parity     = UART_PARITY_DISABLE,
        .stop_bits  = UART_STOP_BITS_1,
        .flow_ctrl  = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_DEFAULT,
    };
    ESP_ERROR_CHECK(uart_driver_install(LINK_UART_NUM, LINK_RX_BUFSZ * 2, 0, 0, NULL, 0));
    ESP_ERROR_CHECK(uart_param_config(LINK_UART_NUM, &cfg));
    ESP_ERROR_CHECK(uart_set_pin(LINK_UART_NUM, LINK_TX_GPIO, LINK_RX_GPIO,
                                 UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE));
}

int link_read_frame(uint8_t *buf, size_t cap, uint32_t timeout_ms)
{
    int64_t deadline = esp_timer_get_time() + (int64_t) timeout_ms * 1000;
    size_t have = 0;

    while (esp_timer_get_time() < deadline) {
        /* Fill the header first so the payload length is known. */
        while (have < EVPIL_HEADER_SIZE) {
            int n = uart_read_bytes(LINK_UART_NUM, buf + have,
                                    EVPIL_HEADER_SIZE - have, pdMS_TO_TICKS(1));
            if (n <= 0) {
                if (esp_timer_get_time() >= deadline) return 0;
                continue;
            }
            have += (size_t) n;
        }

        /* Resynchronise: slide until the buffer starts with magic. */
        if (buf[0] != 0x1C || buf[1] != 0xE7) {
            memmove(buf, buf + 1, have - 1);
            have -= 1;
            continue;
        }

        size_t total = EVPIL_HEADER_SIZE + buf[3] + EVPIL_CRC_SIZE;
        if (total > cap) { have = 0; continue; }

        while (have < total) {
            int n = uart_read_bytes(LINK_UART_NUM, buf + have, total - have,
                                    pdMS_TO_TICKS(1));
            if (n <= 0) {
                if (esp_timer_get_time() >= deadline) return 0;
                continue;
            }
            have += (size_t) n;
        }

        evpil_frame_t f;
        int rc = evpil_unpack(buf, total, &f);
        if (rc == 0) return (int) total;

        memmove(buf, buf + 2, have - 2);   /* drop this magic, rescan */
        have -= 2;
    }
    return 0;
}

int link_write(const uint8_t *buf, size_t len)
{
    return uart_write_bytes(LINK_UART_NUM, (const char *) buf, len);
}
```

```cmake
# firmware/main/CMakeLists.txt
idf_component_register(SRCS "main.c" "bench_mac.c" "protocol.c" "link.c"
                       INCLUDE_DIRS ".")
```

- [ ] **Step 6: Add an echo loop to main and verify the round-trip**

```c
// firmware/main/main.c  -- replace the trailing while(1) with this
#include "link.h"
#include "protocol.h"
#include "esp_timer.h"

    link_init();

    static uint8_t rx[64];
    static uint8_t tx[64];

    while (1) {
        int n = link_read_frame(rx, sizeof rx, 100);
        if (n <= 0) continue;

        evpil_frame_t f;
        if (evpil_unpack(rx, (size_t) n, &f) != 0) continue;

        /* Echo the payload back, stamped with our own clock. */
        int m = evpil_pack(tx, sizeof tx, f.type, f.seq,
                           (uint32_t) esp_timer_get_time(), f.payload, f.len);
        if (m > 0) link_write(tx, (size_t) m);
    }
```

Wire the USB-UART adapter: adapter RX to GPIO17, adapter TX to GPIO18, and **ground to ground**. Then:

```bash
cd firmware && idf.py build && idf.py -p /dev/cu.usbmodem* flash
```

Verify with a throwaway one-liner (the measured version comes in Task 7):

```bash
python -c "
from evpil.link import SerialLink
from evpil.protocol import pack_actuation
import time
with SerialLink('/dev/cu.usbserial-XXXX') as link:
    for i in range(10):
        link.send(pack_actuation(i, int(time.perf_counter()*1e6), [1.0, 0.5, 0.25]))
        print(link.recv(0.5))
    print(link.stats)
"
```

Expected: ten tuples with `FrameType.ACTUATION` and `seq` counting 0 to 9, then
`{'frames_ok': 10, 'frames_bad': 0, 'frames_dropped': 0}`.

Substitute the real device path from `ls /dev/cu.*`.

- [ ] **Step 7: Commit**

```bash
git add src/evpil/link.py tests/test_link.py firmware/main/link.c firmware/main/link.h firmware/main/main.c firmware/main/CMakeLists.txt
git commit -m "feat: PIL serial transport, host and firmware"
```

---

### Task 6: GPIO timing instrumentation

**Files:**
- Create: `firmware/main/timing.c`
- Create: `firmware/main/timing.h`
- Modify: `firmware/main/CMakeLists.txt`
- Create: `docs/measurement-rig.md`

**Interfaces:**
- Consumes: nothing.
- Produces: `timing_init()`, and the macros `TIMING_MARK_HIGH(ch)` / `TIMING_MARK_LOW(ch)` with channels `TIMING_CH_CTRL`, `TIMING_CH_INFER`, `TIMING_CH_COMM`. Task 7 wraps every task body in these. Phase 4's measurement campaign reads the resulting waveforms.

A GPIO pin held high for exactly the duration of a task body, captured by an external logic analyser, is far stronger evidence of worst-case execution time than any figure the firmware reports about itself. It costs two register writes.

- [ ] **Step 1: Write the implementation**

Direct register access is used rather than `gpio_set_level()` because the latter costs enough cycles to distort the very measurement being taken.

```c
// firmware/main/timing.h
#pragma once
#include <stdint.h>
#include "soc/gpio_struct.h"

#define TIMING_CH_CTRL   4    /* GPIO4  -> AD3 DIO0 */
#define TIMING_CH_INFER  5    /* GPIO5  -> AD3 DIO1 */
#define TIMING_CH_COMM   6    /* GPIO6  -> AD3 DIO2 */

void timing_init(void);

/* Single-register writes: a few cycles, so the pin edge tracks the task
   boundary closely enough not to bias the measurement. */
#define TIMING_MARK_HIGH(ch)  do { GPIO.out_w1ts = (1u << (ch)); } while (0)
#define TIMING_MARK_LOW(ch)   do { GPIO.out_w1tc = (1u << (ch)); } while (0)
```

```c
// firmware/main/timing.c
#include "timing.h"
#include "driver/gpio.h"

void timing_init(void)
{
    const uint64_t mask = (1ULL << TIMING_CH_CTRL)
                        | (1ULL << TIMING_CH_INFER)
                        | (1ULL << TIMING_CH_COMM);

    gpio_config_t cfg = {
        .pin_bit_mask = mask,
        .mode         = GPIO_MODE_OUTPUT,
        .pull_up_en   = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type    = GPIO_INTR_DISABLE,
    };
    ESP_ERROR_CHECK(gpio_config(&cfg));

    GPIO.out_w1tc = (uint32_t) mask;
}
```

```cmake
# firmware/main/CMakeLists.txt
idf_component_register(SRCS "main.c" "bench_mac.c" "protocol.c" "link.c" "timing.c"
                       INCLUDE_DIRS ".")
```

- [ ] **Step 2: Verify the pins toggle**

Add to `main.c` immediately after `link_init()`, build, flash, and probe GPIO4 with the AD3 or any scope:

```c
    timing_init();
    for (int i = 0; i < 1000; i++) {
        TIMING_MARK_HIGH(TIMING_CH_CTRL);
        esp_rom_delay_us(100);
        TIMING_MARK_LOW(TIMING_CH_CTRL);
        esp_rom_delay_us(900);
    }
```

Expected on the AD3: a 1 kHz square wave on GPIO4 with a 10% duty cycle, high time 100 us ± 2 us. If the high time is materially wrong, the register-write path is not doing what the header claims and must be fixed before it is trusted for WCET.

Remove this verification block once confirmed.

- [ ] **Step 3: Document the measurement rig**

Write `docs/measurement-rig.md` covering:

| Signal | ESP32-S3 pin | AD3 channel | Meaning |
|---|---|---|---|
| `ctrl` task active | GPIO4 | DIO0 | High for the duration of the control task body |
| `infer` task active | GPIO5 | DIO1 | High for the duration of the inference task body |
| `comm` task active | GPIO6 | DIO2 | High for the duration of the comm task body |
| 3V3 supply current | 1 ohm shunt in the 3V3 rail | Scope 1+/1- differential | Instantaneous current; integrate for mJ per inference |

Record the WaveForms capture settings that will be used for every measurement so runs are comparable: Logic Analyzer at 10 MS/s (0.1 us resolution, ample for microsecond-scale task bodies), 20 M sample buffer, trigger on DIO0 rising edge.

State the shunt caveat explicitly: a 1 ohm shunt in the 3V3 rail drops 100 mV at 100 mA, which is within the ESP32-S3's tolerance but is not negligible. Record the shunt value actually used and note that measured current must be corrected for the resulting supply droop.

Also record that WiFi and Bluetooth must be off for every current measurement, per the Global Constraints — radio activity would swamp the inference signal entirely.

- [ ] **Step 4: Commit**

```bash
git add firmware/main/timing.c firmware/main/timing.h firmware/main/CMakeLists.txt docs/measurement-rig.md
git commit -m "feat: GPIO timing instrumentation and measurement rig documentation"
```

---

### Task 7: FreeRTOS task set and clock-master loop (Gate G3)

**Files:**
- Create: `firmware/main/tasks.c`
- Create: `firmware/main/tasks.h`
- Modify: `firmware/main/main.c`
- Modify: `firmware/main/CMakeLists.txt`
- Modify: `firmware/sdkconfig.defaults`
- Create: `scripts/measure_link.py`
- Create: `docs/g3-link-characterisation.md`

**Interfaces:**
- Consumes: `link_*` from Task 5, `TIMING_MARK_*` from Task 6, `evpil_*` from Task 4, `SerialLink` from Task 5.
- Produces: the full six-task FreeRTOS skeleton with correct periods and core pinning, running dummy compute. Phase 2 replaces the dummy inference body with a real model; Phase 3 replaces the dummy control body with PID plus SAC. `docs/g3-link-characterisation.md` records the G3 verdict.

The MCU drives the loop: `comm_tx` emits a STEP_REQ, the host advances the plant one step and replies with STATE, `comm_rx` consumes it. Host scheduler jitter therefore appears as measured link latency rather than as unexplained control-loop jitter.

- [ ] **Step 1: Disable the radios explicitly**

Append to `firmware/sdkconfig.defaults`:

```
CONFIG_ESP_WIFI_ENABLED=n
CONFIG_BT_ENABLED=n
```

Per the Global Constraints, radio activity corrupts both the supply-current and the timing measurements. Setting these explicitly means a later component that pulls in networking cannot silently re-enable them.

- [ ] **Step 2: Write the task set**

```c
// firmware/main/tasks.h
#pragma once
#include <stdint.h>

#define CTRL_PERIOD_MS    10
#define INFER_PERIOD_MS  100
#define EMS_PERIOD_MS    100
#define DIAG_PERIOD_MS   500

typedef struct {
    float    v_mps, a_mps2, soc_frac, i_batt_a;
    float    v_batt_v, t_ambient_c, grade_rad, p_aux_w;
    uint32_t seq;
    uint32_t host_t_us;
    uint32_t rx_t_us;
} plant_state_t;

typedef struct {
    uint32_t loop_count;
    uint32_t rx_timeouts;
    uint32_t rx_bad;
    uint32_t infer_deadline_misses;
    uint32_t ctrl_wcet_us;
    uint32_t infer_wcet_us;
    uint32_t rtt_max_us;
} diag_stats_t;

void tasks_start(void);
```

```c
// firmware/main/tasks.c
#include "tasks.h"
#include "link.h"
#include "protocol.h"
#include "timing.h"

#include <string.h>
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"

static plant_state_t s_state;
static diag_stats_t  s_diag;
static SemaphoreHandle_t s_state_mux;

static float s_torque_cmd  = 0.0f;
static float s_regen_blend = 0.5f;
static float s_p_limit_w   = 50000.0f;

/* ---- core 0: the hard real-time loop ------------------------------------ */

static void ctrl_task(void *arg)
{
    (void) arg;
    TickType_t next = xTaskGetTickCount();
    uint8_t tx[64], rx[64];
    uint32_t seq = 0;

    for (;;) {
        TIMING_MARK_HIGH(TIMING_CH_COMM);
        uint32_t t_req = (uint32_t) esp_timer_get_time();

        /* The MCU is the clock master: request one plant step. */
        int m = evpil_pack(tx, sizeof tx, EVPIL_STEP_REQ, seq, t_req, NULL, 0);
        if (m > 0) link_write(tx, (size_t) m);

        int n = link_read_frame(rx, sizeof rx, CTRL_PERIOD_MS - 1);
        TIMING_MARK_LOW(TIMING_CH_COMM);

        if (n > 0) {
            evpil_frame_t f;
            if (evpil_unpack(rx, (size_t) n, &f) == 0 && f.type == EVPIL_STATE
                && f.len == 32) {
                uint32_t t_rx = (uint32_t) esp_timer_get_time();
                uint32_t rtt  = t_rx - t_req;
                if (rtt > s_diag.rtt_max_us) s_diag.rtt_max_us = rtt;

                float v[8];
                memcpy(v, f.payload, sizeof v);

                xSemaphoreTake(s_state_mux, portMAX_DELAY);
                s_state.v_mps       = v[0];  s_state.a_mps2      = v[1];
                s_state.soc_frac    = v[2];  s_state.i_batt_a    = v[3];
                s_state.v_batt_v    = v[4];  s_state.t_ambient_c = v[5];
                s_state.grade_rad   = v[6];  s_state.p_aux_w     = v[7];
                s_state.seq         = f.seq;
                s_state.host_t_us   = f.t_us;
                s_state.rx_t_us     = t_rx;
                xSemaphoreGive(s_state_mux);
            } else {
                s_diag.rx_bad++;
            }
        } else {
            s_diag.rx_timeouts++;
        }

        /* Control body. Phase 3 replaces this with PID plus the SAC setpoint. */
        TIMING_MARK_HIGH(TIMING_CH_CTRL);
        uint32_t t0 = (uint32_t) esp_timer_get_time();

        xSemaphoreTake(s_state_mux, portMAX_DELAY);
        float v_meas = s_state.v_mps;
        xSemaphoreGive(s_state_mux);
        s_torque_cmd = 10.0f * (15.0f - v_meas);   /* placeholder P controller */

        uint32_t dur = (uint32_t) esp_timer_get_time() - t0;
        if (dur > s_diag.ctrl_wcet_us) s_diag.ctrl_wcet_us = dur;
        TIMING_MARK_LOW(TIMING_CH_CTRL);

        /* Emit the actuation frame. */
        float act[3] = {s_torque_cmd, s_regen_blend, s_p_limit_w};
        m = evpil_pack(tx, sizeof tx, EVPIL_ACTUATION, seq,
                       (uint32_t) esp_timer_get_time(),
                       (const uint8_t *) act, sizeof act);
        if (m > 0) link_write(tx, (size_t) m);

        seq++;
        s_diag.loop_count++;
        vTaskDelayUntil(&next, pdMS_TO_TICKS(CTRL_PERIOD_MS));
    }
}

/* ---- core 1: inference, energy management, diagnostics ------------------ */

static void infer_task(void *arg)
{
    (void) arg;
    TickType_t next = xTaskGetTickCount();
    const uint32_t budget_us = 40000;   /* the G5 budget from the spec */

    for (;;) {
        TIMING_MARK_HIGH(TIMING_CH_INFER);
        uint32_t t0 = (uint32_t) esp_timer_get_time();

        /* Dummy load standing in for the forecaster. Phase 2 replaces this. */
        volatile int32_t acc = 0;
        for (int i = 0; i < 20000; i++) acc += i & 0x7F;

        uint32_t dur = (uint32_t) esp_timer_get_time() - t0;
        if (dur > s_diag.infer_wcet_us)  s_diag.infer_wcet_us = dur;
        if (dur > budget_us)             s_diag.infer_deadline_misses++;
        TIMING_MARK_LOW(TIMING_CH_INFER);

        vTaskDelayUntil(&next, pdMS_TO_TICKS(INFER_PERIOD_MS));
    }
}

static void ems_task(void *arg)
{
    (void) arg;
    TickType_t next = xTaskGetTickCount();
    for (;;) {
        /* Phase 3 replaces this with the SAC policy output plus safety clamps. */
        xSemaphoreTake(s_state_mux, portMAX_DELAY);
        float soc = s_state.soc_frac;
        xSemaphoreGive(s_state_mux);
        s_regen_blend = (soc > 0.95f) ? 0.0f : 0.5f;

        vTaskDelayUntil(&next, pdMS_TO_TICKS(EMS_PERIOD_MS));
    }
}

static void diag_task(void *arg)
{
    (void) arg;
    TickType_t next = xTaskGetTickCount();
    for (;;) {
        printf("EVPIL-DIAG loops=%u timeouts=%u bad=%u miss=%u "
               "ctrl_wcet_us=%u infer_wcet_us=%u rtt_max_us=%u "
               "heap=%u stack_ctrl=%u\n",
               (unsigned) s_diag.loop_count,   (unsigned) s_diag.rx_timeouts,
               (unsigned) s_diag.rx_bad,       (unsigned) s_diag.infer_deadline_misses,
               (unsigned) s_diag.ctrl_wcet_us, (unsigned) s_diag.infer_wcet_us,
               (unsigned) s_diag.rtt_max_us,
               (unsigned) esp_get_free_internal_heap_size(),
               (unsigned) uxTaskGetStackHighWaterMark(NULL));

        vTaskDelayUntil(&next, pdMS_TO_TICKS(DIAG_PERIOD_MS));
    }
}

void tasks_start(void)
{
    s_state_mux = xSemaphoreCreateMutex();
    configASSERT(s_state_mux);
    memset(&s_diag, 0, sizeof s_diag);

    /* Core 0 owns the hard real-time loop; core 1 owns everything else, so
       inference can never delay control. */
    xTaskCreatePinnedToCore(ctrl_task,  "ctrl",  4096, NULL, 20, NULL, 0);
    xTaskCreatePinnedToCore(infer_task, "infer", 8192, NULL,  5, NULL, 1);
    xTaskCreatePinnedToCore(ems_task,   "ems",   4096, NULL,  8, NULL, 1);
    xTaskCreatePinnedToCore(diag_task,  "diag",  4096, NULL,  1, NULL, 1);
}
```

`comm_rx`, `ctrl` and `comm_tx` are fused into `ctrl_task` rather than split into three tasks. The spec's table lists them separately, but they are strictly sequential within one 10 ms period and splitting them would add two context switches per period for no benefit. The GPIO channels still separate communication from control in the captured waveform, so the measurement granularity the spec asks for is preserved.

- [ ] **Step 3: Wire into main, build and flash**

```c
// firmware/main/main.c  -- replace the echo loop with this
#include "tasks.h"
#include "timing.h"

    link_init();
    timing_init();
    tasks_start();

    /* app_main returns; the pinned tasks keep running. */
```

```cmake
# firmware/main/CMakeLists.txt
idf_component_register(SRCS "main.c" "bench_mac.c" "protocol.c" "link.c"
                            "timing.c" "tasks.c"
                       INCLUDE_DIRS ".")
```

Run: `cd firmware && idf.py build && idf.py -p /dev/cu.usbmodem* flash`
Expected: build succeeds; `EVPIL-DIAG` lines appear twice per second on the monitor with `loops` climbing by about 500 each line.

- [ ] **Step 4: Write the host-side G3 harness**

```python
# scripts/measure_link.py
"""G3: characterise PIL link latency and reliability over a 10-minute run.

The ESP32 is the clock master. This responder waits for STEP_REQ, replies with
a STATE frame, and records the interval between consecutive requests. That
interval is the loop period as the MCU actually realises it.
"""

from __future__ import annotations

import argparse
import statistics
import time

import numpy as np

from evpil.link import SerialLink
from evpil.protocol import FrameType, pack_state


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", required=True, help="e.g. /dev/cu.usbserial-1420")
    ap.add_argument("--baud", type=int, default=921600)
    ap.add_argument("--minutes", type=float, default=10.0)
    args = ap.parse_args()

    intervals_ms: list[float] = []
    end = time.perf_counter() + args.minutes * 60.0
    last_req: float | None = None
    n_steps = 0

    with SerialLink(args.port, args.baud) as link:
        while time.perf_counter() < end:
            got = link.recv(timeout_s=0.5)
            if got is None:
                continue
            ftype, seq, t_us, _payload = got
            if ftype is not FrameType.STEP_REQ:
                continue

            now = time.perf_counter()
            if last_req is not None:
                intervals_ms.append((now - last_req) * 1000.0)
            last_req = now
            n_steps += 1

            # Constant dummy state; Task 16 substitutes the real plant.
            link.send(pack_state(seq, int(now * 1e6),
                                 [15.0, 0.0, 0.6, 40.0, 350.0, 22.0, 0.0, 500.0]))

        stats = link.stats

    arr = np.asarray(intervals_ms)
    jitter = arr - 10.0     # deviation from the nominal 10 ms period

    print(f"steps                 {n_steps}")
    print(f"duration              {args.minutes:.1f} min")
    print(f"period mean           {arr.mean():.4f} ms")
    print(f"period median         {statistics.median(arr):.4f} ms")
    print(f"jitter p50            {np.percentile(np.abs(jitter), 50):.4f} ms")
    print(f"jitter p99            {np.percentile(np.abs(jitter), 99):.4f} ms")
    print(f"jitter max            {np.abs(jitter).max():.4f} ms")
    print(f"frames_ok             {stats['frames_ok']}")
    print(f"frames_bad            {stats['frames_bad']}")
    print(f"frames_dropped        {stats['frames_dropped']}")

    p99 = float(np.percentile(np.abs(jitter), 99))
    dropped = stats["frames_dropped"] + stats["frames_bad"]
    ok = p99 <= 1.0 and dropped == 0
    print(f"\nG3 {'PASS' if ok else 'FAIL'}  (p99 <= 1.0 ms and zero dropped)")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run the G3 measurement**

Run: `python scripts/measure_link.py --port /dev/cu.usbserial-XXXX --minutes 10`
Expected: `G3 PASS`, with roughly 60,000 steps at a 10 ms period.

Simultaneously capture GPIO4 and GPIO6 on the AD3 using the settings in `docs/measurement-rig.md`. The externally measured period is the authoritative one; the host-side number can only ever be a lower bound on the true jitter, because the host is itself the source of some of it.

- [ ] **Step 6: Evaluate Gate G3**

Write `docs/g3-link-characterisation.md` with the full harness output, the AD3 waveform screenshot, and a stated verdict.

**If G3 fails**, work through these in order and record which one resolved it:

1. Rebuild with USB-Serial-JTAG instead of UART1 and re-measure. Some hosts do better on one than the other, and the spec leaves this open precisely so it can be decided on evidence.
2. Raise the baud rate to 2000000 and re-measure.
3. Close other applications on the Mac. An 8 GB machine under memory pressure will inject scheduler delays that no firmware change can absorb.
4. If p99 jitter remains above 1 ms, **re-scope the loop to 20 ms** and record that decision here with its measured justification. A 20 ms loop that provably meets its deadline is a far better result than a 10 ms loop that quietly misses.

- [ ] **Step 7: Commit**

```bash
git add firmware/main/tasks.c firmware/main/tasks.h firmware/main/main.c firmware/main/CMakeLists.txt firmware/sdkconfig.defaults scripts/measure_link.py docs/g3-link-characterisation.md
git commit -m "feat: FreeRTOS task set with clock-master loop, gate G3 measured"
```

---

## Track B: Plant and Data

Track B shares no code with Track A until Phase 2. The two may be run in parallel by two people, or sequentially by one.

### Task 8: Canonical schema and BMW i3 loader

**Files:**
- Create: `src/evpil/data/__init__.py`
- Create: `src/evpil/data/schema.py`
- Create: `src/evpil/data/i3_loader.py`
- Test: `tests/data/test_schema.py`
- Test: `tests/data/test_i3_loader.py`
- Create: `docs/dataset-provenance.md`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `CANONICAL_COLUMNS: tuple[str, ...]` and `CANONICAL_UNITS: dict[str, str]`
  - `validate_frame(df: pd.DataFrame) -> None`, raising `SchemaError`
  - `load_trip(path: Path, mapping: dict[str, str]) -> pd.DataFrame`
  - `load_all_trips(root: Path, mapping: dict[str, str]) -> pd.DataFrame` with a `trip_id` column
  - Tasks 9, 15 and 16 all consume the canonical frame.

The real column names in the IEEE DataPort archive are **not known at the time of writing** and must not be guessed. Step 1 inspects the files and records the actual names; the mapping dictionary is data, not code, so discovering it is a documented step rather than an assumption baked into the loader. Tests use a synthetic fixture in canonical form, so they are independent of whatever the archive turns out to call its columns.

- [ ] **Step 1: Acquire the dataset and record its real schema**

Download from IEEE DataPort, DOI `10.21227/6jr9-5235` ("Battery and Heating Data in Real Driving Cycles", Steinstraeter, Buberger, Trifonov, 2020). The Kaggle mirror is `atechnohazard/battery-and-heating-data-in-real-driving-cycles`.

Place the extracted trip files under `data/raw/i3/`. Add `data/` to `.gitignore` — the archive is large and redistributing it may not be permitted.

Inspect one file and record what is actually there:

```bash
ls data/raw/i3/ | head -20
python -c "
import pandas as pd, sys, glob
f = sorted(glob.glob('data/raw/i3/*.csv'))[0]
df = pd.read_csv(f)
print('file:', f)
print('rows:', len(df))
print('columns:')
for c in df.columns:
    print('   ', repr(c), df[c].dtype)
print(df.head(3).T)
"
```

Write `docs/dataset-provenance.md` recording: the DOI and full citation, the licence terms, the download date, the file count, the exact column names with units as printed above, the observed sample interval, and any files that fail to parse.

Confirm the 10 Hz sample rate from the timestamp column rather than assuming it.

- [ ] **Step 2: Write the failing tests**

```python
# tests/data/test_schema.py
import pandas as pd
import pytest
from evpil.data.schema import CANONICAL_COLUMNS, SchemaError, validate_frame


# A physically plausible row. An all-zeros frame would violate the validator's
# own v_batt_v range and t_s monotonicity rules, so it cannot serve as the
# "good" fixture.
_VALID_ROW = {
    "t_s": 0.0, "v_mps": 10.0, "a_mps2": 0.0, "soc_frac": 0.6,
    "i_batt_a": 20.0, "v_batt_v": 350.0, "t_ambient_c": 20.0,
    "t_batt_c": 25.0, "elevation_m": 100.0, "grade_rad": 0.0, "p_aux_w": 500.0,
}


def _good_frame(n: int = 5) -> pd.DataFrame:
    df = pd.DataFrame({c: [_VALID_ROW[c]] * n for c in CANONICAL_COLUMNS})
    df["t_s"] = [i * 0.1 for i in range(n)]   # must be strictly monotonic
    return df


def test_canonical_columns_are_stable():
    assert CANONICAL_COLUMNS == (
        "t_s", "v_mps", "a_mps2", "soc_frac", "i_batt_a", "v_batt_v",
        "t_ambient_c", "t_batt_c", "elevation_m", "grade_rad", "p_aux_w",
    )


def test_validate_accepts_good_frame():
    validate_frame(_good_frame())


def test_validate_rejects_missing_column():
    df = _good_frame().drop(columns=["soc_frac"])
    with pytest.raises(SchemaError, match="missing"):
        validate_frame(df)


def test_validate_rejects_nan():
    df = _good_frame()
    df.loc[2, "v_mps"] = float("nan")
    with pytest.raises(SchemaError, match="NaN"):
        validate_frame(df)


def test_validate_rejects_soc_out_of_range():
    df = _good_frame()
    df.loc[1, "soc_frac"] = 1.4
    with pytest.raises(SchemaError, match="soc_frac"):
        validate_frame(df)


def test_validate_rejects_non_monotonic_time():
    df = _good_frame()
    df["t_s"] = [0.0, 0.1, 0.05, 0.3, 0.4]
    with pytest.raises(SchemaError, match="monotonic"):
        validate_frame(df)
```

```python
# tests/data/test_i3_loader.py
import pandas as pd
import pytest
from evpil.data.i3_loader import load_all_trips, load_trip
from evpil.data.schema import CANONICAL_COLUMNS

MAPPING = {
    "Time [s]": "t_s",
    "Velocity [km/h]": "v_mps",
    "SoC [%]": "soc_frac",
    "Battery Current [A]": "i_batt_a",
    "Battery Voltage [V]": "v_batt_v",
    "Ambient Temperature [C]": "t_ambient_c",
    "Battery Temperature [C]": "t_batt_c",
    "Elevation [m]": "elevation_m",
    "Heating Power [W]": "p_aux_w",
}


@pytest.fixture
def raw_csv(tmp_path):
    """A file in the archive's *raw* form: km/h, percent SoC, no derived columns."""
    df = pd.DataFrame({
        "Time [s]": [0.0, 0.1, 0.2, 0.3, 0.4],
        "Velocity [km/h]": [0.0, 36.0, 72.0, 72.0, 36.0],
        "SoC [%]": [80.0, 79.9, 79.8, 79.7, 79.6],
        "Battery Current [A]": [0.0, 10.0, 20.0, 20.0, -5.0],
        "Battery Voltage [V]": [350.0, 349.0, 348.0, 348.0, 351.0],
        "Ambient Temperature [C]": [20.0] * 5,
        "Battery Temperature [C]": [25.0] * 5,
        "Elevation [m]": [100.0, 100.0, 100.5, 101.0, 101.0],
        "Heating Power [W]": [500.0] * 5,
    })
    p = tmp_path / "TripA01.csv"
    df.to_csv(p, index=False)
    return p


def test_load_trip_produces_canonical_columns(raw_csv):
    df = load_trip(raw_csv, MAPPING)
    assert tuple(df.columns[: len(CANONICAL_COLUMNS)]) == CANONICAL_COLUMNS


def test_velocity_converted_to_mps(raw_csv):
    df = load_trip(raw_csv, MAPPING)
    # 36 km/h == 10 m/s
    assert df["v_mps"].tolist() == pytest.approx([0.0, 10.0, 20.0, 20.0, 10.0])


def test_soc_converted_to_fraction(raw_csv):
    df = load_trip(raw_csv, MAPPING)
    assert df["soc_frac"].iloc[0] == pytest.approx(0.80)


def test_acceleration_derived_from_velocity(raw_csv):
    df = load_trip(raw_csv, MAPPING)
    # First sample is backfilled from the second; 0 -> 10 m/s over 0.1 s is 100 m/s^2.
    assert df["a_mps2"].iloc[1] == pytest.approx(100.0, rel=1e-6)
    assert df["a_mps2"].iloc[3] == pytest.approx(0.0, abs=1e-9)


def test_grade_derived_from_elevation(raw_csv):
    df = load_trip(raw_csv, MAPPING)
    # Sample 2: elevation rises 0.5 m while 20 m/s * 0.1 s = 2.0 m of road is
    # covered. v*dt is distance along the road surface, so sin(theta) = dz/ds
    # and theta = arcsin(0.25) = 0.25268026 rad.
    assert df["grade_rad"].iloc[2] == pytest.approx(0.25268026, rel=1e-5)


def test_grade_is_zero_when_stationary(raw_csv):
    df = load_trip(raw_csv, MAPPING)
    assert df["grade_rad"].iloc[0] == pytest.approx(0.0)


def test_load_all_trips_tags_trip_id(raw_csv):
    df = load_all_trips(raw_csv.parent, MAPPING)
    assert set(df["trip_id"].unique()) == {"TripA01"}
    assert len(df) == 5
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/data/ -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'evpil.data'`

- [ ] **Step 4: Write the implementation**

```python
# src/evpil/data/__init__.py
"""Dataset loading, canonicalisation, splitting and leakage guards."""
```

```python
# src/evpil/data/schema.py
"""The canonical signal schema every downstream component consumes.

One schema, one set of units. Source-specific column names and units are
normalised at load time so that nothing downstream needs to know which
dataset a row came from.
"""

from __future__ import annotations

import pandas as pd

CANONICAL_COLUMNS: tuple[str, ...] = (
    "t_s",           # seconds since trip start
    "v_mps",         # vehicle speed, metres per second
    "a_mps2",        # longitudinal acceleration, metres per second squared
    "soc_frac",      # state of charge, 0.0 to 1.0
    "i_batt_a",      # battery current, amperes, positive = discharge
    "v_batt_v",      # battery terminal voltage, volts
    "t_ambient_c",   # ambient temperature, degrees Celsius
    "t_batt_c",      # battery temperature, degrees Celsius
    "elevation_m",   # elevation above datum, metres
    "grade_rad",     # road grade angle, radians, positive = uphill
    "p_aux_w",       # auxiliary and HVAC electrical power, watts
)

CANONICAL_UNITS: dict[str, str] = {
    "t_s": "s", "v_mps": "m/s", "a_mps2": "m/s^2", "soc_frac": "-",
    "i_batt_a": "A", "v_batt_v": "V", "t_ambient_c": "degC",
    "t_batt_c": "degC", "elevation_m": "m", "grade_rad": "rad", "p_aux_w": "W",
}

# Sanity ranges. Deliberately generous: these catch unit-conversion mistakes
# and corrupt rows, not unusual-but-real driving.
_RANGES: dict[str, tuple[float, float]] = {
    "v_mps": (-1.0, 70.0),
    "a_mps2": (-150.0, 150.0),
    "soc_frac": (0.0, 1.0),
    "i_batt_a": (-600.0, 600.0),
    "v_batt_v": (200.0, 450.0),
    "t_ambient_c": (-40.0, 60.0),
    "t_batt_c": (-40.0, 80.0),
    "grade_rad": (-0.35, 0.35),
    "p_aux_w": (-1000.0, 12000.0),
}


class SchemaError(ValueError):
    """Raised when a DataFrame does not satisfy the canonical schema."""


def validate_frame(df: pd.DataFrame) -> None:
    missing = [c for c in CANONICAL_COLUMNS if c not in df.columns]
    if missing:
        raise SchemaError(f"missing columns: {missing}")

    for col in CANONICAL_COLUMNS:
        if df[col].isna().any():
            n = int(df[col].isna().sum())
            raise SchemaError(f"column {col!r} contains {n} NaN values")

    for col, (lo, hi) in _RANGES.items():
        vmin, vmax = float(df[col].min()), float(df[col].max())
        if vmin < lo or vmax > hi:
            raise SchemaError(
                f"column {col!r} out of range: [{vmin:.4g}, {vmax:.4g}] "
                f"outside [{lo}, {hi}]"
            )

    t = df["t_s"].to_numpy()
    if len(t) > 1 and not (t[1:] > t[:-1]).all():
        raise SchemaError("column 't_s' is not strictly monotonic increasing")
```

```python
# src/evpil/data/i3_loader.py
"""Load BMW i3 real-driving trips into the canonical schema.

The archive's own column names are recorded in docs/dataset-provenance.md and
supplied here as a mapping, so this module never hardcodes names it has not
seen. Derived signals (acceleration, grade) are computed here rather than
trusted from the source, since their definitions vary between datasets.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from evpil.data.schema import CANONICAL_COLUMNS, validate_frame

KMH_TO_MPS = 1.0 / 3.6
PERCENT_TO_FRAC = 0.01

# Below this speed the horizontal distance per sample is too small for
# elevation differences to give a meaningful grade, so grade is set to zero.
_MIN_SPEED_FOR_GRADE_MPS = 0.5


def load_trip(path: Path, mapping: dict[str, str]) -> pd.DataFrame:
    """Load one trip CSV and return it in the canonical schema.

    `mapping` maps source column names to canonical names. Source columns
    absent from the mapping are dropped.
    """
    raw = pd.read_csv(path)

    unknown = [src for src in mapping if src not in raw.columns]
    if unknown:
        raise KeyError(f"{path.name}: mapping names absent from file: {unknown}")

    df = raw[list(mapping)].rename(columns=mapping).copy()

    # Unit normalisation. The archive stores km/h and percent.
    df["v_mps"] = df["v_mps"] * KMH_TO_MPS
    df["soc_frac"] = df["soc_frac"] * PERCENT_TO_FRAC

    dt = np.diff(df["t_s"].to_numpy(), prepend=np.nan)

    # Acceleration by backward difference; the first sample is backfilled.
    dv = np.diff(df["v_mps"].to_numpy(), prepend=np.nan)
    a = dv / dt
    df["a_mps2"] = pd.Series(a).bfill().fillna(0.0).to_numpy()

    # Grade from elevation change over distance travelled in the same interval.
    dz = np.diff(df["elevation_m"].to_numpy(), prepend=np.nan)
    ds = df["v_mps"].to_numpy() * dt
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(df["v_mps"].to_numpy() >= _MIN_SPEED_FOR_GRADE_MPS,
                         dz / ds, 0.0)
    ratio = np.clip(np.nan_to_num(ratio, nan=0.0, posinf=0.0, neginf=0.0), -1.0, 1.0)
    df["grade_rad"] = np.arcsin(ratio)

    if "t_batt_c" not in df.columns:
        df["t_batt_c"] = df["t_ambient_c"]

    df = df[list(CANONICAL_COLUMNS)]
    validate_frame(df)
    return df


def load_all_trips(root: Path, mapping: dict[str, str]) -> pd.DataFrame:
    """Load every CSV under `root`, tagging each with a `trip_id` from its stem."""
    root = Path(root)
    paths = sorted(root.glob("*.csv"))
    if not paths:
        raise FileNotFoundError(f"no CSV files under {root}")

    frames = []
    for p in paths:
        trip = load_trip(p, mapping)
        trip["trip_id"] = p.stem
        frames.append(trip)

    return pd.concat(frames, ignore_index=True)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/data/ -v`
Expected: 13 passed

- [ ] **Step 6: Load the real dataset and record what happened**

```bash
python -c "
from pathlib import Path
from evpil.data.i3_loader import load_all_trips
MAPPING = {}  # paste the real mapping recorded in Step 1
df = load_all_trips(Path('data/raw/i3'), MAPPING)
print('trips:', df.trip_id.nunique())
print('rows :', len(df))
print(df.groupby('trip_id').t_s.max().describe())
print(df[['v_mps','soc_frac','i_batt_a','t_ambient_c','p_aux_w']].describe())
"
```

Append the output to `docs/dataset-provenance.md`, along with any trips that
`validate_frame` rejected and why. A rejected trip is a finding, not a nuisance —
record it rather than silently dropping it.

- [ ] **Step 7: Commit**

```bash
git add src/evpil/data/ tests/data/ docs/dataset-provenance.md .gitignore
git commit -m "feat: canonical schema and BMW i3 trip loader"
```

---

### Task 9: Trip-level splits and leakage guards

**Files:**
- Create: `src/evpil/data/splits.py`
- Create: `src/evpil/data/guards.py`
- Test: `tests/data/test_splits.py`
- Test: `tests/data/test_guards.py`

**Interfaces:**
- Consumes: `load_all_trips` and `CANONICAL_COLUMNS` from Task 8.
- Produces:
  - `Split` dataclass with `train: list[str]`, `val: list[str]`, `test: list[str]`
  - `make_trip_splits(df, *, seed, val_frac=0.2, test_frac=0.2) -> Split`
  - `apply_split(df, split) -> tuple[DataFrame, DataFrame, DataFrame]`
  - `assert_no_trip_overlap(split) -> None`
  - `audit_features(feature_cols, target_col, forbidden) -> None` raising `LeakageError`
  - `shuffled_label_control(fit_fn, X, y, seed) -> float`
  - Every modelling task in Phase 2 calls these before training.

This task implements the three guards from spec section 6.4. They exist because the prior work's headline numbers were produced by row-level splitting (defect D2) and by feeding a target-derived column back in as a feature (defect D5).

- [ ] **Step 1: Write the failing tests**

```python
# tests/data/test_splits.py
import numpy as np
import pandas as pd
import pytest
from evpil.data.splits import Split, apply_split, assert_no_trip_overlap, make_trip_splits


def _df(n_trips: int = 20, rows: int = 50) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    parts = []
    for i in range(n_trips):
        parts.append(pd.DataFrame({
            "trip_id": [f"T{i:02d}"] * rows,
            "t_s": np.arange(rows) * 0.1,
            "t_ambient_c": [float(rng.integers(-5, 35))] * rows,
            "v_mps": rng.normal(15, 3, rows),
        }))
    return pd.concat(parts, ignore_index=True)


def test_split_covers_every_trip_exactly_once():
    df = _df()
    s = make_trip_splits(df, seed=42)
    allocated = s.train + s.val + s.test
    assert sorted(allocated) == sorted(df.trip_id.unique())
    assert len(allocated) == len(set(allocated))


def test_split_is_deterministic_for_a_seed():
    df = _df()
    assert make_trip_splits(df, seed=7) == make_trip_splits(df, seed=7)


def test_different_seeds_give_different_splits():
    df = _df()
    assert make_trip_splits(df, seed=1) != make_trip_splits(df, seed=2)


def test_split_respects_requested_fractions():
    df = _df(n_trips=20)
    s = make_trip_splits(df, seed=0, val_frac=0.2, test_frac=0.2)
    assert len(s.val) == 4
    assert len(s.test) == 4
    assert len(s.train) == 12


def test_apply_split_yields_disjoint_row_sets():
    df = _df()
    s = make_trip_splits(df, seed=3)
    tr, va, te = apply_split(df, s)

    assert set(tr.trip_id) & set(va.trip_id) == set()
    assert set(tr.trip_id) & set(te.trip_id) == set()
    assert set(va.trip_id) & set(te.trip_id) == set()
    assert len(tr) + len(va) + len(te) == len(df)


def test_overlap_assertion_catches_a_bad_split():
    bad = Split(train=["A", "B"], val=["B"], test=["C"])
    with pytest.raises(AssertionError, match="overlap"):
        assert_no_trip_overlap(bad)


def test_stratification_spreads_temperature_across_splits():
    df = _df(n_trips=30)
    s = make_trip_splits(df, seed=11)

    def mean_temp(trips):
        return df[df.trip_id.isin(trips)].t_ambient_c.mean()

    # Stratified sampling should keep split means near the overall mean.
    overall = df.t_ambient_c.mean()
    for trips in (s.train, s.val, s.test):
        assert abs(mean_temp(trips) - overall) < 8.0
```

```python
# tests/data/test_guards.py
import numpy as np
import pytest
from evpil.data.guards import LeakageError, audit_features, shuffled_label_control


def test_audit_passes_for_clean_feature_set():
    audit_features(
        feature_cols=["v_mps", "a_mps2", "soc_frac"],
        target_col="p_batt_w",
        forbidden={"p_batt_w": ["v_batt_v", "i_batt_a"]},
    )


def test_audit_rejects_target_as_its_own_feature():
    with pytest.raises(LeakageError, match="target"):
        audit_features(
            feature_cols=["v_mps", "p_batt_w"],
            target_col="p_batt_w",
            forbidden={},
        )


def test_audit_rejects_declared_derived_feature():
    """This is exactly defect D5: Range was a feature and Range came from speed."""
    with pytest.raises(LeakageError, match="i_batt_a"):
        audit_features(
            feature_cols=["v_mps", "i_batt_a"],
            target_col="p_batt_w",
            forbidden={"p_batt_w": ["v_batt_v", "i_batt_a"]},
        )


def test_shuffled_label_control_collapses_for_an_honest_model():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(400, 4))
    y = X @ np.array([1.0, -2.0, 0.5, 3.0])

    def fit_fn(Xtr, ytr, Xte):
        coef, *_ = np.linalg.lstsq(Xtr, ytr, rcond=None)
        return Xte @ coef

    r2 = shuffled_label_control(fit_fn, X, y, seed=0)
    assert r2 < 0.1, f"shuffled-label R2 was {r2:.3f}; expected near zero"


def test_shuffled_label_control_would_detect_leakage():
    """Sanity check on the R2 computation itself.

    A fit_fn with oracle access to the shuffled holdout targets must score near
    1.0. If it did not, the control could not detect leakage when it mattered.
    """
    rng = np.random.default_rng(1)
    X = rng.normal(size=(200, 3))
    y = rng.normal(size=200)

    # Reproduce the guard's internal shuffle (same seed) to obtain y_te.
    y_shuffled = np.array(y, copy=True)
    np.random.default_rng(0).shuffle(y_shuffled)
    y_te = y_shuffled[-50:]          # holdout_frac 0.25 of 200 rows

    def oracle_fit(Xtr, ytr, Xte):
        return y_te

    r2 = shuffled_label_control(oracle_fit, X, y, seed=0)
    assert r2 > 0.99, "an oracle model must score high, or the control is blind"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/data/test_splits.py tests/data/test_guards.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'evpil.data.splits'`

- [ ] **Step 3: Write the implementation**

```python
# src/evpil/data/splits.py
"""Trip-level splits with temperature stratification.

Splitting at the row level on temporally correlated data puts neighbouring
samples on both sides of the boundary, so the test score measures memorisation
rather than generalisation. Every split here is at trip granularity.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Split:
    train: list[str]
    val: list[str]
    test: list[str]

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Split):
            return NotImplemented
        return (sorted(self.train) == sorted(other.train)
                and sorted(self.val) == sorted(other.val)
                and sorted(self.test) == sorted(other.test))


def make_trip_splits(
    df: pd.DataFrame,
    *,
    seed: int,
    val_frac: float = 0.2,
    test_frac: float = 0.2,
    stratify_col: str = "t_ambient_c",
) -> Split:
    """Partition trips into train/val/test, stratified by mean ambient temperature.

    The i3 archive spans winter and summer, and HVAC load is the dominant
    confounder on energy consumption, so an unstratified split risks putting
    all the cold trips on one side.
    """
    per_trip = (df.groupby("trip_id")[stratify_col].mean()
                  .sort_values(kind="mergesort"))
    trips = per_trip.index.to_numpy()

    n = len(trips)
    n_val = int(round(n * val_frac))
    n_test = int(round(n * test_frac))
    if n_val + n_test >= n:
        raise ValueError(f"val_frac + test_frac leaves no training trips (n={n})")

    # Walk the temperature-ordered list in strata of 5 and shuffle within each,
    # so every split draws from the full temperature range.
    rng = np.random.default_rng(seed)
    order: list[str] = []
    for start in range(0, n, 5):
        block = list(trips[start : start + 5])
        rng.shuffle(block)
        order.extend(block)

    # Deal round-robin so strata stay balanced across the three splits.
    val: list[str] = []
    test: list[str] = []
    train: list[str] = []
    for i, trip in enumerate(order):
        if len(val) < n_val and i % 5 == 0:
            val.append(trip)
        elif len(test) < n_test and i % 5 == 1:
            test.append(trip)
        else:
            train.append(trip)

    # Round-robin may under-fill; top up from the largest split.
    while len(val) < n_val:
        val.append(train.pop())
    while len(test) < n_test:
        test.append(train.pop())

    return Split(train=sorted(train), val=sorted(val), test=sorted(test))


def assert_no_trip_overlap(split: Split) -> None:
    tr, va, te = set(split.train), set(split.val), set(split.test)
    for a, b, names in ((tr, va, "train/val"), (tr, te, "train/test"),
                        (va, te, "val/test")):
        shared = a & b
        assert not shared, f"trip overlap between {names}: {sorted(shared)}"


def apply_split(
    df: pd.DataFrame, split: Split
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    assert_no_trip_overlap(split)
    return (
        df[df.trip_id.isin(split.train)].reset_index(drop=True),
        df[df.trip_id.isin(split.val)].reset_index(drop=True),
        df[df.trip_id.isin(split.test)].reset_index(drop=True),
    )
```

```python
# src/evpil/data/guards.py
"""Leakage guards, run before any model is trained.

Implements spec section 6.4. These exist because the predecessor work reported
metrics produced by row-level splitting and by feeding a target-derived column
back in as an input feature.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence

import numpy as np


class LeakageError(AssertionError):
    """Raised when a feature set can see its own target."""


def audit_features(
    feature_cols: Sequence[str],
    target_col: str,
    forbidden: Mapping[str, Iterable[str]],
) -> None:
    """Fail if any feature is the target, or is declared derived from it.

    `forbidden` maps a target name to columns that must never be used to
    predict it. The mapping is written down deliberately, per target, because
    it encodes domain knowledge no automatic check can infer.
    """
    if target_col in feature_cols:
        raise LeakageError(f"target {target_col!r} is present in its own feature set")

    banned = set(forbidden.get(target_col, ()))
    hits = sorted(banned.intersection(feature_cols))
    if hits:
        raise LeakageError(
            f"features {hits} are derived from target {target_col!r} "
            f"and must not be used to predict it"
        )


def shuffled_label_control(
    fit_fn: Callable[[np.ndarray, np.ndarray, np.ndarray], np.ndarray],
    X: np.ndarray,
    y: np.ndarray,
    seed: int,
    holdout_frac: float = 0.25,
) -> float:
    """Train on shuffled targets and return R^2 on a held-out shuffled set.

    An honest pipeline scores near zero. A materially positive score means the
    model can see the evaluation targets through some path, and the pipeline is
    broken regardless of how good the real numbers look.
    """
    rng = np.random.default_rng(seed)
    y_shuffled = np.array(y, copy=True)
    rng.shuffle(y_shuffled)

    n_hold = max(1, int(len(X) * holdout_frac))
    X_tr, y_tr = X[:-n_hold], y_shuffled[:-n_hold]
    X_te, y_te = X[-n_hold:], y_shuffled[-n_hold:]

    pred = np.asarray(fit_fn(X_tr, y_tr, X_te)).ravel()

    ss_res = float(np.sum((y_te - pred) ** 2))
    ss_tot = float(np.sum((y_te - y_te.mean()) ** 2))
    return 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/data/ -v`
Expected: 25 passed

- [ ] **Step 5: Generate and freeze the real split**

```bash
python -c "
import json
from pathlib import Path
from evpil.data.i3_loader import load_all_trips
from evpil.data.splits import make_trip_splits, assert_no_trip_overlap
MAPPING = {}  # the real mapping from Task 8
df = load_all_trips(Path('data/raw/i3'), MAPPING)
s = make_trip_splits(df, seed=20260830)
assert_no_trip_overlap(s)
Path('data/splits.json').write_text(json.dumps(
    {'seed': 20260830, 'train': s.train, 'val': s.val, 'test': s.test}, indent=2))
print('train', len(s.train), 'val', len(s.val), 'test', len(s.test))
"
git add -f data/splits.json
```

`data/splits.json` is force-added despite `data/` being ignored: the split must be version-controlled so results stay reproducible, and it contains only trip names.

**From this point, the trips listed under `test` are not read again until the end of the project.** Not for hyperparameters, not for quantisation calibration, not for sanity checks.

- [ ] **Step 6: Commit**

```bash
git add src/evpil/data/splits.py src/evpil/data/guards.py tests/data/test_splits.py tests/data/test_guards.py data/splits.json
git commit -m "feat: trip-level splits and leakage guards"
```

---

### Task 10: Longitudinal dynamics

**Files:**
- Create: `src/evpil/plant/__init__.py`
- Create: `src/evpil/plant/longitudinal.py`
- Test: `tests/plant/test_longitudinal.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `RoadLoad` NamedTuple with fields `rolling_n`, `aero_n`, `grade_n`, `inertia_n`, `tractive_n`
  - `road_load(v_mps, a_mps2, grade_rad, *, mass_kg, c_rr, cd, frontal_area_m2, rho_kgm3=1.2, g=9.81) -> RoadLoad`
  - `mechanical_power_w(load: RoadLoad, v_mps: float) -> float`
  - Tasks 14, 15 and 16 consume both.

This module supplies all four force terms. The predecessor work omitted rolling resistance and the inertial term entirely (defect D6), which is why its "physics-based" range figures could not be reproduced.

- [ ] **Step 1: Write the failing test**

```python
# tests/plant/test_longitudinal.py
import math
import pytest
from evpil.plant.longitudinal import mechanical_power_w, road_load

PARAMS = dict(mass_kg=1400.0, c_rr=0.01, cd=0.29, frontal_area_m2=2.38,
              rho_kgm3=1.2, g=9.81)


def test_all_four_terms_on_the_flat_at_constant_speed():
    load = road_load(v_mps=20.0, a_mps2=0.0, grade_rad=0.0, **PARAMS)
    assert load.rolling_n == pytest.approx(137.340000, rel=1e-9)
    assert load.aero_n == pytest.approx(165.648000, rel=1e-9)
    assert load.grade_n == pytest.approx(0.0, abs=1e-12)
    assert load.inertia_n == pytest.approx(0.0, abs=1e-12)
    assert load.tractive_n == pytest.approx(302.988000, rel=1e-9)


def test_power_on_the_flat_at_constant_speed():
    load = road_load(v_mps=20.0, a_mps2=0.0, grade_rad=0.0, **PARAMS)
    assert mechanical_power_w(load, 20.0) == pytest.approx(6059.760000, rel=1e-9)


def test_climbing_while_accelerating():
    load = road_load(v_mps=10.0, a_mps2=1.0, grade_rad=math.radians(5.0), **PARAMS)
    assert load.rolling_n == pytest.approx(136.817380, rel=1e-6)
    assert load.aero_n == pytest.approx(41.412000, rel=1e-9)
    assert load.grade_n == pytest.approx(1196.996971, rel=1e-6)
    assert load.inertia_n == pytest.approx(1400.0, rel=1e-12)
    assert load.tractive_n == pytest.approx(2775.226351, rel=1e-6)
    assert mechanical_power_w(load, 10.0) == pytest.approx(27752.263507, rel=1e-6)


def test_aero_force_scales_with_the_square_of_speed():
    a = road_load(v_mps=10.0, a_mps2=0.0, grade_rad=0.0, **PARAMS).aero_n
    b = road_load(v_mps=20.0, a_mps2=0.0, grade_rad=0.0, **PARAMS).aero_n
    assert b == pytest.approx(4.0 * a, rel=1e-12)


def test_descending_gives_negative_grade_force():
    load = road_load(v_mps=15.0, a_mps2=0.0, grade_rad=math.radians(-5.0), **PARAMS)
    assert load.grade_n < 0
    assert load.grade_n == pytest.approx(-1196.996971, rel=1e-6)


def test_rolling_resistance_opposes_motion_when_reversing():
    fwd = road_load(v_mps=5.0, a_mps2=0.0, grade_rad=0.0, **PARAMS)
    rev = road_load(v_mps=-5.0, a_mps2=0.0, grade_rad=0.0, **PARAMS)
    assert fwd.rolling_n > 0
    assert rev.rolling_n < 0
    assert rev.rolling_n == pytest.approx(-fwd.rolling_n, rel=1e-12)


def test_rolling_and_aero_vanish_at_standstill():
    load = road_load(v_mps=0.0, a_mps2=0.0, grade_rad=0.0, **PARAMS)
    assert load.rolling_n == pytest.approx(0.0, abs=1e-12)
    assert load.aero_n == pytest.approx(0.0, abs=1e-12)


def test_aero_force_opposes_motion_when_reversing():
    rev = road_load(v_mps=-20.0, a_mps2=0.0, grade_rad=0.0, **PARAMS)
    assert rev.aero_n == pytest.approx(-165.648000, rel=1e-9)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/plant/test_longitudinal.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'evpil.plant'`

- [ ] **Step 3: Write the implementation**

```python
# src/evpil/plant/__init__.py
"""Physics EV plant: road load, battery, motor, auxiliary and regeneration."""
```

```python
# src/evpil/plant/longitudinal.py
"""Longitudinal vehicle dynamics.

All four resistance terms are present. Sign conventions: positive v is forward,
positive grade is uphill, and rolling and aerodynamic forces always oppose
motion.
"""

from __future__ import annotations

import math
from typing import NamedTuple


class RoadLoad(NamedTuple):
    rolling_n: float
    aero_n: float
    grade_n: float
    inertia_n: float
    tractive_n: float


def road_load(
    v_mps: float,
    a_mps2: float,
    grade_rad: float,
    *,
    mass_kg: float,
    c_rr: float,
    cd: float,
    frontal_area_m2: float,
    rho_kgm3: float = 1.2,
    g: float = 9.81,
) -> RoadLoad:
    """Return the four force components and their sum, in newtons.

    `tractive_n` is the force the powertrain must supply. It is negative when
    the vehicle is being decelerated or is descending, which is the condition
    under which regeneration is available.
    """
    direction = 0.0 if v_mps == 0.0 else math.copysign(1.0, v_mps)

    rolling = c_rr * mass_kg * g * math.cos(grade_rad) * direction
    aero = 0.5 * rho_kgm3 * cd * frontal_area_m2 * v_mps * v_mps * direction
    grade = mass_kg * g * math.sin(grade_rad)
    inertia = mass_kg * a_mps2

    return RoadLoad(
        rolling_n=rolling,
        aero_n=aero,
        grade_n=grade,
        inertia_n=inertia,
        tractive_n=rolling + aero + grade + inertia,
    )


def mechanical_power_w(load: RoadLoad, v_mps: float) -> float:
    """Mechanical power at the wheels, in watts. Negative means regeneration."""
    return load.tractive_n * v_mps
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/plant/test_longitudinal.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add src/evpil/plant/__init__.py src/evpil/plant/longitudinal.py tests/plant/test_longitudinal.py
git commit -m "feat: longitudinal dynamics with all four road-load terms"
```

---

### Task 11: Battery equivalent-circuit model

**Files:**
- Create: `src/evpil/plant/battery.py`
- Test: `tests/plant/test_battery.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `BatteryParams` dataclass: `capacity_ah`, `ocv_soc_points`, `ocv_volts`, `r0_ohm`, `r1_ohm`, `c1_farad`, `i_discharge_max_a`, `i_charge_max_a`, `soc_min`, `soc_max`, `r0_temp_coeff_per_c`, `t_ref_c`
  - `BatteryState` dataclass: `soc_frac`, `v_rc_v`, `t_batt_c`
  - `ocv_v(params, soc_frac) -> float`
  - `r0_at(params, t_batt_c) -> float`
  - `terminal_voltage_v(params, state, i_a) -> float`
  - `battery_step(params, state, i_a, dt_s) -> BatteryState`
  - `clamp_current(params, state, i_a) -> float`
  - Tasks 14, 15 and 16 consume these.

First-order Thevenin: one series resistance plus one RC pair. Current sign convention is **positive for discharge**, matching the i3 archive.

Temperature-dependent `r0` is deliberately included. It is one of the effects the nominal physics of the predecessor work omitted, and it is precisely the kind of residual a physics-informed model can be shown to learn in Phase 2 — so it must be in the plant for that comparison to mean anything.

- [ ] **Step 1: Write the failing test**

```python
# tests/plant/test_battery.py
import pytest
from evpil.plant.battery import (
    BatteryParams, BatteryState, battery_step, clamp_current, current_for_power,
    emf_v, max_power_w, ocv_v, r0_at, terminal_voltage_v,
)

P = BatteryParams(
    capacity_ah=60.0,
    ocv_soc_points=(0.0, 0.5, 1.0),
    ocv_volts=(300.0, 350.0, 400.0),
    r0_ohm=0.05,
    r1_ohm=0.01,
    c1_farad=2000.0,
    i_discharge_max_a=400.0,
    i_charge_max_a=150.0,
    soc_min=0.05,
    soc_max=0.98,
    r0_temp_coeff_per_c=-0.004,
    t_ref_c=25.0,
)


def test_ocv_at_table_points():
    assert ocv_v(P, 0.0) == pytest.approx(300.0)
    assert ocv_v(P, 0.5) == pytest.approx(350.0)
    assert ocv_v(P, 1.0) == pytest.approx(400.0)


def test_ocv_interpolates_linearly_between_points():
    assert ocv_v(P, 0.25) == pytest.approx(325.0)
    assert ocv_v(P, 0.75) == pytest.approx(375.0)


def test_ocv_clamps_outside_the_table():
    assert ocv_v(P, -0.2) == pytest.approx(300.0)
    assert ocv_v(P, 1.5) == pytest.approx(400.0)


def test_r0_at_reference_temperature():
    assert r0_at(P, 25.0) == pytest.approx(0.05)


def test_r0_rises_as_the_cell_gets_colder():
    cold = r0_at(P, 0.0)
    hot = r0_at(P, 45.0)
    assert cold > 0.05 > hot
    # 0.05 * (1 + -0.004 * (0 - 25)) == 0.05 * 1.1
    assert cold == pytest.approx(0.055, rel=1e-9)


def test_r0_never_goes_non_positive_at_extreme_heat():
    assert r0_at(P, 500.0) > 0.0


def test_terminal_voltage_drops_under_discharge():
    st = BatteryState(soc_frac=0.5, v_rc_v=0.0, t_batt_c=25.0)
    assert terminal_voltage_v(P, st, i_a=0.0) == pytest.approx(350.0)
    assert terminal_voltage_v(P, st, i_a=100.0) == pytest.approx(345.0)


def test_terminal_voltage_rises_under_charge():
    st = BatteryState(soc_frac=0.5, v_rc_v=0.0, t_batt_c=25.0)
    assert terminal_voltage_v(P, st, i_a=-100.0) == pytest.approx(355.0)


def test_terminal_voltage_includes_the_rc_branch():
    st = BatteryState(soc_frac=0.5, v_rc_v=2.0, t_batt_c=25.0)
    assert terminal_voltage_v(P, st, i_a=100.0) == pytest.approx(343.0)


def test_coulomb_counting_over_one_step():
    st = BatteryState(soc_frac=0.5, v_rc_v=0.0, t_batt_c=25.0)
    out = battery_step(P, st, i_a=100.0, dt_s=0.1)
    # 100 A for 0.1 s out of 60 Ah is 10 / 216000 of full charge.
    assert out.soc_frac == pytest.approx(0.5 - 4.6296296296e-5, rel=1e-9)


def test_one_c_discharge_drops_soc_at_the_expected_rate():
    # 60 A from a 60 Ah pack is 1C: 30 minutes removes half the charge.
    # Start at 0.9 so the result stays clear of soc_max and soc_min and the
    # test measures the discharge rate rather than the clamp.
    st = BatteryState(soc_frac=0.9, v_rc_v=0.0, t_batt_c=25.0)
    for _ in range(1800):
        st = battery_step(P, st, i_a=60.0, dt_s=1.0)
    assert st.soc_frac == pytest.approx(0.4, rel=1e-9)


def test_rc_branch_charges_toward_its_steady_state():
    st = BatteryState(soc_frac=0.5, v_rc_v=0.0, t_batt_c=25.0)
    out = battery_step(P, st, i_a=100.0, dt_s=0.1)
    # dv_rc = dt * (i/c1 - v_rc/(r1*c1)) = 0.1 * (100/2000 - 0) = 0.005
    assert out.v_rc_v == pytest.approx(0.005, rel=1e-9)

    for _ in range(100000):
        out = battery_step(P, out, i_a=100.0, dt_s=0.1)
    assert out.v_rc_v == pytest.approx(100.0 * P.r1_ohm, rel=1e-3)


def test_soc_is_clamped_to_its_bounds():
    st = BatteryState(soc_frac=P.soc_min, v_rc_v=0.0, t_batt_c=25.0)
    assert battery_step(P, st, i_a=400.0, dt_s=10.0).soc_frac == pytest.approx(P.soc_min)

    st = BatteryState(soc_frac=P.soc_max, v_rc_v=0.0, t_batt_c=25.0)
    assert battery_step(P, st, i_a=-400.0, dt_s=10.0).soc_frac == pytest.approx(P.soc_max)


def test_current_is_clamped_to_the_rated_limits():
    st = BatteryState(soc_frac=0.5, v_rc_v=0.0, t_batt_c=25.0)
    assert clamp_current(P, st, 1000.0) == pytest.approx(400.0)
    assert clamp_current(P, st, -1000.0) == pytest.approx(-150.0)
    assert clamp_current(P, st, 50.0) == pytest.approx(50.0)


def test_charging_is_blocked_at_full_and_discharge_at_empty():
    full = BatteryState(soc_frac=P.soc_max, v_rc_v=0.0, t_batt_c=25.0)
    assert clamp_current(P, full, -100.0) == pytest.approx(0.0)

    empty = BatteryState(soc_frac=P.soc_min, v_rc_v=0.0, t_batt_c=25.0)
    assert clamp_current(P, empty, 100.0) == pytest.approx(0.0)


def test_emf_is_ocv_less_the_rc_drop():
    st = BatteryState(soc_frac=0.5, v_rc_v=2.0, t_batt_c=25.0)
    assert emf_v(P, st) == pytest.approx(348.0)


def test_current_for_power_is_zero_at_zero_power():
    st = BatteryState(soc_frac=0.5, v_rc_v=0.0, t_batt_c=25.0)
    assert current_for_power(P, st, 0.0) == pytest.approx(0.0, abs=1e-12)


def test_current_for_power_round_trips_through_terminal_voltage():
    st = BatteryState(soc_frac=0.5, v_rc_v=0.0, t_batt_c=25.0)
    for target in (5000.0, 20000.0, 50000.0):
        i = current_for_power(P, st, target)
        assert terminal_voltage_v(P, st, i) * i == pytest.approx(target, rel=1e-9)


def test_current_for_power_handles_charging():
    st = BatteryState(soc_frac=0.5, v_rc_v=0.0, t_batt_c=25.0)
    i = current_for_power(P, st, -20000.0)
    assert i < 0.0
    assert terminal_voltage_v(P, st, i) * i == pytest.approx(-20000.0, rel=1e-9)


def test_current_for_power_clamps_at_the_matched_load_point():
    st = BatteryState(soc_frac=0.5, v_rc_v=0.0, t_batt_c=25.0)
    # Peak power is E^2 / (4 r0) = 350^2 / 0.2 = 612500 W.
    assert max_power_w(P, st) == pytest.approx(612500.0, rel=1e-9)

    i = current_for_power(P, st, 1e9)          # far beyond what is deliverable
    assert i == pytest.approx(350.0 / (2 * 0.05), rel=1e-9)


def test_lower_root_is_chosen_not_the_upper():
    st = BatteryState(soc_frac=0.5, v_rc_v=0.0, t_batt_c=25.0)
    i = current_for_power(P, st, 100000.0)
    assert i < 350.0 / (2 * 0.05), "must stay on the physical side of peak power"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/plant/test_battery.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'evpil.plant.battery'`

- [ ] **Step 3: Write the implementation**

```python
# src/evpil/plant/battery.py
"""First-order Thevenin battery model with a temperature-dependent series
resistance.

Current sign convention: positive is discharge, matching the BMW i3 archive.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

# Floor on r0 so extreme temperatures cannot drive it to zero or negative,
# which would make the terminal-voltage equation nonsensical.
_R0_FLOOR_FRACTION = 0.1


@dataclass(frozen=True)
class BatteryParams:
    capacity_ah: float
    ocv_soc_points: tuple[float, ...]
    ocv_volts: tuple[float, ...]
    r0_ohm: float
    r1_ohm: float
    c1_farad: float
    i_discharge_max_a: float
    i_charge_max_a: float
    soc_min: float
    soc_max: float
    r0_temp_coeff_per_c: float = 0.0
    t_ref_c: float = 25.0


@dataclass(frozen=True)
class BatteryState:
    soc_frac: float
    v_rc_v: float
    t_batt_c: float


def ocv_v(params: BatteryParams, soc_frac: float) -> float:
    """Open-circuit voltage, linearly interpolated and clamped at the table ends."""
    return float(np.interp(soc_frac, params.ocv_soc_points, params.ocv_volts))


def r0_at(params: BatteryParams, t_batt_c: float) -> float:
    """Series resistance at a given cell temperature.

    A negative temperature coefficient means resistance rises as the cell
    cools, which is the physically correct direction for lithium-ion.
    """
    scale = 1.0 + params.r0_temp_coeff_per_c * (t_batt_c - params.t_ref_c)
    floor = params.r0_ohm * _R0_FLOOR_FRACTION
    return max(params.r0_ohm * scale, floor)


def terminal_voltage_v(params: BatteryParams, state: BatteryState, i_a: float) -> float:
    """Terminal voltage for a given current, using the current RC-branch state."""
    return ocv_v(params, state.soc_frac) - i_a * r0_at(params, state.t_batt_c) - state.v_rc_v


def emf_v(params: BatteryParams, state: BatteryState) -> float:
    """Terminal voltage at zero current: OCV less the RC-branch drop."""
    return ocv_v(params, state.soc_frac) - state.v_rc_v


def max_power_w(params: BatteryParams, state: BatteryState) -> float:
    """Peak deliverable power, at the matched-load point i = E / (2 * r0)."""
    e = emf_v(params, state)
    return e * e / (4.0 * r0_at(params, state.t_batt_c))


def current_for_power(
    params: BatteryParams, state: BatteryState, p_target_w: float
) -> float:
    """Exact current that delivers `p_target_w` at the terminals.

    Solves (E - i*r0) * i = P for i, i.e. r0*i^2 - E*i + P = 0, and takes the
    lower root, which is the physically realised branch (the upper root is past
    the matched-load point, where more current yields less power).

    Solving this in closed form rather than dividing by a previous step's
    voltage is what makes a commanded power limit actually binding. Using a
    stale voltage lets the realised power overshoot the limit by several
    percent, which would silently corrupt any energy-management result.
    """
    e = emf_v(params, state)
    r0 = r0_at(params, state.t_batt_c)

    disc = e * e - 4.0 * r0 * p_target_w
    if disc <= 0.0:
        return e / (2.0 * r0)          # demand exceeds peak power; clamp to it
    return (e - math.sqrt(disc)) / (2.0 * r0)


def clamp_current(params: BatteryParams, state: BatteryState, i_a: float) -> float:
    """Clamp to the rated limits and block current that would breach an SoC bound."""
    i = float(np.clip(i_a, -params.i_charge_max_a, params.i_discharge_max_a))
    if i > 0.0 and state.soc_frac <= params.soc_min:
        return 0.0
    if i < 0.0 and state.soc_frac >= params.soc_max:
        return 0.0
    return i


def battery_step(
    params: BatteryParams, state: BatteryState, i_a: float, dt_s: float
) -> BatteryState:
    """Advance SoC by Coulomb counting and the RC branch by one forward-Euler step.

    Terminal voltage is evaluated by the caller *before* this call, so the RC
    voltage used for the output is the one at the start of the interval.
    """
    d_soc = i_a * dt_s / (3600.0 * params.capacity_ah)
    soc = float(np.clip(state.soc_frac - d_soc, params.soc_min, params.soc_max))

    tau = params.r1_ohm * params.c1_farad
    dv_rc = dt_s * (i_a / params.c1_farad - state.v_rc_v / tau)

    return BatteryState(soc_frac=soc, v_rc_v=state.v_rc_v + dv_rc, t_batt_c=state.t_batt_c)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/plant/test_battery.py -v`
Expected: 21 passed

- [ ] **Step 5: Commit**

```bash
git add src/evpil/plant/battery.py tests/plant/test_battery.py
git commit -m "feat: Thevenin battery model with temperature-dependent resistance"
```

---

### Task 12: Motor efficiency map and regeneration limits

**Files:**
- Create: `src/evpil/plant/motor.py`
- Create: `src/evpil/plant/regen.py`
- Test: `tests/plant/test_motor.py`
- Test: `tests/plant/test_regen.py`

**Interfaces:**
- Consumes: `BatteryParams`, `BatteryState`, `terminal_voltage_v` from Task 11.
- Produces:
  - `MotorParams` dataclass: `torque_axis_nm`, `speed_axis_radps`, `efficiency_grid`, `torque_max_nm`, `speed_max_radps`, `power_max_w`
  - `efficiency(params, torque_nm, omega_radps) -> float`
  - `electrical_power_w(params, torque_nm, omega_radps) -> float`
  - `clamp_torque(params, torque_nm, omega_radps) -> float`
  - `RegenParams` dataclass: `power_limit_w`, `blend_min`, `blend_max`
  - `split_braking(p_mech_w, blend, *, regen_params, batt_params, batt_state, v_term_v) -> tuple[float, float]` returning `(p_regen_w, p_friction_w)`
  - Tasks 14, 15 and 16 consume these.

The efficiency map is 2-D, not a scalar. A constant efficiency is a poor approximation across an EV's operating envelope and is another of the predecessor work's omissions.

- [ ] **Step 1: Write the failing tests**

```python
# tests/plant/test_motor.py
import numpy as np
import pytest
from evpil.plant.motor import MotorParams, clamp_torque, efficiency, electrical_power_w

M = MotorParams(
    torque_axis_nm=(0.0, 100.0, 200.0),
    speed_axis_radps=(0.0, 500.0, 1000.0),
    efficiency_grid=np.array([
        [0.70, 0.80, 0.75],   # torque 0
        [0.80, 0.94, 0.90],   # torque 100
        [0.75, 0.90, 0.85],   # torque 200
    ]),
    torque_max_nm=250.0,
    speed_max_radps=1200.0,
    power_max_w=125000.0,
)


def test_efficiency_at_grid_points():
    assert efficiency(M, 100.0, 500.0) == pytest.approx(0.94)
    assert efficiency(M, 0.0, 0.0) == pytest.approx(0.70)
    assert efficiency(M, 200.0, 1000.0) == pytest.approx(0.85)


def test_efficiency_interpolates_bilinearly():
    # Midpoint of the (0,100)x(0,500) cell: mean of 0.70, 0.80, 0.80, 0.94
    assert efficiency(M, 50.0, 250.0) == pytest.approx(0.81)


def test_efficiency_uses_torque_magnitude_so_regen_shares_the_map():
    assert efficiency(M, -100.0, 500.0) == pytest.approx(efficiency(M, 100.0, 500.0))


def test_efficiency_clamps_beyond_the_grid():
    assert efficiency(M, 400.0, 2000.0) == pytest.approx(0.85)


def test_driving_draws_more_electrical_than_mechanical_power():
    # 100 Nm at 500 rad/s is 50 kW mechanical, at 0.94 efficiency.
    p = electrical_power_w(M, 100.0, 500.0)
    assert p == pytest.approx(50000.0 / 0.94, rel=1e-9)
    assert p > 50000.0


def test_regeneration_returns_less_electrical_than_mechanical_power():
    p = electrical_power_w(M, -100.0, 500.0)
    assert p == pytest.approx(-50000.0 * 0.94, rel=1e-9)
    assert -50000.0 < p < 0.0


def test_zero_speed_gives_zero_power():
    assert electrical_power_w(M, 150.0, 0.0) == pytest.approx(0.0)


def test_torque_clamped_to_the_rated_maximum():
    assert clamp_torque(M, 400.0, 100.0) == pytest.approx(250.0)
    assert clamp_torque(M, -400.0, 100.0) == pytest.approx(-250.0)


def test_torque_clamped_by_the_power_limit_at_high_speed():
    # At 1000 rad/s, 125 kW allows only 125 Nm.
    assert clamp_torque(M, 250.0, 1000.0) == pytest.approx(125.0, rel=1e-9)


def test_no_torque_above_the_speed_limit():
    assert clamp_torque(M, 200.0, 1500.0) == pytest.approx(0.0)
```

```python
# tests/plant/test_regen.py
import pytest
from evpil.plant.battery import BatteryParams, BatteryState
from evpil.plant.regen import RegenParams, split_braking

BP = BatteryParams(
    capacity_ah=60.0, ocv_soc_points=(0.0, 0.5, 1.0), ocv_volts=(300.0, 350.0, 400.0),
    r0_ohm=0.05, r1_ohm=0.01, c1_farad=2000.0,
    i_discharge_max_a=400.0, i_charge_max_a=150.0, soc_min=0.05, soc_max=0.98,
)
RP = RegenParams(power_limit_w=50000.0, blend_min=0.0, blend_max=1.0)
ST = BatteryState(soc_frac=0.5, v_rc_v=0.0, t_batt_c=25.0)


def test_driving_produces_no_braking_split():
    regen, friction = split_braking(30000.0, 0.8, regen_params=RP, batt_params=BP,
                                    batt_state=ST, v_term_v=350.0)
    assert regen == pytest.approx(0.0)
    assert friction == pytest.approx(0.0)


def test_blend_sets_the_regenerated_fraction():
    regen, friction = split_braking(-20000.0, 0.75, regen_params=RP, batt_params=BP,
                                    batt_state=ST, v_term_v=350.0)
    assert regen == pytest.approx(-15000.0)
    assert friction == pytest.approx(-5000.0)


def test_regen_and_friction_always_sum_to_the_demand():
    regen, friction = split_braking(-40000.0, 0.6, regen_params=RP, batt_params=BP,
                                    batt_state=ST, v_term_v=350.0)
    assert regen + friction == pytest.approx(-40000.0)


def test_regen_capped_by_the_declared_power_limit():
    regen, friction = split_braking(-90000.0, 1.0, regen_params=RP, batt_params=BP,
                                    batt_state=ST, v_term_v=350.0)
    assert regen == pytest.approx(-50000.0)
    assert friction == pytest.approx(-40000.0)


def test_regen_capped_by_the_battery_charge_current_limit():
    # 150 A charge limit at 350 V terminal is 52.5 kW, above the 50 kW power
    # limit, so lower the terminal voltage to make current the binding constraint.
    regen, friction = split_braking(-90000.0, 1.0, regen_params=RP, batt_params=BP,
                                    batt_state=ST, v_term_v=200.0)
    assert regen == pytest.approx(-30000.0)     # 150 A * 200 V
    assert friction == pytest.approx(-60000.0)


def test_no_regen_when_the_battery_is_full():
    full = BatteryState(soc_frac=BP.soc_max, v_rc_v=0.0, t_batt_c=25.0)
    regen, friction = split_braking(-30000.0, 1.0, regen_params=RP, batt_params=BP,
                                    batt_state=full, v_term_v=350.0)
    assert regen == pytest.approx(0.0)
    assert friction == pytest.approx(-30000.0)


def test_blend_is_clamped_to_its_declared_range():
    a, _ = split_braking(-20000.0, 5.0, regen_params=RP, batt_params=BP,
                         batt_state=ST, v_term_v=350.0)
    b, _ = split_braking(-20000.0, 1.0, regen_params=RP, batt_params=BP,
                         batt_state=ST, v_term_v=350.0)
    assert a == pytest.approx(b)

    c, d = split_braking(-20000.0, -3.0, regen_params=RP, batt_params=BP,
                         batt_state=ST, v_term_v=350.0)
    assert c == pytest.approx(0.0)
    assert d == pytest.approx(-20000.0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/plant/test_motor.py tests/plant/test_regen.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'evpil.plant.motor'`

- [ ] **Step 3: Write the implementations**

```python
# src/evpil/plant/motor.py
"""Motor and drivetrain: a 2-D efficiency map plus torque and power limits.

Efficiency is looked up on |torque| so that motoring and generating share one
map, which is the usual simplification when only a single map is published.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class MotorParams:
    torque_axis_nm: tuple[float, ...]
    speed_axis_radps: tuple[float, ...]
    efficiency_grid: np.ndarray      # shape (len(torque_axis), len(speed_axis))
    torque_max_nm: float
    speed_max_radps: float
    power_max_w: float


def efficiency(params: MotorParams, torque_nm: float, omega_radps: float) -> float:
    """Bilinear interpolation on the efficiency map, clamped at the grid edges."""
    t_axis = np.asarray(params.torque_axis_nm, dtype=float)
    w_axis = np.asarray(params.speed_axis_radps, dtype=float)

    t = float(np.clip(abs(torque_nm), t_axis[0], t_axis[-1]))
    w = float(np.clip(abs(omega_radps), w_axis[0], w_axis[-1]))

    i = int(np.clip(np.searchsorted(t_axis, t) - 1, 0, len(t_axis) - 2))
    j = int(np.clip(np.searchsorted(w_axis, w) - 1, 0, len(w_axis) - 2))

    t0, t1 = t_axis[i], t_axis[i + 1]
    w0, w1 = w_axis[j], w_axis[j + 1]
    ft = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
    fw = 0.0 if w1 == w0 else (w - w0) / (w1 - w0)

    g = params.efficiency_grid
    return float(
        g[i, j] * (1 - ft) * (1 - fw) + g[i + 1, j] * ft * (1 - fw)
        + g[i, j + 1] * (1 - ft) * fw + g[i + 1, j + 1] * ft * fw
    )


def electrical_power_w(params: MotorParams, torque_nm: float, omega_radps: float) -> float:
    """Electrical power at the inverter terminals. Negative means generating.

    Driving divides by efficiency (losses add to the draw); generating
    multiplies by it (losses subtract from the return).
    """
    p_mech = torque_nm * omega_radps
    if p_mech == 0.0:
        return 0.0

    eta = efficiency(params, torque_nm, omega_radps)
    return p_mech / eta if p_mech > 0.0 else p_mech * eta


def clamp_torque(params: MotorParams, torque_nm: float, omega_radps: float) -> float:
    """Clamp to the rated torque, the constant-power envelope, and the speed limit."""
    if abs(omega_radps) > params.speed_max_radps:
        return 0.0

    limit = params.torque_max_nm
    if abs(omega_radps) > 0.0:
        limit = min(limit, params.power_max_w / abs(omega_radps))

    return float(np.clip(torque_nm, -limit, limit))
```

```python
# src/evpil/plant/regen.py
"""Regenerative braking: split braking demand between the machine and friction.

Whatever the machine cannot absorb goes to the friction brakes, so the braking
demand is always met in full. Only the recovered fraction changes.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from evpil.plant.battery import BatteryParams, BatteryState


@dataclass(frozen=True)
class RegenParams:
    power_limit_w: float
    blend_min: float = 0.0
    blend_max: float = 1.0


def split_braking(
    p_brake_w: float,
    blend: float,
    *,
    regen_params: RegenParams,
    batt_params: BatteryParams,
    batt_state: BatteryState,
    v_term_v: float,
) -> tuple[float, float]:
    """Return (p_regen_w, p_friction_w), both negative or zero, summing to demand.

    `p_brake_w` is the *electrical* braking power the machine can return,
    negative when braking. `blend` is the commanded regenerative fraction,
    clamped to its declared range; the realised fraction may be lower when a
    limit binds.
    """
    if p_brake_w >= 0.0:
        return 0.0, 0.0

    b = float(np.clip(blend, regen_params.blend_min, regen_params.blend_max))

    if batt_state.soc_frac >= batt_params.soc_max:
        return 0.0, p_brake_w

    ceiling = min(
        regen_params.power_limit_w,
        batt_params.i_charge_max_a * max(v_term_v, 0.0),
    )

    p_regen = max(b * p_brake_w, -ceiling)
    return p_regen, p_brake_w - p_regen
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/plant/test_motor.py tests/plant/test_regen.py -v`
Expected: 17 passed

- [ ] **Step 5: Commit**

```bash
git add src/evpil/plant/motor.py src/evpil/plant/regen.py tests/plant/test_motor.py tests/plant/test_regen.py
git commit -m "feat: 2-D motor efficiency map and regeneration limits"
```

---

### Task 13: Auxiliary and HVAC power model

**Files:**
- Create: `src/evpil/plant/auxiliary.py`
- Test: `tests/plant/test_auxiliary.py`

**Interfaces:**
- Consumes: the canonical frame from Task 8 (specifically `t_ambient_c` and `p_aux_w`).
- Produces:
  - `AuxParams` dataclass: `p_base_w`, `k_heat_w_per_c`, `k_cool_w_per_c`, `t_setpoint_c`
  - `aux_power_w(params, t_ambient_c) -> float`
  - `fit_auxiliary(t_ambient_c: np.ndarray, p_aux_w: np.ndarray, t_setpoint_c=21.0) -> AuxParams`
  - Tasks 14, 15 and 16 consume both.

This module exists because of the i3 archive's heating-circuit channel. Auxiliary load is a first-order contributor to real EV consumption, and it is the term the predecessor work declared as `HVAC_load = 5` and then never used anywhere in its calculation (defect D6).

The model is piecewise-linear in ambient temperature about a cabin setpoint: heating below it, cooling above it, with different coefficients because heat pumps and resistive heaters are not symmetric.

- [ ] **Step 1: Write the failing test**

```python
# tests/plant/test_auxiliary.py
import numpy as np
import pytest
from evpil.plant.auxiliary import AuxParams, aux_power_w, fit_auxiliary

A = AuxParams(p_base_w=300.0, k_heat_w_per_c=180.0, k_cool_w_per_c=90.0,
              t_setpoint_c=21.0)


def test_only_base_load_at_the_setpoint():
    assert aux_power_w(A, 21.0) == pytest.approx(300.0)


def test_heating_load_below_the_setpoint():
    # 21 degC below setpoint at 180 W/degC, plus 300 W base.
    assert aux_power_w(A, 0.0) == pytest.approx(300.0 + 21.0 * 180.0)


def test_cooling_load_above_the_setpoint():
    # 14 degC above setpoint at 90 W/degC, plus 300 W base.
    assert aux_power_w(A, 35.0) == pytest.approx(300.0 + 14.0 * 90.0)


def test_heating_and_cooling_coefficients_are_independent():
    below = aux_power_w(A, 21.0 - 10.0) - A.p_base_w
    above = aux_power_w(A, 21.0 + 10.0) - A.p_base_w
    assert below == pytest.approx(1800.0)
    assert above == pytest.approx(900.0)
    assert below != above


def test_fit_recovers_known_coefficients():
    t = np.linspace(-10.0, 40.0, 500)
    p = np.array([aux_power_w(A, x) for x in t])

    got = fit_auxiliary(t, p, t_setpoint_c=21.0)
    assert got.p_base_w == pytest.approx(300.0, abs=1.0)
    assert got.k_heat_w_per_c == pytest.approx(180.0, abs=1.0)
    assert got.k_cool_w_per_c == pytest.approx(90.0, abs=1.0)


def test_fit_is_robust_to_moderate_noise():
    rng = np.random.default_rng(0)
    t = np.linspace(-10.0, 40.0, 2000)
    p = np.array([aux_power_w(A, x) for x in t]) + rng.normal(0, 50.0, 2000)

    got = fit_auxiliary(t, p, t_setpoint_c=21.0)
    assert got.k_heat_w_per_c == pytest.approx(180.0, rel=0.05)
    assert got.k_cool_w_per_c == pytest.approx(90.0, rel=0.05)


def test_fitted_power_is_never_negative():
    t = np.linspace(-10.0, 40.0, 100)
    p = np.zeros_like(t)
    got = fit_auxiliary(t, p, t_setpoint_c=21.0)
    assert aux_power_w(got, -20.0) >= 0.0
    assert aux_power_w(got, 50.0) >= 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/plant/test_auxiliary.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'evpil.plant.auxiliary'`

- [ ] **Step 3: Write the implementation**

```python
# src/evpil/plant/auxiliary.py
"""Auxiliary and HVAC electrical load as a function of ambient temperature.

Piecewise-linear about a cabin setpoint, with separate heating and cooling
coefficients because the two use different mechanisms and are not symmetric.
Coefficients are fitted from the i3 archive's heating-circuit channel rather
than assumed.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class AuxParams:
    p_base_w: float
    k_heat_w_per_c: float
    k_cool_w_per_c: float
    t_setpoint_c: float = 21.0


def aux_power_w(params: AuxParams, t_ambient_c: float) -> float:
    """Auxiliary electrical power in watts. Never negative."""
    heat_deficit = max(0.0, params.t_setpoint_c - t_ambient_c)
    cool_excess = max(0.0, t_ambient_c - params.t_setpoint_c)

    p = (params.p_base_w
         + params.k_heat_w_per_c * heat_deficit
         + params.k_cool_w_per_c * cool_excess)
    return max(0.0, p)


def fit_auxiliary(
    t_ambient_c: np.ndarray,
    p_aux_w: np.ndarray,
    t_setpoint_c: float = 21.0,
) -> AuxParams:
    """Least-squares fit of the three coefficients from logged data.

    The design matrix has one column per coefficient, so this is an ordinary
    linear least-squares problem despite the piecewise form.
    """
    t = np.asarray(t_ambient_c, dtype=float).ravel()
    p = np.asarray(p_aux_w, dtype=float).ravel()
    if t.shape != p.shape:
        raise ValueError(f"shape mismatch: {t.shape} vs {p.shape}")

    heat = np.maximum(0.0, t_setpoint_c - t)
    cool = np.maximum(0.0, t - t_setpoint_c)
    design = np.column_stack([np.ones_like(t), heat, cool])

    coeffs, *_ = np.linalg.lstsq(design, p, rcond=None)
    base, k_heat, k_cool = (float(c) for c in coeffs)

    # Negative coefficients are unphysical: more heating demand cannot reduce
    # electrical load. Clamp rather than propagate a nonsense fit.
    return AuxParams(
        p_base_w=max(0.0, base),
        k_heat_w_per_c=max(0.0, k_heat),
        k_cool_w_per_c=max(0.0, k_cool),
        t_setpoint_c=t_setpoint_c,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/plant/test_auxiliary.py -v`
Expected: 7 passed

- [ ] **Step 5: Fit against the real training trips**

```bash
python -c "
import json
from pathlib import Path
import numpy as np
from evpil.data.i3_loader import load_all_trips
from evpil.data.splits import Split, apply_split
from evpil.plant.auxiliary import fit_auxiliary
MAPPING = {}  # the real mapping from Task 8
sp = json.loads(Path('data/splits.json').read_text())
df = load_all_trips(Path('data/raw/i3'), MAPPING)
tr, _, _ = apply_split(df, Split(sp['train'], sp['val'], sp['test']))
a = fit_auxiliary(tr.t_ambient_c.to_numpy(), tr.p_aux_w.to_numpy())
print(a)
"
```

Fit on **training trips only**. Record the coefficients in `docs/dataset-provenance.md` with the residual RMSE, and note the ambient-temperature range they were fitted over — extrapolating a fit beyond its data is how plausible-looking plants produce wrong answers at the edges.

- [ ] **Step 6: Commit**

```bash
git add src/evpil/plant/auxiliary.py tests/plant/test_auxiliary.py
git commit -m "feat: auxiliary and HVAC power model fitted from logged data"
```

---

### Task 14: Vehicle parameters and plant assembly

**Files:**
- Create: `src/evpil/plant/params.py`
- Create: `src/evpil/plant/plant.py`
- Test: `tests/plant/test_plant.py`

**Interfaces:**
- Consumes: everything from Tasks 10 through 13.
- Produces:
  - `VehicleParams` dataclass aggregating `mass_kg`, `c_rr`, `cd`, `frontal_area_m2`, `wheel_radius_m`, `gear_ratio`, `drivetrain_eta`, plus nested `battery`, `motor`, `regen`, `aux`, and a `citations: dict[str, str]`
  - `PlantState` dataclass: `v_mps`, `battery`, `distance_m`, `energy_wh`
  - `PlantOutput` dataclass: `state`, `a_mps2`, `i_batt_a`, `v_batt_v`, `p_batt_w`, `p_mech_w`, `p_regen_w`, `p_friction_w`, `p_aux_w`
  - `class Plant` with `reset(soc0, t_ambient_c, t_batt_c) -> PlantState` and `step(state, *, torque_nm, regen_blend, p_limit_w, grade_rad, t_ambient_c, dt_s) -> PlantOutput`
  - Tasks 15 and 16 drive this; Phase 3 uses it as the PIL simulator.

Every field of `VehicleParams` has an entry in `citations`. A parameter without a source is a parameter a reviewer can reject, so the dataclass refuses to construct without one.

- [ ] **Step 1: Write the failing test**

```python
# tests/plant/test_plant.py
import math
import numpy as np
import pytest
from evpil.plant.auxiliary import AuxParams
from evpil.plant.battery import BatteryParams
from evpil.plant.motor import MotorParams
from evpil.plant.params import VehicleParams
from evpil.plant.plant import Plant
from evpil.plant.regen import RegenParams

BATT = BatteryParams(
    capacity_ah=60.0, ocv_soc_points=(0.0, 0.5, 1.0), ocv_volts=(300.0, 350.0, 400.0),
    r0_ohm=0.05, r1_ohm=0.01, c1_farad=2000.0,
    i_discharge_max_a=400.0, i_charge_max_a=150.0, soc_min=0.05, soc_max=0.98,
)
MOTOR = MotorParams(
    torque_axis_nm=(0.0, 100.0, 200.0), speed_axis_radps=(0.0, 500.0, 1000.0),
    efficiency_grid=np.full((3, 3), 0.90),
    torque_max_nm=250.0, speed_max_radps=1200.0, power_max_w=125000.0,
)
AUX = AuxParams(p_base_w=300.0, k_heat_w_per_c=180.0, k_cool_w_per_c=90.0)

VP = VehicleParams(
    mass_kg=1400.0, c_rr=0.01, cd=0.29, frontal_area_m2=2.38,
    wheel_radius_m=0.32, gear_ratio=9.7, drivetrain_eta=0.95,
    battery=BATT, motor=MOTOR, regen=RegenParams(power_limit_w=50000.0), aux=AUX,
    citations={
        "mass_kg": "test fixture", "c_rr": "test fixture", "cd": "test fixture",
        "frontal_area_m2": "test fixture", "wheel_radius_m": "test fixture",
        "gear_ratio": "test fixture", "drivetrain_eta": "test fixture",
        "battery": "test fixture", "motor": "test fixture",
        "regen": "test fixture", "aux": "test fixture",
    },
)


def test_params_reject_a_missing_citation():
    with pytest.raises(ValueError, match="citation"):
        VehicleParams(
            mass_kg=1400.0, c_rr=0.01, cd=0.29, frontal_area_m2=2.38,
            wheel_radius_m=0.32, gear_ratio=9.7, drivetrain_eta=0.95,
            battery=BATT, motor=MOTOR, regen=RegenParams(power_limit_w=50000.0),
            aux=AUX, citations={"mass_kg": "only this one"},
        )


def test_reset_produces_the_requested_initial_condition():
    st = Plant(VP).reset(soc0=0.8, t_ambient_c=21.0, t_batt_c=25.0)
    assert st.v_mps == pytest.approx(0.0)
    assert st.battery.soc_frac == pytest.approx(0.8)
    assert st.distance_m == pytest.approx(0.0)


def test_zero_torque_from_rest_leaves_the_vehicle_at_rest():
    plant = Plant(VP)
    st = plant.reset(soc0=0.8, t_ambient_c=21.0, t_batt_c=25.0)
    out = plant.step(st, torque_nm=0.0, regen_blend=0.0, p_limit_w=1e6,
                     grade_rad=0.0, t_ambient_c=21.0, dt_s=0.1)
    assert out.state.v_mps == pytest.approx(0.0, abs=1e-9)
    assert out.p_mech_w == pytest.approx(0.0, abs=1e-9)


def test_positive_torque_accelerates_the_vehicle():
    plant = Plant(VP)
    st = plant.reset(soc0=0.8, t_ambient_c=21.0, t_batt_c=25.0)
    out = plant.step(st, torque_nm=100.0, regen_blend=0.0, p_limit_w=1e6,
                     grade_rad=0.0, t_ambient_c=21.0, dt_s=0.1)
    assert out.a_mps2 > 0.0
    assert out.state.v_mps > 0.0


def test_wheel_force_matches_the_gear_and_efficiency_chain():
    plant = Plant(VP)
    st = plant.reset(soc0=0.8, t_ambient_c=21.0, t_batt_c=25.0)
    out = plant.step(st, torque_nm=100.0, regen_blend=0.0, p_limit_w=1e6,
                     grade_rad=0.0, t_ambient_c=21.0, dt_s=0.1)
    # F = T * G * eta / r = 100 * 9.7 * 0.95 / 0.32; from rest the only
    # resistance is rolling (aero is zero at v = 0).
    f_wheel = 100.0 * 9.7 * 0.95 / 0.32
    f_roll = 0.0     # direction is 0 at exactly v = 0
    assert out.a_mps2 == pytest.approx((f_wheel - f_roll) / 1400.0, rel=1e-9)


def test_driving_discharges_and_regeneration_charges():
    plant = Plant(VP)
    st = plant.reset(soc0=0.8, t_ambient_c=21.0, t_batt_c=25.0)
    for _ in range(50):
        out = plant.step(st, torque_nm=80.0, regen_blend=0.0, p_limit_w=1e6,
                         grade_rad=0.0, t_ambient_c=21.0, dt_s=0.1)
        st = out.state
    assert st.battery.soc_frac < 0.8
    soc_after_drive = st.battery.soc_frac

    out = plant.step(st, torque_nm=-80.0, regen_blend=1.0, p_limit_w=1e6,
                     grade_rad=0.0, t_ambient_c=21.0, dt_s=0.1)
    assert out.p_regen_w < 0.0
    assert out.i_batt_a < 0.0
    assert out.state.battery.soc_frac > soc_after_drive


def test_auxiliary_load_flows_into_battery_power():
    plant = Plant(VP)
    st = plant.reset(soc0=0.8, t_ambient_c=21.0, t_batt_c=25.0)

    warm = plant.step(st, torque_nm=0.0, regen_blend=0.0, p_limit_w=1e6,
                      grade_rad=0.0, t_ambient_c=21.0, dt_s=0.1)
    cold = plant.step(st, torque_nm=0.0, regen_blend=0.0, p_limit_w=1e6,
                      grade_rad=0.0, t_ambient_c=-5.0, dt_s=0.1)

    assert cold.p_aux_w > warm.p_aux_w
    assert cold.p_batt_w > warm.p_batt_w


def test_discharge_power_limit_is_enforced():
    plant = Plant(VP)
    st = plant.reset(soc0=0.8, t_ambient_c=21.0, t_batt_c=25.0)
    for _ in range(100):
        st = plant.step(st, torque_nm=200.0, regen_blend=0.0, p_limit_w=1e6,
                        grade_rad=0.0, t_ambient_c=21.0, dt_s=0.1).state

    out = plant.step(st, torque_nm=200.0, regen_blend=0.0, p_limit_w=20000.0,
                     grade_rad=0.0, t_ambient_c=21.0, dt_s=0.1)
    # The limit must be met exactly, not merely not exceeded. Solving the
    # battery coupling with a stale voltage used to overshoot this by ~4.6%,
    # which would silently invalidate every energy-management result in Phase 3.
    assert out.p_batt_w == pytest.approx(20000.0, rel=1e-9)
    assert out.v_batt_v * out.i_batt_a == pytest.approx(out.p_batt_w, rel=1e-9)


def test_climbing_needs_more_energy_than_the_flat():
    plant = Plant(VP)
    base = plant.reset(soc0=0.8, t_ambient_c=21.0, t_batt_c=25.0)

    flat, hill = base, base
    for _ in range(100):
        flat = plant.step(flat, torque_nm=120.0, regen_blend=0.0, p_limit_w=1e6,
                          grade_rad=0.0, t_ambient_c=21.0, dt_s=0.1).state
        hill = plant.step(hill, torque_nm=120.0, regen_blend=0.0, p_limit_w=1e6,
                          grade_rad=math.radians(6.0), t_ambient_c=21.0,
                          dt_s=0.1).state

    assert hill.v_mps < flat.v_mps
    assert hill.distance_m < flat.distance_m


def test_distance_and_energy_accumulate_monotonically():
    plant = Plant(VP)
    st = plant.reset(soc0=0.8, t_ambient_c=21.0, t_batt_c=25.0)
    prev_d, prev_e = -1.0, -1.0
    for _ in range(30):
        st = plant.step(st, torque_nm=100.0, regen_blend=0.0, p_limit_w=1e6,
                        grade_rad=0.0, t_ambient_c=21.0, dt_s=0.1).state
        assert st.distance_m > prev_d
        assert st.energy_wh > prev_e
        prev_d, prev_e = st.distance_m, st.energy_wh
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/plant/test_plant.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'evpil.plant.params'`

- [ ] **Step 3: Write the implementation**

```python
# src/evpil/plant/params.py
"""Vehicle parameters, every one of them cited.

A parameter without a source is a parameter a reviewer can reject, so
construction fails when a citation is missing rather than at review time.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields

from evpil.plant.auxiliary import AuxParams
from evpil.plant.battery import BatteryParams
from evpil.plant.motor import MotorParams
from evpil.plant.regen import RegenParams

_CITED_FIELDS = (
    "mass_kg", "c_rr", "cd", "frontal_area_m2", "wheel_radius_m",
    "gear_ratio", "drivetrain_eta", "battery", "motor", "regen", "aux",
)


@dataclass(frozen=True)
class VehicleParams:
    mass_kg: float
    c_rr: float
    cd: float
    frontal_area_m2: float
    wheel_radius_m: float
    gear_ratio: float
    drivetrain_eta: float
    battery: BatteryParams
    motor: MotorParams
    regen: RegenParams
    aux: AuxParams
    citations: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        missing = [name for name in _CITED_FIELDS if not self.citations.get(name)]
        if missing:
            raise ValueError(
                f"missing citation for: {missing}. Every vehicle parameter must "
                f"name its source (published specification, or identification "
                f"against logged data)."
            )
        for name in ("mass_kg", "wheel_radius_m", "gear_ratio"):
            if getattr(self, name) <= 0.0:
                raise ValueError(f"{name} must be positive, got {getattr(self, name)}")
        if not 0.0 < self.drivetrain_eta <= 1.0:
            raise ValueError(f"drivetrain_eta must be in (0, 1], got {self.drivetrain_eta}")
```

```python
# src/evpil/plant/plant.py
"""The EV plant: composes road load, motor, regeneration, auxiliary and battery.

The battery coupling I = P/V(I) is solved in closed form (see
battery.current_for_power) rather than by dividing by the previous step's
voltage. The lagged form let a commanded power limit be exceeded by several
percent, which matters because in Phase 3 that limit is an RL action.
"""

from __future__ import annotations

from dataclasses import dataclass

from evpil.plant.auxiliary import aux_power_w
from evpil.plant.battery import (
    BatteryState, battery_step, clamp_current, current_for_power, emf_v,
    terminal_voltage_v,
)
from evpil.plant.longitudinal import road_load
from evpil.plant.motor import clamp_torque, electrical_power_w
from evpil.plant.params import VehicleParams
from evpil.plant.regen import split_braking


@dataclass(frozen=True)
class PlantState:
    v_mps: float
    battery: BatteryState
    distance_m: float
    energy_wh: float


@dataclass(frozen=True)
class PlantOutput:
    state: PlantState
    a_mps2: float
    i_batt_a: float
    v_batt_v: float
    p_batt_w: float
    p_mech_w: float
    p_regen_w: float
    p_friction_w: float
    p_aux_w: float


class Plant:
    def __init__(self, params: VehicleParams) -> None:
        self.p = params

    def reset(self, soc0: float, t_ambient_c: float, t_batt_c: float) -> PlantState:
        batt = BatteryState(soc_frac=soc0, v_rc_v=0.0, t_batt_c=t_batt_c)
        return PlantState(
            v_mps=0.0,
            battery=batt,
            distance_m=0.0,
            energy_wh=0.0,
        )

    def step(
        self,
        state: PlantState,
        *,
        torque_nm: float,
        regen_blend: float,
        p_limit_w: float,
        grade_rad: float,
        t_ambient_c: float,
        dt_s: float,
    ) -> PlantOutput:
        p = self.p

        omega = (state.v_mps / p.wheel_radius_m) * p.gear_ratio
        torque = clamp_torque(p.motor, torque_nm, omega)

        # Drivetrain losses always reduce power in its direction of flow.
        if torque >= 0.0:
            f_wheel = torque * p.gear_ratio * p.drivetrain_eta / p.wheel_radius_m
        else:
            f_wheel = torque * p.gear_ratio / (p.drivetrain_eta * p.wheel_radius_m)

        load = road_load(
            v_mps=state.v_mps, a_mps2=0.0, grade_rad=grade_rad,
            mass_kg=p.mass_kg, c_rr=p.c_rr, cd=p.cd,
            frontal_area_m2=p.frontal_area_m2,
        )
        f_resist = load.rolling_n + load.aero_n + load.grade_n
        a_mps2 = (f_wheel - f_resist) / p.mass_kg

        p_mech_w = torque * omega
        p_elec_w = electrical_power_w(p.motor, torque, omega)

        if p_elec_w < 0.0:
            p_regen_w, p_friction_w = split_braking(
                p_elec_w, regen_blend,
                regen_params=p.regen, batt_params=p.battery,
                batt_state=state.battery, v_term_v=emf_v(p.battery, state.battery),
            )
            p_machine_w = p_regen_w
        else:
            p_regen_w, p_friction_w = 0.0, 0.0
            p_machine_w = p_elec_w

        p_aux = aux_power_w(p.aux, t_ambient_c)
        p_batt_w = min(p_machine_w + p_aux, p_limit_w)

        # Exact solve, so p_limit_w is genuinely binding. Clamping afterwards
        # only ever reduces |i| on the lower root, so it cannot push power back
        # above the limit.
        i_raw = current_for_power(p.battery, state.battery, p_batt_w)
        i_batt = clamp_current(p.battery, state.battery, i_raw)

        v_term = terminal_voltage_v(p.battery, state.battery, i_batt)
        p_batt_actual = v_term * i_batt

        batt_next = battery_step(p.battery, state.battery, i_batt, dt_s)

        v_next = state.v_mps + a_mps2 * dt_s
        dist_next = state.distance_m + abs(state.v_mps) * dt_s
        energy_next = state.energy_wh + max(0.0, p_batt_actual) * dt_s / 3600.0

        next_state = PlantState(
            v_mps=v_next,
            battery=batt_next,
            distance_m=dist_next,
            energy_wh=energy_next,
        )

        return PlantOutput(
            state=next_state, a_mps2=a_mps2, i_batt_a=i_batt, v_batt_v=v_term,
            p_batt_w=p_batt_actual, p_mech_w=p_mech_w, p_regen_w=p_regen_w,
            p_friction_w=p_friction_w, p_aux_w=p_aux,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/plant/ -v`
Expected: 63 passed

- [ ] **Step 5: Commit**

```bash
git add src/evpil/plant/params.py src/evpil/plant/plant.py tests/plant/test_plant.py
git commit -m "feat: vehicle parameters with mandatory citations, plant assembly"
```

---

### Task 15: Parameter identification against logged trips

**Files:**
- Create: `scripts/__init__.py` (empty; makes `scripts` importable, which Task 16 relies on)
- Create: `scripts/identify_params.py`
- Create: `data/i3_params.json`
- Modify: `docs/dataset-provenance.md`

**Interfaces:**
- Consumes: `Plant`, `VehicleParams` from Task 14; the loader and splits from Tasks 8 and 9.
- Produces: `data/i3_params.json`, a fully cited parameter set. Task 16 validates it, and Phase 3 uses it as the PIL plant configuration.

Three parameters are identified rather than cited: `c_rr`, `cd` (with frontal area held at its published value) and `r0_ohm`. These are the ones that vary with tyre, load and cell age, so a published figure would be less accurate than a fit. Their citation string records the identification procedure instead — that is a source, and a stronger one than a datasheet.

Everything else comes from published BMW i3 (60 Ah, 2014) specifications. **Look these up and record the actual source for each**; no figures are asserted here because none have been verified.

- [ ] **Step 1: Write the identification script**

```python
# scripts/identify_params.py
"""Identify c_rr, cd and r0 by matching simulated battery power to logged power.

Only these three are fitted. Everything else is a published specification, so
fitting it would trade a citable number for an uncitable one.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import least_squares

from evpil.data.i3_loader import load_all_trips
from evpil.data.splits import Split, apply_split
from evpil.plant.auxiliary import fit_auxiliary
from evpil.plant.battery import BatteryParams
from evpil.plant.motor import MotorParams
from evpil.plant.params import VehicleParams
from evpil.plant.plant import Plant
from evpil.plant.regen import RegenParams

# Paste the real mapping recorded in Task 8 Step 1.
MAPPING: dict[str, str] = {}

# ---------------------------------------------------------------------------
# BMW i3 (I01, 60 Ah, 2013-2017) parameters.
#
# NOTE: this is the ORIGINAL i3 (I01), not the 2026 i3 sedan (NA0), which is a
# different vehicle entirely. The dataset is 2014 I01.
#
# Three parameters are deliberately NOT fixed here: c_rr, cd and r0_ohm are
# identified by least squares below, because they vary with tyre, load and cell
# age more than any published figure can capture.
#
# Sources are listed in REFERENCES at the bottom of this module.
# ---------------------------------------------------------------------------
PUBLISHED = dict(
    mass_kg=1270.0,          # 1195 kg DIN kerb [R1] + 75 kg driver [R6]
    frontal_area_m2=2.38,    # CdA 0.690 / Cd 0.29 [R4] -- see CAVEATS
    wheel_radius_m=0.3498,   # 155/70 R19: (482.6 + 2*108.5)/2 mm [R5]
    gear_ratio=9.665,        # single-speed reduction [R2]
    drivetrain_eta=0.95,     # ASSUMPTION, not a published figure -- see CAVEATS
    capacity_ah=60.0,        # nameplate cell capacity, 96s [R3]
    power_max_w=125000.0,    # 125 kW / 170 hp [R1][R2]
    torque_max_nm=250.0,     # 250 Nm from standstill [R1][R2]
)

CITATIONS = {
    "mass_kg": "BMW Group PressClub, 'The BMW i3' technical data: 1195 kg DIN "
               "kerb weight [R1]; +75 kg driver per EU kerb convention [R6]",
    "c_rr": "identified by least squares against training trips, "
            "scripts/identify_params.py",
    "cd": "identified by least squares against training trips, "
          "scripts/identify_params.py; initial value 0.29 (BEV) [R1][R4]",
    "frontal_area_m2": "derived as CdA/Cd = 0.690/0.29 [R4]. ASSUMPTION-GRADE "
                       "source (enthusiast forum); low risk because the fitted "
                       "cd absorbs error in the CdA product",
    "wheel_radius_m": "geometric radius of the standard 155/70 R19 tyre [R5]",
    "gear_ratio": "single-speed reduction gear, 9.665:1 [R2]",
    "drivetrain_eta": "ENGINEERING ASSUMPTION: 0.95, typical single-speed "
                      "reduction gear. Not a published BMW figure",
    "battery": "96s, 360 V nominal, 60 Ah Samsung NCA prismatic cells, 21.6 kWh "
               "gross / 18.8 kWh usable [R3]. r0 identified; OCV curve, RC "
               "branch and current limits are ASSUMPTIONS (see CAVEATS)",
    "motor": "125 kW / 250 Nm hybrid-synchronous machine [R1][R2]. The "
             "efficiency MAP is a representative PMSM surface, not measured "
             "(see CAVEATS)",
    "regen": "ENGINEERING ASSUMPTION: 50 kW regenerative ceiling. BMW does not "
             "publish a figure for the I01",
    "aux": "fitted from the heating-circuit channel, "
           "evpil.plant.auxiliary.fit_auxiliary",
}

REFERENCES = """
[R1] BMW Group PressClub, "The BMW i3", global press kit, 2013.
     https://www.press.bmwgroup.com/global/article/detail/T0148284EN/the-bmw-i3
     -- 125 kW / 250 Nm; Cd 0.29 (BEV); DIN kerb weight 1195 kg.
[R2] Green Car Congress, "More details on BMW's i3; electric and connected",
     2013-07-10. https://www.greencarcongress.com/2013/07/bmwi3-20130710.html
     -- single-speed transmission, 9.665:1 reduction.
[R3] Battery Design, "2013 BMW i3 - Battery Design".
     https://www.batterydesign.net/bmw-i3-2/
     -- 96 cells in series, 360 V nominal, 60 Ah Samsung NCA prismatic,
        21.6 kWh gross / 18.8 kWh usable.
[R4] InsideEVs / EcoModder community aerodynamic data: CdA 0.690 m2 (BEV),
     0.710 m2 (REx). ASSUMPTION-GRADE SOURCE.
[R5] Wheel-Size.com, BMW i3 (2013-2022) tyre fitment: 155/70 R19 standard.
     https://www.wheel-size.com/tire/iso-metric-155-70-R-19/bmw/i3/2013-2022/
[R6] EU kerb-weight convention (Directive 92/21/EEC): DIN kerb + 75 kg driver.

CAVEATS -- read before trusting any downstream number:

 1. frontal_area_m2 rests on a forum-sourced CdA. Risk is low: the drag term is
    0.5*rho*cd*A*v^2, and cd is fitted, so the identification calibrates the
    CdA PRODUCT against real logs. An error in A is absorbed by cd.
 2. drivetrain_eta, the motor efficiency map, the RC branch (r1, c1), the
    current limits and the regen ceiling are ENGINEERING ASSUMPTIONS. BMW does
    not publish them. They are flagged as such in CITATIONS and must be
    described as assumptions in the paper, never as specifications.
 3. wheel_radius_m is the geometric, not dynamic, rolling radius (typically
    2-3% smaller under load). This largely cancels: simulate_trip inverts
    force to torque with the same radius the plant uses to convert back, so
    P_mech = F*v/eta is radius-independent. It survives only via the omega
    argument to the efficiency map, a second-order effect.
 4. capacity_ah is the 60 Ah NAMEPLATE. If the dataset's SoC channel is
    referenced to USABLE capacity (18.8/21.6 = 87%), the correct value is
    ~52.2 Ah with a [0, 1] window instead. Resolve this at G2: a systematic
    SoC drift of roughly 13% is the signature of getting it wrong.
 5. The OCV curve below is a representative 96s NCA characteristic, NOT an i3
    measurement. It is the single most likely cause of a systematic SoC error
    at G2 (see Task 16 troubleshooting step 4).
"""


def build_params(c_rr: float, cd: float, r0: float, aux) -> VehicleParams:
    battery = BatteryParams(
        capacity_ah=PUBLISHED["capacity_ah"],
        # Representative 96s NCA pack curve: 3.20 V/cell empty to 4.15 V/cell
        # full. ASSUMPTION -- see CAVEATS note 5.
        ocv_soc_points=(0.0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0),
        ocv_volts=(307.2, 336.0, 348.5, 357.1, 371.5, 388.8, 398.4),
        r0_ohm=r0, r1_ohm=0.01, c1_farad=2000.0,
        # 125 kW at 360 V nominal is ~347 A. Charge limit and regen ceiling are
        # assumptions (CAVEATS note 2).
        i_discharge_max_a=350.0, i_charge_max_a=150.0,
        # 18.8 kWh usable of 21.6 kWh gross is an 87% window.
        soc_min=0.07, soc_max=0.94,
        r0_temp_coeff_per_c=-0.004, t_ref_c=25.0,
    )
    motor = MotorParams(
        torque_axis_nm=(0.0, 62.5, 125.0, 250.0),
        speed_axis_radps=(0.0, 300.0, 700.0, 1151.0),
        # Representative PMSM efficiency surface -- ASSUMPTION, see CAVEATS.
        efficiency_grid=np.array([
            [0.70, 0.82, 0.85, 0.83],
            [0.78, 0.91, 0.93, 0.90],
            [0.80, 0.93, 0.94, 0.91],
            [0.76, 0.90, 0.91, 0.88],
        ]),
        torque_max_nm=PUBLISHED["torque_max_nm"],
        # 150 km/h limited [R1] = 41.67 m/s; omega_motor = v/r * G = 1151 rad/s.
        speed_max_radps=1151.0,
        power_max_w=PUBLISHED["power_max_w"],
    )
    return VehicleParams(
        mass_kg=PUBLISHED["mass_kg"], c_rr=c_rr, cd=cd,
        frontal_area_m2=PUBLISHED["frontal_area_m2"],
        wheel_radius_m=PUBLISHED["wheel_radius_m"],
        gear_ratio=PUBLISHED["gear_ratio"],
        drivetrain_eta=PUBLISHED["drivetrain_eta"],
        battery=battery, motor=motor,
        regen=RegenParams(power_limit_w=50000.0), aux=aux,
        citations=CITATIONS,
    )


def simulate_trip(params: VehicleParams, trip: pd.DataFrame) -> np.ndarray:
    """Replay a trip's logged speed profile and return simulated battery power.

    Torque is inverted from the logged acceleration rather than commanded, so
    this isolates the plant's power model from any controller behaviour.
    """
    plant = Plant(params)
    st = plant.reset(soc0=float(trip.soc_frac.iloc[0]),
                     t_ambient_c=float(trip.t_ambient_c.iloc[0]),
                     t_batt_c=float(trip.t_batt_c.iloc[0]))

    out_p = np.empty(len(trip))
    t = trip.t_s.to_numpy()

    for k in range(len(trip)):
        dt = float(t[k] - t[k - 1]) if k > 0 else float(t[1] - t[0])
        v = float(trip.v_mps.iloc[k])
        a = float(trip.a_mps2.iloc[k])
        grade = float(trip.grade_rad.iloc[k])

        # Force needed to follow the logged profile, converted to motor torque.
        from evpil.plant.longitudinal import road_load
        load = road_load(v_mps=v, a_mps2=a, grade_rad=grade,
                         mass_kg=params.mass_kg, c_rr=params.c_rr, cd=params.cd,
                         frontal_area_m2=params.frontal_area_m2)
        f = load.tractive_n
        if f >= 0.0:
            torque = f * params.wheel_radius_m / (params.gear_ratio * params.drivetrain_eta)
        else:
            torque = f * params.wheel_radius_m * params.drivetrain_eta / params.gear_ratio

        st = replace_speed(st, v)
        res = plant.step(st, torque_nm=torque, regen_blend=1.0, p_limit_w=1e9,
                         grade_rad=grade, t_ambient_c=float(trip.t_ambient_c.iloc[k]),
                         dt_s=dt)
        out_p[k] = res.p_batt_w
        st = res.state

    return out_p


def replace_speed(state, v_mps: float):
    """Pin the simulated speed to the logged value so errors cannot accumulate."""
    from dataclasses import replace
    return replace(state, v_mps=v_mps)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/raw/i3")
    ap.add_argument("--splits", default="data/splits.json")
    ap.add_argument("--out", default="data/i3_params.json")
    args = ap.parse_args()

    sp = json.loads(Path(args.splits).read_text())
    df = load_all_trips(Path(args.data), MAPPING)
    train, _, _ = apply_split(df, Split(sp["train"], sp["val"], sp["test"]))

    aux = fit_auxiliary(train.t_ambient_c.to_numpy(), train.p_aux_w.to_numpy())
    print(f"auxiliary fit: {aux}")

    # Fit on a subset of training trips: identification does not need all of
    # them, and the rest stay available as an independent check.
    trips = sorted(train.trip_id.unique())[:8]
    subsets = [train[train.trip_id == t].reset_index(drop=True) for t in trips]

    def residuals(x: np.ndarray) -> np.ndarray:
        c_rr, cd, r0 = x
        params = build_params(c_rr, cd, r0, aux)
        parts = []
        for trip in subsets:
            sim = simulate_trip(params, trip)
            obs = (trip.v_batt_v * trip.i_batt_a).to_numpy()
            parts.append((sim - obs) / 1000.0)     # kW, to keep the scale sane
        return np.concatenate(parts)

    x0 = np.array([0.010, 0.29, 0.05])
    result = least_squares(
        residuals, x0,
        bounds=([0.004, 0.15, 0.01], [0.025, 0.45, 0.20]),
        verbose=2, xtol=1e-8,
    )
    c_rr, cd, r0 = (float(v) for v in result.x)

    rmse_kw = float(np.sqrt(np.mean(result.fun ** 2)))
    print(f"\nc_rr = {c_rr:.5f}\ncd   = {cd:.5f}\nr0   = {r0:.5f}")
    print(f"training residual RMSE = {rmse_kw:.3f} kW")

    Path(args.out).write_text(json.dumps({
        "identified": {"c_rr": c_rr, "cd": cd, "r0_ohm": r0},
        "aux": {"p_base_w": aux.p_base_w, "k_heat_w_per_c": aux.k_heat_w_per_c,
                "k_cool_w_per_c": aux.k_cool_w_per_c, "t_setpoint_c": aux.t_setpoint_c},
        "published": PUBLISHED,
        "citations": CITATIONS,
        "fit_trips": trips,
        "train_residual_rmse_kw": rmse_kw,
    }, indent=2))
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Review the parameter sources**

The figures above are filled in and cited (references [R1] to [R6] in the
module). Zero `TODO-VERIFY` markers remain; confirm with:

```bash
grep -c "TODO-VERIFY" scripts/identify_params.py
```

Expected: `0`.

Then read the CAVEATS block and satisfy yourself about the five items it
raises, because each is a place where a plausible-looking number could be
wrong:

1. `frontal_area_m2` comes from a forum-sourced CdA of 0.690 m2. Low risk, since
   `cd` is fitted and the identification calibrates the CdA product.
2. `drivetrain_eta`, the motor efficiency map, the RC branch, the current limits
   and the regen ceiling are **engineering assumptions**, not BMW figures. They
   must be described as assumptions in the paper.
3. `wheel_radius_m` is geometric rather than dynamic. Mostly cancels, because
   `simulate_trip` inverts force to torque with the same radius the plant uses
   to convert back.
4. `capacity_ah` is the 60 Ah nameplate. If the dataset's SoC channel is
   referenced to usable capacity, ~52.2 Ah with a [0, 1] window is correct
   instead. A systematic ~13% SoC drift at G2 is the signature.
5. The OCV curve is a representative 96s NCA characteristic, not an i3
   measurement, and is the most likely single cause of SoC error at G2.

Sanity-check the arithmetic before running anything:

```bash
python3 -c "
from evpil.plant.auxiliary import AuxParams
from scripts.identify_params import build_params
vp = build_params(0.010, 0.29, 0.05, AuxParams(300.0, 180.0, 90.0))
print('CdA      ', vp.cd * vp.frontal_area_m2, 'm^2   (published 0.690)')
print('gross kWh', vp.battery.capacity_ah * 360 / 1000, '  (published 21.6)')
print('usable   ', vp.battery.capacity_ah * 360 / 1000 * (vp.battery.soc_max - vp.battery.soc_min), '  (published 18.8)')
"
```

Expected: 0.690, 21.6, 18.8. `VehicleParams` raises on any blank citation, so a
successful construction is itself part of the check.

- [ ] **Step 3: Run the identification**

Run: `python scripts/identify_params.py`
Expected: `least_squares` converges, printing decreasing cost; final `c_rr` in roughly 0.008 to 0.015, `cd` near the published figure, `r0` in roughly 0.02 to 0.10 ohm.

If a fitted value pins against a bound, the model is absorbing an error that belongs elsewhere. Do not widen the bound to make it converge — find out what is wrong. A `c_rr` of 0.025 means something else in the chain is missing.

- [ ] **Step 4: Record the outcome**

Append to `docs/dataset-provenance.md`: the identified values, the training residual RMSE, the trips used for identification, and each published figure with its source. Note any parameter that pinned against a bound and what you concluded.

- [ ] **Step 5: Commit**

```bash
git add scripts/__init__.py scripts/identify_params.py data/i3_params.json docs/dataset-provenance.md
git commit -m "feat: vehicle parameter identification against logged trips"
```

---

### Task 16: Plant validation harness (Gate G2)

**Files:**
- Create: `scripts/validate_plant.py`
- Create: `docs/g2-plant-validation.md`

**Interfaces:**
- Consumes: `data/i3_params.json` from Task 15; `Plant` from Task 14; splits from Task 9.
- Produces: `docs/g2-plant-validation.md` with the G2 verdict. **Phase 2 does not begin until this gate passes.**

This is the most important gate in Phase 1. If the plant cannot reproduce real trips, every downstream result is built on a simulator that does not describe the vehicle, and no amount of modelling work fixes that.

Validation runs on the **validation** trips, never the test trips.

- [ ] **Step 1: Write the harness**

```python
# scripts/validate_plant.py
"""G2: does the plant reproduce held-out real trips?

Pass criterion, from spec section 6.1: battery-power RMSE at most 10% of the
trip's mean absolute power, and terminal SoC error at most 2 percentage points,
on every validation trip.

Runs on validation trips only. Test trips stay sealed until the end of the
project.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from evpil.data.i3_loader import load_all_trips
from evpil.data.splits import Split, apply_split
from evpil.plant.auxiliary import AuxParams
from scripts.identify_params import MAPPING, build_params, simulate_trip

POWER_RMSE_FRACTION = 0.10      # of mean absolute power
SOC_ERROR_LIMIT = 0.02          # 2 percentage points


def validate_trip(params, trip: pd.DataFrame) -> dict[str, float]:
    sim_p = simulate_trip(params, trip)
    obs_p = (trip.v_batt_v * trip.i_batt_a).to_numpy()

    rmse = float(np.sqrt(np.mean((sim_p - obs_p) ** 2)))
    mean_abs = float(np.mean(np.abs(obs_p)))
    rel = rmse / mean_abs if mean_abs > 0 else float("inf")

    # Integrate simulated current to get terminal SoC, and compare with logged.
    dt = np.diff(trip.t_s.to_numpy(), prepend=trip.t_s.iloc[0])
    i_sim = np.divide(sim_p, trip.v_batt_v.to_numpy(),
                      out=np.zeros_like(sim_p),
                      where=trip.v_batt_v.to_numpy() > 0)
    ah_used = float(np.sum(i_sim * dt) / 3600.0)
    soc_sim_end = float(trip.soc_frac.iloc[0]) - ah_used / params.battery.capacity_ah
    soc_err = abs(soc_sim_end - float(trip.soc_frac.iloc[-1]))

    return {
        "power_rmse_w": rmse,
        "mean_abs_power_w": mean_abs,
        "power_rmse_frac": rel,
        "soc_sim_end": soc_sim_end,
        "soc_obs_end": float(trip.soc_frac.iloc[-1]),
        "soc_abs_error": soc_err,
        "passes": float(rel <= POWER_RMSE_FRACTION and soc_err <= SOC_ERROR_LIMIT),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/raw/i3")
    ap.add_argument("--splits", default="data/splits.json")
    ap.add_argument("--params", default="data/i3_params.json")
    args = ap.parse_args()

    cfg = json.loads(Path(args.params).read_text())
    aux = AuxParams(**cfg["aux"])
    params = build_params(cfg["identified"]["c_rr"], cfg["identified"]["cd"],
                          cfg["identified"]["r0_ohm"], aux)

    sp = json.loads(Path(args.splits).read_text())
    df = load_all_trips(Path(args.data), MAPPING)
    _, val, _ = apply_split(df, Split(sp["train"], sp["val"], sp["test"]))

    rows = []
    for trip_id in sorted(val.trip_id.unique()):
        trip = val[val.trip_id == trip_id].reset_index(drop=True)
        r = validate_trip(params, trip)
        r["trip_id"] = trip_id
        rows.append(r)
        print(f"{trip_id:20s} rmse={r['power_rmse_w']:9.1f} W "
              f"({r['power_rmse_frac']*100:5.1f}%)  "
              f"soc_err={r['soc_abs_error']*100:5.2f} pp  "
              f"{'PASS' if r['passes'] else 'FAIL'}")

    out = pd.DataFrame(rows)
    out.to_csv("docs/g2-per-trip.csv", index=False)

    n_fail = int((out.passes == 0).sum())
    print(f"\nvalidation trips: {len(out)}")
    print(f"median power RMSE: {out.power_rmse_frac.median()*100:.1f}%")
    print(f"worst  power RMSE: {out.power_rmse_frac.max()*100:.1f}%")
    print(f"worst  SoC error : {out.soc_abs_error.max()*100:.2f} pp")
    print(f"\nG2 {'PASS' if n_fail == 0 else f'FAIL ({n_fail} trips)'}")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run the validation**

Run: `python -m scripts.validate_plant`
Expected: one line per validation trip, then the G2 verdict.

- [ ] **Step 3: Evaluate Gate G2 and record it**

Write `docs/g2-plant-validation.md` containing the full output, a scatter plot of simulated against logged battery power for the best and worst trips, a time-series overlay for one representative trip, and the verdict.

**If G2 fails, stop. Do not start Phase 2.** Work through these in order and record which one mattered:

1. Plot simulated against logged power over time for the worst trip. A constant offset points at the auxiliary model; an offset that scales with speed points at `c_rr` or `cd`; errors concentrated in acceleration transients point at mass or the inertial term; errors concentrated in braking point at the regeneration model.
2. Check the sign convention on `i_batt_a` in the archive. If the dataset uses positive-for-charge, every power figure is inverted and nothing else will make sense.
3. Check that `p_aux_w` is the full auxiliary load and not the heating circuit alone. If it excludes other loads, the base term absorbs the difference and the fit will look worse than the model deserves.
4. Verify the OCV curve. The placeholder in `build_params` is a guess and is the most likely single cause of a systematic SoC error.
5. If the criterion turns out to be unachievable for a defensible reason, revise it **once**, record the new threshold and the full justification in `docs/g2-plant-validation.md`, and note the change in the spec's section 6.1. Do not silently relax it.

- [ ] **Step 4: Commit**

```bash
git add scripts/validate_plant.py docs/g2-plant-validation.md docs/g2-per-trip.csv
git commit -m "feat: plant validation harness, gate G2 evaluated"
```

---

## Phase 1 exit criteria

Phase 2 begins only when all three hold:

| Gate | Evidence | Location |
|---|---|---|
| **G1** | Measured MACs/s; chosen Transformer configuration | `docs/g1-compute-budget.md` |
| **G2** | Every validation trip within 10% power RMSE and 2 pp SoC error | `docs/g2-plant-validation.md` |
| **G3** | p99 jitter at most 1 ms, zero dropped frames over 10 minutes | `docs/g3-link-characterisation.md` |

Also complete by the end of Phase 1:

- `docs/hardware-inventory.md` states the usable SRAM budget
- `docs/dataset-provenance.md` records the real schema, the split, the auxiliary fit, and every cited vehicle parameter
- `data/splits.json` is committed and the test trips remain unread
- `docs/measurement-rig.md` records the AD3 capture configuration
- `python -m pytest` passes: 25 data, 63 plant, 10 protocol, 6 link, 1 smoke = 105 tests
- `cd firmware/host_test && make check` passes
