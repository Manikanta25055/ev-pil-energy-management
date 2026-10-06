#include "tasks.h"
#include "control.h"
#include "link.h"
#include "protocol.h"
#include "timing.h"

#include <stdio.h>
#include <string.h>
#include "esp_timer.h"
#include "esp_system.h"
#include "esp_task_wdt.h"
#if HAVE_SAC_ACTOR
#include "actor.h"
#include <sac_actor_weights.h>
#endif
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

#if FAULT_INJECT
/* True while `now_us` lies in the [at_s, at_s + FAULT_WINDOW_S) window. */
static bool fault_window(uint32_t now_us, uint32_t at_s)
{
    uint32_t t_s = now_us / 1000000u;
    return t_s >= at_s && t_s < at_s + FAULT_WINDOW_S;
}
#endif

static float s_torque_cmd  = 0.0f;

/* The outer loop's published setpoint, with the time it was published. The
   timestamp is the whole mechanism behind the fallback: the control task
   never asks whether the energy manager is alive, it asks how old its last
   answer is, which is a question with an answer even when the answer is
   "the task is gone". */
static volatile float    s_regen_blend = 0.5f;
static volatile float    s_p_limit_w   = 50000.0f;
/* Written by the outer loop once something there decides it; until then it is
   the build's constant. */
static volatile float    s_speed_alpha = SPEED_FILTER_ALPHA;
static speed_filter_t    s_speed_filt;
#if SPEED_KALMAN == 4
static fault_kalman_t    s_fault;
#elif SPEED_KALMAN
static kalman_speed_t    s_kalman;
#endif
#if SPEED_KALMAN
static bool              s_kalman_ready;
static float             s_v_ctl;           /* last estimate handed to the PID */
/* The command before last. In the pipelined loop the state this step acts on
   is the reply to the previous request, and the torque that moved the car
   into that state was commanded one step earlier still. */
static float             s_torque_prev2;
#endif
static volatile float    s_aux_derate  = 0.0f;
/* Accumulators for the ceiling the energy manager actually applied. Kept out
   of diag_stats_t because the sum has to be 64-bit and the frame is not: a
   campaign cell is 6,000 outer steps and a ceiling can be 100 kW, which wraps
   a 32-bit accumulator and reports a mean far below the truth. */
static uint64_t s_p_limit_sum;
static uint32_t s_p_limit_n;
static volatile uint32_t s_ems_t_us    = 0;

/* Set by infer when it overruns, cleared by ems once it has acted on it. */
static volatile bool s_infer_late = false;

static pid_state_t s_pid;

/* ---- core 0: the hard real-time loop ------------------------------------ */

static void ctrl_task(void *arg)
{
    (void) arg;
    TickType_t next = xTaskGetTickCount();
    uint8_t tx[64], rx[64];
    uint32_t seq = 0;
    uint32_t t_prev = 0;
    const uint32_t nominal_us = CTRL_PERIOD_MS * 1000u;

    uint32_t stale_run = 0;

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
            /* A loop late against its own deadline, which is a different
               failure from the host answering late and is counted apart from
               it. The open G3 question is exactly whether the gate should
               distinguish the two. */
            if (dev > CTRL_LATE_US) s_diag.ctrl_late++;
        }
        t_prev = t_req;

        /* The MCU is the clock master: request one plant step. */
        int m = evpil_pack(tx, sizeof tx, EVPIL_STEP_REQ, seq, t_req, NULL, 0);
        if (m > 0) link_write(tx, (size_t) m);

#if CTRL_PIPELINED
        /* Take whatever has already arrived and move on. One millisecond of
           the ten is the whole budget this is allowed to spend: the reply to
           the previous request has normally been sitting in the buffer for
           most of a period, so the read returns at once, and when it does not
           the loop gives up rather than waiting.

           Zero was tried first and is wrong: `link_read_frame` treats a zero
           timeout as an expired deadline and returns without reading, which
           made every single step stale. */
        int n = link_read_frame(rx, sizeof rx, 1);
        if (n <= 0) {
            stale_run++;
            s_diag.stale_steps++;
            if (stale_run > s_diag.stale_worst) s_diag.stale_worst = stale_run;
        } else {
            stale_run = 0;
        }
#else
        int n = link_read_frame(rx, sizeof rx, CTRL_PERIOD_MS - 1);
#endif
        TIMING_MARK_LOW(TIMING_CH_COMM);

        if (n > 0) {
            evpil_frame_t f;
            if (evpil_unpack(rx, (size_t) n, &f) == 0 && f.type == EVPIL_STATE
                && f.len == STATE_PAYLOAD_BYTES) {
                uint32_t t_rx = (uint32_t) esp_timer_get_time();
                uint32_t rtt  = t_rx - t_req;
                if (rtt > s_diag.rtt_max_us) s_diag.rtt_max_us = rtt;

                float v[STATE_PAYLOAD_BYTES / 4];
                memcpy(v, f.payload, sizeof v);

                xSemaphoreTake(s_state_mux, portMAX_DELAY);
                s_state.v_mps       = v[0];  s_state.a_mps2      = v[1];
                s_state.soc_frac    = v[2];  s_state.i_batt_a    = v[3];
                s_state.v_batt_v    = v[4];  s_state.t_ambient_c = v[5];
                s_state.grade_rad   = v[6];  s_state.p_aux_w     = v[7];
                s_state.v_ref_mps   = v[8];  s_state.a_ref_mps2  = v[9];
                s_state.t_batt_c    = v[10];
                s_state.seq         = f.seq;
                s_state.host_t_us   = f.t_us;
                s_state.rx_t_us     = t_rx;
                xSemaphoreGive(s_state_mux);
            } else {
                s_diag.rx_bad++;
            }
        }
#if !CTRL_PIPELINED
        else {
            s_diag.rx_timeouts++;
        }
        /* Synchronous mode has no separate staleness notion -- a reply either
           arrived inside the slot or did not -- but the limp path is defined
           against the same run length in both, so the run is kept here too.
           Without this the ablation would compare a mode that can limp
           against one that cannot. */
        if (n > 0) stale_run = 0; else stale_run++;
#endif

        /* Control body: PID on speed with a physics feedforward, plus the
           fallback path. */
        TIMING_MARK_HIGH(TIMING_CH_CTRL);
        uint32_t t0 = (uint32_t) esp_timer_get_time();

        xSemaphoreTake(s_state_mux, portMAX_DELAY);
        float v_meas = s_state.v_mps;
#if SPEED_KALMAN == 4
        float a_meas = s_state.a_mps2;
#endif
        float v_ref  = s_state.v_ref_mps;
        float a_ref  = s_state.a_ref_mps2;
        float grade  = s_state.grade_rad;
        float soc    = s_state.soc_frac;
        xSemaphoreGive(s_state_mux);

        float blend  = s_regen_blend;
        float p_lim  = s_p_limit_w;
        float derate = s_aux_derate;

#if FALLBACK_ENABLED
        /* The outer loop has gone quiet: run the rule manager here instead.
           It costs a handful of compares, which is why it can live inside the
           10 ms task at all. */
        if ((uint32_t) (t0 - s_ems_t_us) > EMS_STALE_LIMIT_US) {
            ems_action_t a = control_rule_action(soc, v_meas);
            blend = a.regen_blend;
            p_lim = a.p_limit_w;
            derate = a.aux_derate;
            s_diag.ctrl_fallback_steps++;
        }
#endif

        float omega = (v_meas / k_vehicle.wheel_radius_m) * k_vehicle.gear_ratio;
        float t_lim = control_torque_limit_nm(&k_vehicle, omega);
        if (t_lim <= 0.0f) t_lim = 1e-6f;

#if FALLBACK_ENABLED
        if (stale_run > STALE_LIMIT_STEPS) {
            /* The speed this loop holds is too old to act on. Ramp the torque
               out rather than dropping it, and freeze the integrator: an
               integrator fed a stale error charges up against a vehicle that
               has already moved on. */
            if (s_torque_cmd > LIMP_RAMP_NM)       s_torque_cmd -= LIMP_RAMP_NM;
            else if (s_torque_cmd < -LIMP_RAMP_NM) s_torque_cmd += LIMP_RAMP_NM;
            else                                   s_torque_cmd = 0.0f;
            s_diag.limp_steps++;
        } else
#endif
        {
            float ff = control_feedforward_nm(&k_vehicle, v_ref, a_ref, grade);
#if SPEED_KALMAN
            const float dt = CTRL_PERIOD_MS * 1e-3f;
            /* The torque that produced the state now held. */
#if CTRL_PIPELINED
            float tq_meas = s_torque_prev2;
#else
            float tq_meas = s_torque_cmd;
#endif
            s_torque_prev2 = s_torque_cmd;
            bool fresh = (stale_run == 0);
#if SPEED_KALMAN == 4
            if (!s_kalman_ready) {
                control_fault_kalman_init(&s_fault);
                s_kalman_ready = true;
            }
            /* No new measurement this period: hold the last estimate rather
               than show the detector the same sample twice. */
            if (fresh)
                s_v_ctl = control_fault_kalman_step(
                    &k_vehicle, &s_fault, KALMAN_ADAPT_Q_MPS, KALMAN_QD_MPS2,
                    KALMAN_R_FLOOR_MPS, KALMAN_DR_TAU_S, v_meas, a_meas,
                    tq_meas, grade, dt);
            s_diag.sensor_flag_steps = s_fault.flag_steps;
            s_diag.sensor_alarms = s_fault.alarms;
#else
            const float q = (SPEED_KALMAN == 1) ? KALMAN_FIXED_Q_MPS
                                                : KALMAN_ADAPT_Q_MPS;
            const float q_d = (SPEED_KALMAN == 3) ? KALMAN_QD_MPS2 : 0.0f;
            if (!s_kalman_ready) {
                control_kalman_init(&s_kalman, SPEED_KALMAN == 1
                                    ? KALMAN_FIXED_R_MPS : KALMAN_ADAPT_R0_MPS);
                s_kalman_ready = true;
            }
            /* No new measurement this period: run on the model alone. */
            if (fresh)
                s_v_ctl = control_kalman_step(
                    &k_vehicle, &s_kalman, q, q_d, SPEED_KALMAN != 1,
                    KALMAN_R_FLOOR_MPS, v_meas, tq_meas, grade, dt);
            else
                s_v_ctl = control_kalman_coast(&k_vehicle, &s_kalman, q, q_d,
                                               tq_meas, grade, dt);
#endif
            float v_ctl = s_v_ctl;
#else
            float v_ctl = control_speed_filter_step(&s_speed_filt, v_meas,
                                                    s_speed_alpha);
#endif
            s_torque_cmd = control_pid_step(&k_pid_gains, &s_pid, v_ref,
                                            v_ctl, ff, t_lim,
                                            CTRL_PERIOD_MS * 1e-3f, NULL);
        }

        uint32_t dur = (uint32_t) esp_timer_get_time() - t0;
        if (dur > s_diag.ctrl_wcet_us) s_diag.ctrl_wcet_us = dur;
        TIMING_MARK_LOW(TIMING_CH_CTRL);

        /* Emit the actuation frame. */
        float act[4] = {s_torque_cmd, blend, p_lim, derate};
        m = evpil_pack(tx, sizeof tx, EVPIL_ACTUATION, seq,
                       (uint32_t) esp_timer_get_time(),
                       (const uint8_t *) act, sizeof act);
        if (m > 0) link_write(tx, (size_t) m);

        esp_task_wdt_reset();

        seq++;
        s_diag.loop_count++;

#if FAULT_INJECT == 2
        /* Stop feeding the watchdog and stop yielding. Nothing else in the
           firmware can recover this; the watchdog is the only thing that can,
           which is the property being demonstrated. */
        if ((uint32_t) esp_timer_get_time() / 1000000u >= FAULT_WDT_AT_S) {
            for (;;) { }
        }
#endif
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
        int iters = 20000;
#if FAULT_INJECT == 1
        /* Sized to overrun the 40 ms budget rather than to be slow: the
           counter under test is a budget comparison, so the injected load has
           to cross the budget and not merely rise. The nominal 20,000
           iterations measure 836 us on this board, so 1.3 M lands near 54 ms
           -- past the 40 ms budget and still inside the 100 ms period, which
           keeps this a deadline miss rather than a task that never returns. */
        if (fault_window((uint32_t) t0, FAULT_INFER_AT_S)) iters = 1300000;
#endif
        for (int i = 0; i < iters; i++) acc += i & 0x7F;

        uint32_t dur = (uint32_t) esp_timer_get_time() - t0;
        if (dur > s_diag.infer_wcet_us)  s_diag.infer_wcet_us = dur;
        if (dur > budget_us) {
            s_diag.infer_deadline_misses++;
            s_infer_late = true;
        }
        TIMING_MARK_LOW(TIMING_CH_INFER);

        esp_task_wdt_reset();
        vTaskDelayUntil(&next, pdMS_TO_TICKS(INFER_PERIOD_MS));
    }
}

static void ems_task(void *arg)
{
    (void) arg;
    TickType_t next = xTaskGetTickCount();
    for (;;) {
#if FAULT_INJECT == 1
        if (fault_window((uint32_t) esp_timer_get_time(), FAULT_EMS_AT_S)) {
            /* Publish nothing. The setpoint timestamp stops advancing, which
               is exactly what a hung outer loop looks like to the control
               task. */
            vTaskDelayUntil(&next, pdMS_TO_TICKS(EMS_PERIOD_MS));
            continue;
        }
#endif
        xSemaphoreTake(s_state_mux, portMAX_DELAY);
        float soc     = s_state.soc_frac;
        float v       = s_state.v_mps;
        float a_meas  = s_state.a_mps2;
        float t_batt  = s_state.t_batt_c;
        float grade   = s_state.grade_rad;
        float v_ref   = s_state.v_ref_mps;
        xSemaphoreGive(s_state_mux);

        bool late = s_infer_late;
        s_infer_late = false;
        if (late) s_diag.ems_fallback_steps++;

        ems_action_t a;
#if HAVE_SAC_ACTOR
        if (late) {
            /* The policy did not answer in time, so the rules take over. This
               is the branch ems_fallback_steps has always counted; until the
               actor was deployed both branches produced the same action and
               the counter recorded an opportunity rather than an event. */
            a = control_rule_action(soc, v);
        } else {
            /* The eight observations the policy was trained on, in the order
               evpil.control.env.OBS_NAMES declares them. The last two are the
               forecast channels and are held at zero on purpose: the deployed
               policy is the without-forecast arm of ablation A3, trained with
               these at zero, and no forecaster runs on this device. Feeding a
               with-forecast policy two dead channels would be a different
               controller that still looked like it was working. */
            float raw[SAC_ACTOR_N_IN] = {
                soc, v, a_meas, t_batt, grade, v_ref - v, 0.0f, 0.0f,
            };
            float scaled[SAC_ACTOR_N_IN];
            float act[SAC_ACTOR_N_OUT];
            actor_scale_observation(raw, scaled, SAC_ACTOR_N_IN);
            uint32_t us = actor_forward(scaled, act);
            if (us > s_diag.actor_wcet_us) s_diag.actor_wcet_us = us;
            s_diag.actor_steps++;
            actor_decode_action_raw(act, &a.regen_blend,
                                    &a.p_limit_w, &a.aux_derate);
        }
#else
        (void) a_meas; (void) t_batt; (void) grade; (void) v_ref;
        a = control_rule_action(soc, v);
#endif
        s_regen_blend = a.regen_blend;
        s_p_limit_w   = a.p_limit_w;
        s_aux_derate  = a.aux_derate;
        s_ems_t_us    = (uint32_t) esp_timer_get_time();

        /* Record the ceiling this step actually applied. The sum is kept in
           64 bits and divided when the frame is packed: a run is 6,000 outer
           steps and a ceiling can be 100 kW, so a 32-bit accumulator would
           wrap inside a single campaign cell and report a mean far below the
           truth. Negative is not physical here and is clamped rather than
           wrapped into a huge unsigned. */
        {
            float pl_f = a.p_limit_w;
            uint32_t pl = (pl_f <= 0.0f) ? 0u : (uint32_t) pl_f;
            if (pl < s_diag.p_limit_min_w) s_diag.p_limit_min_w = pl;
            if (pl > s_diag.p_limit_max_w) s_diag.p_limit_max_w = pl;
            s_p_limit_sum += (uint64_t) pl;
            s_p_limit_n++;
        }

        vTaskDelayUntil(&next, pdMS_TO_TICKS(EMS_PERIOD_MS));
    }
}

static void diag_task(void *arg)
{
    (void) arg;
    TickType_t next = xTaskGetTickCount();
    uint8_t tx[160];
    uint8_t payload[24 * 4 + JITTER_N_BINS * 2];
    uint32_t seq = 0;

    for (;;) {
        /* Sent as a frame rather than printed. The link and the console share
           one USB endpoint when the transport is USB-Serial-JTAG, and text
           interleaved into a binary stream costs the host a resynchronisation
           on every diagnostic line. Framing it also means the host parses one
           format instead of scraping a printf. */
        /* The mean is computed here rather than carried, so the running sum
           can stay 64-bit without widening the frame. Before any outer step
           the ceiling fields read 0, which is separable from a real ceiling
           of 0 W because loop_count is 0 too. */
        s_diag.p_limit_mean_w = s_p_limit_n
            ? (uint32_t) (s_p_limit_sum / s_p_limit_n) : 0u;
        uint32_t pl_min = s_p_limit_n ? s_diag.p_limit_min_w : 0u;

        /* Order must match evpil.protocol.DIAG_FIELDS. */
        uint32_t u32[24] = {
            s_diag.loop_count, s_diag.rx_timeouts, s_diag.rx_bad,
            s_diag.infer_deadline_misses, s_diag.ctrl_wcet_us,
            s_diag.infer_wcet_us, s_diag.rtt_max_us,
            s_diag.period_min_us, s_diag.period_max_us,
            s_diag.stale_steps, s_diag.stale_worst,
            s_diag.ctrl_late, s_diag.ctrl_fallback_steps,
            s_diag.limp_steps, s_diag.ems_fallback_steps,
            s_diag.boot_reason,
            s_diag.actor_steps, s_diag.actor_wcet_us,
            pl_min, s_diag.p_limit_mean_w, s_diag.p_limit_max_w,
            (uint32_t) SPEED_KALMAN, s_diag.sensor_flag_steps,
            s_diag.sensor_alarms,
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
    /* Not zero: this is a running minimum and zero is the smallest ceiling
       there is, so a zeroed field would never be replaced and every run would
       report a floor of 0 W. */
    s_diag.p_limit_min_w = UINT32_MAX;
    s_p_limit_sum = 0;
    s_p_limit_n = 0;
    memset(&s_pid, 0, sizeof s_pid);

    /* The reset reason survives a reset, which is the only way a watchdog
       event can be reported at all: the firmware that would have reported it
       is the firmware that was restarted. It is sent in every DIAG frame so
       the host sees it whenever it connects, not only if it happened to be
       listening at the moment of the reset. */
    s_diag.boot_reason = (uint32_t) esp_reset_reason();
    printf("EVPIL-BOARD boot_reason=%u\n", (unsigned) s_diag.boot_reason);

    /* The watchdog covers the two tasks whose failure is silent. A control
       task that stops feeding it stops producing actuation frames, and the
       host would see that; a control task stuck inside a link read produces
       nothing and also says nothing, and that is the case this catches. The
       timeout is far longer than either period on purpose -- this is a
       liveness guard, not a deadline monitor, and the deadline monitors are
       the counters above. */
    esp_task_wdt_config_t wdt = {
        .timeout_ms = 2000,
        .idle_core_mask = 0,
        .trigger_panic = true,
    };
    if (esp_task_wdt_init(&wdt) == ESP_ERR_INVALID_STATE)
        esp_task_wdt_reconfigure(&wdt);

    /* Core 0 owns the hard real-time loop; core 1 owns everything else, so
       inference can never delay control. */
    TaskHandle_t h_ctrl = NULL, h_infer = NULL;
    xTaskCreatePinnedToCore(ctrl_task,  "ctrl",  4096, NULL, 20, &h_ctrl,  0);
    xTaskCreatePinnedToCore(infer_task, "infer", 8192, NULL,  5, &h_infer, 1);
    esp_task_wdt_add(h_ctrl);
    esp_task_wdt_add(h_infer);
    xTaskCreatePinnedToCore(ems_task,   "ems",   4096, NULL,  8, NULL, 1);
    xTaskCreatePinnedToCore(diag_task,  "diag",  4096, NULL,  1, NULL, 1);
}
