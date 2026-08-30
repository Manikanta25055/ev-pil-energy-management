#pragma once
#include <stdint.h>

#define CTRL_PERIOD_MS    10

/* How the control task obtains the plant state.

   0  synchronous: send a request and block for the reply inside the same
      10 ms slot. Simple, and it ties the control deadline to the host's
      scheduling tail. Gate G3 measured six missed replies in 59,650 loops
      this way, all inside one minute on an otherwise idle laptop, and the
      misses were the host's rather than the device's.

   1  pipelined: request the next state, act on the most recent state already
      held, and read replies without blocking. The control period is then
      independent of host latency. The cost is one sample of age on the state,
      which is 10 ms, and that is a real cost rather than a free win: it is
      the same quantity spec 6.5 injects deliberately as a communication-delay
      scenario.

   Both are built so the comparison is a rebuild rather than a rewrite, and so
   that the loop the paper reports is the loop that was measured. */
#ifndef CTRL_PIPELINED
#define CTRL_PIPELINED 1
#endif
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
    uint32_t stale_steps;          /* loops that acted on a state older than one step */
    uint32_t stale_worst;          /* longest run of consecutive stale loops */
    uint16_t jitter_hist[JITTER_N_BINS];
} diag_stats_t;

void tasks_start(void);
