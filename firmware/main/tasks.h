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

/* Absolute deviation of the realised control period from CTRL_PERIOD_MS, in
   microseconds. Mirrored by JITTER_BIN_EDGES_US in evpil/protocol.py; the two
   must stay in step or the host will label the bins wrongly. Gate G3 is stated
   as a p99, and a percentile needs a distribution, so the MCU keeps one. */
#define JITTER_N_BINS  13
extern const uint32_t k_jitter_edges_us[JITTER_N_BINS - 1];

typedef struct {
    uint32_t loop_count;
    uint32_t rx_timeouts;
    uint32_t rx_bad;
    uint32_t infer_deadline_misses;
    uint32_t ctrl_wcet_us;
    uint32_t infer_wcet_us;
    uint32_t rtt_max_us;
    uint32_t period_min_us;
    uint32_t period_max_us;
    uint16_t jitter_hist[JITTER_N_BINS];
} diag_stats_t;

void tasks_start(void);
