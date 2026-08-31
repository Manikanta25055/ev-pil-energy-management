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

/* Deadline handling, spec 4.4. Ablation A4 turns this off and measures what
   it was worth, so it is a compile-time switch rather than a rewrite.

   Three distinct failures, three distinct responses, three distinct counters.
   Collapsing them into one "fault" state is how a controller ends up limping
   because a diagnostic task was late.

     ctrl_fallback  the 100 ms outer loop has not published a setpoint inside
                    its staleness window. The rule-based manager runs inside
                    the control task instead. Tracking is unaffected; only the
                    energy-management command changes.
     limp           the plant state itself is stale beyond STALE_LIMIT_STEPS.
                    Acting on an arbitrarily old speed measurement is worse
                    than not acting, so torque is ramped to zero and the
                    integrator is frozen.
     ems_fallback   inference overran its budget, so the policy output for
                    this outer step does not exist. The energy manager emits
                    the rule-based action for that step. */
#ifndef FALLBACK_ENABLED
#define FALLBACK_ENABLED 1
#endif

/* Fault injection, for the week 7 hardware verification of the fallback path.

   A fallback path that has never been taken is a claim, not a result. Two of
   the three failures cannot be induced from the host -- the outer loop going
   quiet and inference overrunning both happen entirely on the device -- so a
   test build injects them on a fixed schedule and the host checks that the
   counters move by the amount the schedule implies. The third, a stale plant
   state, the host induces itself by not answering.

   0  normal firmware
   1  scheduled faults: after FAULT_EMS_AT_S the energy manager stops
      publishing for FAULT_WINDOW_S; after FAULT_INFER_AT_S inference overruns
      its budget for FAULT_WINDOW_S
   2  hang the control task after FAULT_WDT_AT_S, so the task watchdog fires.
      This one resets the board, which is the point: the evidence is the boot
      reason in the next DIAG frame. */
#ifndef FAULT_INJECT
#define FAULT_INJECT 0
#endif
#define FAULT_EMS_AT_S     20
#define FAULT_INFER_AT_S   40
#define FAULT_WDT_AT_S     20
#define FAULT_WINDOW_S      2

/* Three outer periods. One late setpoint is normal jitter; three in a row is
   an outer loop that has stopped answering. */
#define EMS_STALE_LIMIT_US  (3 * EMS_PERIOD_MS * 1000)
/* Five control periods of no fresh state. At 100 Hz that is 50 ms, about the
   distance a car covers in a metre at urban speed. */
#define STALE_LIMIT_STEPS   5
/* Torque removed per control step while limping: a full-scale command bleeds
   off in 250 ms rather than being dropped, which would be a step input into
   the driveline. */
#define LIMP_RAMP_NM        10.0f
/* A loop is late against its own deadline when the realised period exceeds
   the nominal by more than this. Same 1 ms the G3 jitter criterion uses. */
#define CTRL_LATE_US        1000u

typedef struct {
    float    v_mps, a_mps2, soc_frac, i_batt_a;
    float    v_batt_v, t_ambient_c, grade_rad, p_aux_w;
    float    v_ref_mps, a_ref_mps2;
    uint32_t seq;
    uint32_t host_t_us;
    uint32_t rx_t_us;
} plant_state_t;

/* Bytes of STATE payload: ten floats. The reference speed and its derivative
   are sent by the host because the plant owns the road and the driver; the
   controller owns only how it follows them. */
#define STATE_PAYLOAD_BYTES  40
#define ACT_PAYLOAD_BYTES    16

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
    uint32_t ctrl_late;            /* loops whose own period exceeded nominal by CTRL_LATE_US */
    uint32_t ctrl_fallback_steps;  /* loops that ran the rule manager because the outer loop was stale */
    uint32_t limp_steps;           /* loops that ramped torque down on a stale state */
    uint32_t ems_fallback_steps;   /* outer steps that used the rule action after an inference overrun */
    uint32_t boot_reason;          /* esp_reset_reason() at startup; watchdog resets show up here */
    uint16_t jitter_hist[JITTER_N_BINS];
} diag_stats_t;

void tasks_start(void);
