#include "bench_actor.h"
#include "actor.h"
#include <sac_actor_weights.h>

#include <stdio.h>
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

/* Fixed observations, already scaled, spanning the corners and the middle of
   the declared observation box. Mirrored by PROBES in scripts/verify_actor.py.
   Corners matter more than random draws here: saturation and sign changes are
   where a transposed weight matrix or a row-major mix-up shows up, and a
   uniform sample would visit those almost never. */
#define N_PROBE 9
static const float k_probe[N_PROBE][8] = {
    { 0.80f,  0.30f,  0.00f,  0.33f,  0.00f,  0.00f,  0.00f,  0.00f},
    { 0.20f,  0.00f,  0.00f,  0.33f,  0.00f,  0.00f,  0.00f,  0.00f},
    { 0.94f,  0.75f, -0.40f,  0.33f,  0.30f, -0.20f, -0.50f, -0.10f},
    { 0.07f,  0.10f,  0.40f,  0.50f, -0.30f,  0.20f,  0.90f,  1.00f},
    { 0.50f,  0.50f,  0.20f,  0.33f,  0.10f,  0.05f,  0.25f,  0.40f},
    {-1.00f, -1.00f, -1.00f, -1.00f, -1.00f, -1.00f, -1.00f, -1.00f},
    { 1.00f,  1.00f,  1.00f,  1.00f,  1.00f,  1.00f,  1.00f,  1.00f},
    {10.00f, 10.00f, 10.00f, 10.00f, 10.00f, 10.00f, 10.00f, 10.00f},
    { 0.00f,  0.00f,  0.00f,  0.00f,  0.00f,  0.00f,  0.00f,  0.00f},
};

#define N_REPEAT 200

/* Measure once, then print the same report on a loop.

   The console shares the native USB-Serial-JTAG peripheral, which delivers
   nothing to the first host connection after a reset and drops anything
   printed while no host is attached. A report printed once at boot is
   therefore a report the host usually misses, and the failure looks exactly
   like firmware that is not running -- the same trap that cost a long detour
   during gate G3. Repeating it costs nothing and removes the race. */
void bench_actor_report(void)
{
    bench_actor_measure();
    for (;;) {
        bench_actor_print();
        vTaskDelay(pdMS_TO_TICKS(2000));
    }
}

static float s_action[N_PROBE][8];
static double s_mean_us;
static uint32_t s_worst_us;

void bench_actor_measure(void)
{
    float action[8];
    for (int p = 0; p < N_PROBE; p++) {
        actor_forward(k_probe[p], action);
        for (int j = 0; j < 8; j++) s_action[p][j] = action[j];
    }

    /* Timed separately from the printing, and over many repeats: a single
       inference is shorter than the timer's own overhead is stable. */
    s_worst_us = 0;
    int64_t t0 = esp_timer_get_time();
    for (int r = 0; r < N_REPEAT; r++) {
        uint32_t dur = actor_forward(k_probe[r % N_PROBE], action);
        if (dur > s_worst_us) s_worst_us = dur;
    }
    s_mean_us = (double) (esp_timer_get_time() - t0) / N_REPEAT;
}

void bench_actor_print(void)
{
    printf("EVPIL-ACTOR geometry in=%d out=%d params=%d layers=%d\n",
           actor_n_in(), actor_n_out(), actor_n_params(),
           SAC_ACTOR_N_LAYERS);
    printf("EVPIL-ACTOR checksum=%08x\n", (unsigned) actor_checksum());
    printf("EVPIL-ACTOR bytes=%u\n",
           (unsigned) (actor_n_params() * sizeof(float)));

    for (int p = 0; p < N_PROBE; p++) {
        printf("EVPIL-ACTOR probe %d", p);
        for (int j = 0; j < actor_n_out(); j++) printf(" %.7e", s_action[p][j]);
        printf("\n");
    }

    printf("EVPIL-ACTOR latency_mean_us %.3f\n", s_mean_us);
    printf("EVPIL-ACTOR latency_worst_us %u\n", (unsigned) s_worst_us);
    printf("EVPIL-ACTOR repeats %d\n", N_REPEAT);
    printf("EVPIL-ACTOR done\n");
}
