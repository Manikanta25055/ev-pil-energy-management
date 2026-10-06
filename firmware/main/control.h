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

/* One-state Kalman filter on speed, mirroring
   evpil.control.speed_estimators.KalmanSpeed: predict from the torque
   commanded on the previous step and the road load, correct with the
   measurement. Start it with control_kalman_init. */
typedef struct {
    float          x_mps, p, r2;
    bool           primed;
    jitter_meter_t meter;
} kalman_speed_t;

void control_kalman_init(kalman_speed_t *k, float r_mps);

/* `adaptive` replaces the assumed measurement noise, once per block, with the
   level the jitter meter reads, never below `r_floor_mps`. */
float control_kalman_step(const vehicle_t *v, kalman_speed_t *k,
                          float q_mps, bool adaptive, float r_floor_mps,
                          float v_meas_mps, float torque_prev_nm,
                          float grade_rad, float dt_s);

/* The rule-based energy manager. Deterministic, memoryless and cheap enough to
   run inside the 10 ms control task, which is what makes it usable as the
   fallback when the 100 ms outer loop has not answered. */
ems_action_t control_rule_action(float soc_frac, float v_mps);
