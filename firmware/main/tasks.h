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
