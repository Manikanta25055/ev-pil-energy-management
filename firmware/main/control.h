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
} fault_kalman_t;

void control_fault_kalman_init(fault_kalman_t *f);

float control_fault_kalman_step(const vehicle_t *v, fault_kalman_t *f,
                                float q_mps, float q_d_mps2, float r_floor_mps,
                                float tau_s, float v_meas_mps, float a_meas_mps2,
                                float torque_prev_nm, float grade_rad,
                                float dt_s);

/* The rule-based energy manager. Deterministic, memoryless and cheap enough to
   run inside the 10 ms control task, which is what makes it usable as the
   fallback when the 100 ms outer loop has not answered. */
ems_action_t control_rule_action(float soc_frac, float v_mps);
