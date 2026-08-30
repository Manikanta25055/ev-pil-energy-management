#include "tasks.h"
#include "link.h"
#include "protocol.h"
#include "timing.h"

#include <stdio.h>
#include <string.h>
#include "esp_timer.h"
#include "esp_system.h"
#include "esp_heap_caps.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"

const uint32_t k_jitter_edges_us[JITTER_N_BINS - 1] = {
    25, 50, 100, 150, 200, 300, 500, 750, 1000, 1500, 2000, 5000,
};

static plant_state_t s_state;
static diag_stats_t  s_diag;
static SemaphoreHandle_t s_state_mux;

/* Linear scan over twelve edges. A binary search would be faster and this is
   on the control path, but twelve compares is under a microsecond at 240 MHz
   and the measurement must not perturb what it measures by more than it
   resolves. */
static void jitter_record(uint32_t dev_us)
{
    for (int k = 0; k < JITTER_N_BINS - 1; k++) {
        if (dev_us <= k_jitter_edges_us[k]) {
            if (s_diag.jitter_hist[k] < 0xFFFF) s_diag.jitter_hist[k]++;
            return;
        }
    }
    if (s_diag.jitter_hist[JITTER_N_BINS - 1] < 0xFFFF)
        s_diag.jitter_hist[JITTER_N_BINS - 1]++;
}

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
    uint32_t t_prev = 0;
    const uint32_t nominal_us = CTRL_PERIOD_MS * 1000u;

    for (;;) {
        TIMING_MARK_HIGH(TIMING_CH_COMM);
        uint32_t t_req = (uint32_t) esp_timer_get_time();

        /* Jitter is the gap between consecutive loop starts, measured by the
           MCU against its own clock. The first iteration has no predecessor
           and is skipped rather than counted as a 10 ms error. */
        if (t_prev != 0) {
            uint32_t period = t_req - t_prev;
            uint32_t dev = (period > nominal_us) ? (period - nominal_us)
                                                 : (nominal_us - period);
            jitter_record(dev);
            if (s_diag.period_min_us == 0 || period < s_diag.period_min_us)
                s_diag.period_min_us = period;
            if (period > s_diag.period_max_us) s_diag.period_max_us = period;
        }
        t_prev = t_req;

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
    uint8_t tx[128];
    uint8_t payload[9 * 4 + JITTER_N_BINS * 2];
    uint32_t seq = 0;

    for (;;) {
        /* Sent as a frame rather than printed. The link and the console share
           one USB endpoint when the transport is USB-Serial-JTAG, and text
           interleaved into a binary stream costs the host a resynchronisation
           on every diagnostic line. Framing it also means the host parses one
           format instead of scraping a printf. */
        uint32_t u32[9] = {
            s_diag.loop_count, s_diag.rx_timeouts, s_diag.rx_bad,
            s_diag.infer_deadline_misses, s_diag.ctrl_wcet_us,
            s_diag.infer_wcet_us, s_diag.rtt_max_us,
            s_diag.period_min_us, s_diag.period_max_us,
        };
        memcpy(payload, u32, sizeof u32);
        memcpy(payload + sizeof u32, s_diag.jitter_hist,
               sizeof s_diag.jitter_hist);

        int m = evpil_pack(tx, sizeof tx, EVPIL_DIAG, seq++,
                           (uint32_t) esp_timer_get_time(),
                           payload, (uint8_t) sizeof payload);
        if (m > 0) link_write(tx, (size_t) m);

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
