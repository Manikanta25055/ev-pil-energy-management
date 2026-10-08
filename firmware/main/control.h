#pragma once
#include <stdbool.h>
#include <stdint.h>

/* On-device mirror of evpil.control.pid and evpil.control.rule_ems.

   The host modules are the reference implementation and this is the version
   that gets measured. Keeping them in step is the same discipline protocol.c
   follows against protocol.py: a controller that quietly differs from the one
   the paper's simulation results came from would invalidate every PIL number
   in the results table. tests/control/test_c_parity.py drives both with the
   same inputs and requires them to agree. */

typedef struct {
    float kp, ki, kd;
    float tau_d_s;
    float i_limit_nm;
} pid_gains_t;

typedef struct {
    float integral_nm;
    float d_filt;
    float e_prev_mps;
} pid_state_t;

typedef struct {
    float mass_kg, c_rr, cd, frontal_area_m2;
    float wheel_radius_m, gear_ratio, drivetrain_eta, rot_mass_factor;
    float torque_max_nm, speed_max_radps, power_max_w;
} vehicle_t;

/* Low-pass on measured speed ahead of the speed loop, mirroring
   evpil.control.speed_filter. Zero-initialise it. */
typedef struct {
    float y_mps;
    bool  primed;
} speed_filter_t;

typedef struct {
    float regen_blend;
    float p_limit_w;
    float aux_derate;
} ems_action_t;

extern const pid_gains_t k_pid_gains;
extern const vehicle_t   k_vehicle;

float control_feedforward_nm(const vehicle_t *v, float v_ref_mps,
                             float a_ref_mps2, float grade_rad);

float control_torque_limit_nm(const vehicle_t *v, float omega_radps);

/* Returns the commanded torque and advances `st` in place. `saturated` may be
   NULL. */
float control_pid_step(const pid_gains_t *g, pid_state_t *st,
                       float v_ref_mps, float v_meas_mps,
                       float torque_ff_nm, float torque_limit_nm,
                       float dt_s, bool *saturated);

/* Returns the speed to control on and advances `f` in place. `alpha` is in
   (0, 1]; 1 is no filter and returns the measurement exactly. A value outside
   that range is treated as 1, because the control task has no one to raise an
   error to and an unfiltered loop is the behaviour that was measured. */
float control_speed_filter_step(speed_filter_t *f, float v_meas_mps,
                                float alpha);

/* Noise level on the speed channel, from the spread of the 10 ms differences
   averaged over the last eight 100 ms blocks. Mirrors
   evpil.control.speed_estimators.JitterMeter. Zero-initialise it. */
#define JITTER_BLOCK_STEPS 10
#define JITTER_BLOCKS      8
typedef struct {
    float diffs[JITTER_BLOCK_STEPS];
    int   n_diffs;
    float prev;
    bool  have_prev;
    float recent[JITTER_BLOCKS];
    int   n_recent, head;
    float sigma_mps;
    bool  new_block;            /* true for the one call that closed a block */
} jitter_meter_t;

void control_jitter_push(jitter_meter_t *m, float v_meas_mps);

/* Kalman filter on speed, mirroring evpil.control.speed_estimators.KalmanSpeed:
   predict from the torque commanded on the step that produced this
   measurement and the road load, correct with the measurement.

   With `q_d_mps2` zero it has one state, the speed (arms B3 and B3a). With it
   positive it carries a second: an acceleration the model does not know about
   -- a car heavier than the model, a headwind -- learned alongside the speed
   (arm B5). Start it with control_kalman_init. */
typedef struct {
    float          x_mps, p, r2;
    float          d_mps2, p_vd, p_dd;      /* second state and its covariance */
    float          pred_vd, pred_dd;        /* carried from predict to correct */
    bool           primed;
    jitter_meter_t meter;
} kalman_speed_t;

void control_kalman_init(kalman_speed_t *k, float r_mps);

/* `adaptive` replaces the assumed measurement noise, once per block, with the
   level the jitter meter reads, never below `r_floor_mps`. */
float control_kalman_step(const vehicle_t *v, kalman_speed_t *k,
                          float q_mps, float q_d_mps2, bool adaptive,
                          float r_floor_mps, float v_meas_mps,
                          float torque_prev_nm, float grade_rad, float dt_s);

/* One step on the model alone, for a control period in which no new
   measurement arrived. */
float control_kalman_coast(const vehicle_t *v, kalman_speed_t *k,
                           float q_mps, float q_d_mps2,
                           float torque_prev_nm, float grade_rad, float dt_s);

/* Arm B6, mirroring evpil.control.speed_estimators.KinematicFaultKalman: the
   two-state estimate plus a detector for a speed sensor that is stuck, has
   dropped out, or has picked up an offset. The detector compares the reading
   with a speed dead-reckoned from measured acceleration, so it does not
   depend on the vehicle model and a heavier car does not trip it. While the
   flag is up the estimate is the dead-reckoned speed. Zero-initialise, then
   control_fault_kalman_init. */
#define FAULT_WINDOW        20      /* gaps in the mean test: 200 ms */
#define FAULT_T_LIMIT       8.0f    /* mean over its own standard error */
#define FAULT_GROSS_MPS     1.0f    /* a jump no vehicle makes in 10 ms */
#define FAULT_GROSS_COUNT   2
#define FAULT_FROZEN_COUNT  10      /* identical samples in a row */
#define FAULT_CLEAR_COUNT   50      /* quiet samples before the flag drops */
#define FAULT_CLEAR_BAND_MPS 0.25f

typedef struct {
    float x_mps, p, d_mps2, p_vd, p_dd;
    bool  valid;
} kalman_snapshot_t;

typedef struct {
    kalman_speed_t    k;
    float             v_dr;                     /* dead-reckoned speed */
    float             gap[FAULT_WINDOW];        /* oldest first */
    float             pull[FAULT_WINDOW];       /* what each sample moved v_dr by */
    int               n_gap;
    int               gross, same, quiet;
    float             last;
    kalman_snapshot_t good, good_next;
    bool              flagged;
    uint32_t          alarms;                   /* times the flag went up */
    uint32_t          flag_steps;               /* steps spent flagged */
    /* About the most recent time the flag went up, for telling a false alarm
       apart from a real one after the fact: which test raised it (1 gross,
       2 frozen, 3 mean), the reading at that moment, and the mean gap of
       the window. */
    uint32_t          alarm_test;
    float             alarm_v_mps;
    float             alarm_gap_mps;
} fault_kalman_t;

void control_fault_kalman_init(fault_kalman_t *f);

float control_fault_kalman_step(const vehicle_t *v, fault_kalman_t *f,
                                float q_mps, float q_d_mps2, float r_floor_mps,
                                float tau_s, float v_meas_mps, float a_meas_mps2,
                                float torque_prev_nm, float grade_rad,
                                float dt_s);

/* Arm B7, mirroring evpil.control.speed_estimators.BiasAwareFaultKalman: B6
   made to live with an acceleration channel that carries an offset and a
   slow wander. The dead reckoning estimates the channel's offset and
   subtracts it; a step test compares the mean gap of the last 300 ms with
   the 300 ms before, so the slow error cancels; the mean test's threshold
   carries the dead reckoning's own error. Settings are the ones chosen in
   docs/week13-b7-tuning.json. Zero-initialise, then control_b7_init.

   Four fields let a supervisor steer it, each without effect at its default:
   vigilance (1), hold_release, release_now, model_weight (0: the fallback
   speed is the dead reckoning; 1: the model's prediction). */
#define B7_WINDOW           20
#define B7_T_LIMIT          8.0f
#define B7_GROSS_MPS        1.0f
#define B7_GROSS_COUNT      2
#define B7_FROZEN_COUNT     10
#define B7_CLEAR_COUNT      50
#define B7_CLEAR_BAND_MPS   0.25f
#define B7_TAU_S            2.0f
#define B7_TAU_B_S          2.0f
#define B7_STEP_HALF        30
#define B7_T_STEP           6.0f
#define B7_STEP_SLOPE_MPS2  0.2f
#define B7_DR_SIGMA_MPS     0.15f
#define B7_BAND_GROWTH_MPS2 0.2f
#define B7_KEEP             (2 * B7_STEP_HALF)

typedef struct {
    kalman_speed_t    k;
    float             v_dr;                 /* dead-reckoned speed */
    float             b_mps2;               /* acceleration offset estimate */
    float             gap[B7_KEEP];         /* oldest first */
    float             before_v[B7_KEEP];    /* v_dr and offset before each */
    float             before_b[B7_KEEP];
    float             adt[B7_KEEP];         /* acceleration times dt */
    int               n_gap;
    int               gross, same, quiet;
    float             last;
    float             flag_s;
    kalman_snapshot_t good, good_next;
    bool              flagged;
    uint32_t          alarms, clears, flag_steps;
    uint32_t          alarm_test;           /* 1 gross 2 frozen 3 mean 4 step */
    float             last_gap, last_nu;
    float             vigilance;
    bool              hold_release, release_now;
    float             model_weight;
} b7_t;

void control_b7_init(b7_t *f);

float control_b7_step(const vehicle_t *v, b7_t *f, float q_mps,
                      float q_d_mps2, float r_floor_mps, float v_meas_mps,
                      float a_meas_mps2, float torque_prev_nm,
                      float grade_rad, float dt_s);

/* B7 with the rule monitor around it on the chip (architecture A2),
   mirroring evpil.control.supervisor.Supervisor with a RuleMonitor on a
   channel with no delay and the default Policy. Every 100 ms the block just
   finished is summarised, the monitor votes on whether the sensor is faulty
   and whether the acceleration channel is degraded, and on the next step the
   answer may hold or release B7's flag, switch its fallback speed to the
   model, or tighten its tests. */
#define SUP_BLOCK_STEPS   10
#define SUP_MEMORY        3
#define SUP_P_HOLD        0.6f
#define SUP_P_RELEASE     0.2f
#define SUP_P_ACCEL       0.5f
#define SUP_P_VIGILANT    0.6f
#define SUP_VIGILANCE     0.6f
#define SUP_EXPIRY_S      1.5f
#define SUP_MAX_HOLD_S    10.0f
#define SUP_MIN_FLAG_S    0.5f
/* The two times above, in 10 ms steps, as the Python side's float64 running
   sums cross them: 0.01 added 50 times reaches 0.5, and added 1000 times is
   still just under 10. Counting steps here keeps float32 rounding from
   moving a release or the end of a hold by a step.
   tests/control/test_monitor_c_parity.py derives both numbers again. */
#define SUP_MIN_FLAG_STEPS 50
#define SUP_MAX_HOLD_STEPS 1001
#define MON_OFF_MPS       0.15f
#define MON_SPLIT_MPS     0.15f
#define MON_OFFSET_MPS2   0.1f

typedef struct {
    b7_t     b;
    float    gap[SUP_BLOCK_STEPS], nu[SUP_BLOCK_STEPS];
    int      n, same;
    float    last;
    bool     have_last;
    bool     mon_fault[SUP_MEMORY], mon_accel[SUP_MEMORY];
    int      mon_n;
    /* The answer in flight (sent at the end of a block, read on the next
       step) and the newest one accepted. */
    bool     pend_valid, have;
    uint32_t pend_epoch, epoch, have_epoch;
    float    pend_p_fault, pend_p_accel, p_fault, p_accel;
    uint32_t pend_block, have_block;
    bool     was_flagged;
    uint32_t flag_n, hold_n;        /* steps flagged, steps held */
    uint32_t k, block;
    uint32_t holds, releases, fallbacks, vigilants;     /* steps, not events */
} supervisor_t;

void control_supervisor_init(supervisor_t *s);

float control_supervisor_step(const vehicle_t *v, supervisor_t *s,
                              float q_mps, float q_d_mps2, float r_floor_mps,
                              float v_meas_mps, float a_meas_mps2,
                              float torque_prev_nm, float grade_rad,
                              float dt_s);

/* The rule-based energy manager. Deterministic, memoryless and cheap enough to
   run inside the 10 ms control task, which is what makes it usable as the
   fallback when the 100 ms outer loop has not answered. */
ems_action_t control_rule_action(float soc_frac, float v_mps);
