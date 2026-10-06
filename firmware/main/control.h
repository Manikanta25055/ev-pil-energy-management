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

/* The rule-based energy manager. Deterministic, memoryless and cheap enough to
   run inside the 10 ms control task, which is what makes it usable as the
   fallback when the 100 ms outer loop has not answered. */
ems_action_t control_rule_action(float soc_frac, float v_mps);
