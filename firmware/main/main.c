#include <stdio.h>
#include "esp_chip_info.h"
#include "esp_psram.h"
#include "esp_system.h"
#include "esp_heap_caps.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#include "bench_encoder.h"
#include "bench_mac.h"
#if HAVE_SAC_ACTOR
#include "bench_actor.h"
#endif
#include "link.h"
#include "tasks.h"
#include "timing.h"

/* Set by -DRUN_G1_BENCHMARK=1: the gate G1 measurement run.
   A build switch rather than an edit, so the firmware that produced a number
   can be rebuilt from the command that produced it. It has to be one for the
   Arduino-core build in any case, which has no equivalent of editing a
   sdkconfig and rebuilding in place. */
#ifndef RUN_G1_BENCHMARK
#define RUN_G1_BENCHMARK 0
#endif

/* Set by -DRUN_G5_BENCHMARK=1: time the deployed encoder shape on silicon
   (gate G5 latency). G1 measured a raw multiply-accumulate rate; this measures
   the real graph, including the softmax, normalisation and memory traffic that
   a MAC count cannot see. */
#ifndef RUN_G5_BENCHMARK
#define RUN_G5_BENCHMARK 0
#endif

/* Set by -DRUN_ACTOR_BENCH=1: run the exported SAC actor over a fixed set of
   observations, print each action for the host to check against numpy, and
   time it. Week 8's on-device verification. */
#ifndef RUN_ACTOR_BENCH
#define RUN_ACTOR_BENCH 0
#endif
#if RUN_ACTOR_BENCH && !HAVE_SAC_ACTOR
#error "RUN_ACTOR_BENCH needs sac_actor_weights.h; run scripts/verify_actor.py --export"
#endif

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

#if RUN_G1_BENCHMARK || RUN_G5_BENCHMARK || RUN_ACTOR_BENCH
    /* The actor bench prints a fixed set of actions for the host to check
       against numpy, so it runs once and is not repeated. */
#if RUN_ACTOR_BENCH
    bench_actor_report();
#endif
    /* G1 and G5 repeat instead of printing once at boot.
       The board's USB CDC device re-enumerates when it resets, so a line
       printed during boot is a race against the host reopening the port; it
       used to be won by leaving a serial monitor running and reading the
       result off the screen. Repeating removes the race and turns a single
       number into a distribution, which is worth more than the two seconds it
       costs. Both benchmarks work out of static buffers and carry no state
       between runs, so each repeat measures the same thing. */
    while (1) {
#if RUN_G1_BENCHMARK
        bench_mac_report();
#endif
#if RUN_G5_BENCHMARK
        bench_encoder_report();
#endif
        vTaskDelay(pdMS_TO_TICKS(2000));
    }
#else
    link_init();
    timing_init();
    tasks_start();
    /* app_main returns; the pinned tasks keep running. */
#endif
}
