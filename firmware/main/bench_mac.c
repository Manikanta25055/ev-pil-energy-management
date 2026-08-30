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
