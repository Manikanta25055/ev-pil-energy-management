// Gate G1: int8 MAC throughput on the ESP32-S3.
//
// Arduino port of firmware/main/bench_mac.c, kept numerically identical so the
// two are comparable. See docs/g1-compute-budget.md for the verdict.
//
// Why this exists: the ESP-IDF build works but takes ~30 min from cold on this
// machine. The measurement itself needs no RTOS, no task set and no driver, so
// it runs standalone here. The real firmware still targets ESP-IDF, because it
// needs FreeRTOS core pinning and ESP-NN vector kernels; neither affects this
// number.
//
// Board settings baked into the FQBN used to build this:
//   esp32:esp32:esp32s3  CPUFreq=240  CDCOnBoot=cdc  FlashSize=8M
// CPUFreq=240 matters: the whole measurement scales with it.

#include <Arduino.h>
#include "esp_timer.h"
#include "esp_chip_info.h"

#define MAX_N 4096

static int8_t s_a[MAX_N];
static int8_t s_b[MAX_N];
static volatile int32_t s_sink;

static void fill(int n) {
  for (int i = 0; i < n; i++) {
    s_a[i] = (int8_t)((i * 7) & 0x7F) - 64;
    s_b[i] = (int8_t)((i * 13) & 0x7F) - 64;
  }
}

// The Arduino core builds sketches at -Os, while our ESP-IDF sdkconfig sets
// CONFIG_COMPILER_OPTIMIZATION_PERF (-O2). Forcing -O2 on just this function
// keeps the two builds comparable instead of quietly reporting a slower number.
__attribute__((optimize("O2")))
static uint32_t bench_mac_run(int n, int reps) {
  if (n > MAX_N) n = MAX_N;
  fill(n);

  int64_t t0 = esp_timer_get_time();
  for (int r = 0; r < reps; r++) {
    int32_t acc = 0;
    for (int i = 0; i < n; i++) {
      acc += (int32_t)s_a[i] * (int32_t)s_b[i];
    }
    s_sink = acc;  // volatile: prevents the loop being optimised away
  }
  int64_t t1 = esp_timer_get_time();

  return (uint32_t)(t1 - t0);
}

static void report_board() {
  esp_chip_info_t info;
  esp_chip_info(&info);

  Serial.printf("EVPIL-BOARD cores=%d rev=%d cpu_mhz=%lu\n",
                info.cores, info.revision, (unsigned long)getCpuFrequencyMhz());
  Serial.printf("EVPIL-BOARD internal_free=%u\n",
                (unsigned)ESP.getFreeHeap());
  Serial.printf("EVPIL-BOARD psram_size=%u\n",
                (unsigned)ESP.getPsramSize());
}

static void bench_mac_report() {
  const int sizes[] = {64, 256, 1024, 4096};
  const int reps = 2000;

  for (int k = 0; k < 4; k++) {
    int n = sizes[k];
    uint32_t us = bench_mac_run(n, reps);
    double macs = (double)n * (double)reps;
    double mmac_s = macs / (double)us;  // MACs/us == MMACs/s

    Serial.printf("EVPIL-G1 n=%d reps=%d us=%u mmac_per_s=%.2f\n",
                  n, reps, (unsigned)us, mmac_s);
  }
}

void setup() {
  Serial.begin(115200);
  // Native USB CDC needs a moment to enumerate before the host can attach.
  delay(3000);

  Serial.println("EVPIL-G1-BEGIN");
  report_board();
  bench_mac_report();
  Serial.println("EVPIL-G1-END");
}

void loop() {
  // Re-run every 10 s so a late-attaching monitor still catches a full report.
  delay(10000);
  Serial.println("EVPIL-G1-BEGIN");
  report_board();
  bench_mac_report();
  Serial.println("EVPIL-G1-END");
}
