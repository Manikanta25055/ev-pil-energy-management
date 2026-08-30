#include <stdio.h>
#include "esp_chip_info.h"
#include "esp_psram.h"
#include "esp_system.h"
#include "esp_heap_caps.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#include "bench_encoder.h"
#include "bench_mac.h"
#include "link.h"
#include "tasks.h"
#include "timing.h"

/* Set to 1 for the gate G1 measurement run, then back to 0. */
#define RUN_G1_BENCHMARK 0

/* Set to 1 to time the deployed encoder shape on silicon (gate G5 latency).
   G1 measured a raw multiply-accumulate rate; this measures the real graph,
   including the softmax, normalisation and memory traffic that a MAC count
   cannot see. */
#define RUN_G5_BENCHMARK 0

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

#if RUN_G1_BENCHMARK || RUN_G5_BENCHMARK
#if RUN_G1_BENCHMARK
    bench_mac_report();
#endif
#if RUN_G5_BENCHMARK
    bench_encoder_report();
#endif
    while (1) {
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
#else
    link_init();
    timing_init();
    tasks_start();
    /* app_main returns; the pinned tasks keep running. */
#endif
}
