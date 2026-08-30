#include <stdio.h>
#include "esp_chip_info.h"
#include "esp_psram.h"
#include "esp_system.h"
#include "esp_heap_caps.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#include "bench_mac.h"
#include "link.h"
#include "tasks.h"
#include "timing.h"

/* Set to 1 for the Task 2 (gate G1) measurement run, then back to 0. */
#define RUN_G1_BENCHMARK 0

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

#if RUN_G1_BENCHMARK
    bench_mac_report();
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
