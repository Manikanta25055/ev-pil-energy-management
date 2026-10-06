#include "control.h"

#include <math.h>

/* Gains and vehicle constants, mirroring evpil.control.sim.DEFAULT_GAINS and
   the identified parameters in data/i3_params.json. They are compiled in
   rather than sent over the link on purpose: a controller that cannot run
   without the host telling it what vehicle it is driving is not a controller
   the paper can claim runs on the device. */
const pid_gains_t k_pid_gains = {
    .kp = 120.0f, .ki = 40.0f, .kd = 2.0f,
    .tau_d_s = 0.05f, .i_limit_nm = 250.0f,
};

const vehicle_t k_vehicle = {
    .mass_kg = 1270.0f,
    .c_rr = 0.019474808971758434f,      /* lumped loss coefficient, not a tyre */
    .cd = 0.22015247123435558f,         /* property; see data/i3_params.json  */
    .frontal_area_m2 = 2.38f,
    .wheel_radius_m = 0.3498f,
    .gear_ratio = 9.665f,
    .drivetrain_eta = 0.95f,
    .rot_mass_factor = 0.17062845280771283f,
    .torque_max_nm = 250.0f,
    .speed_max_radps = 1192.0f,
    .power_max_w = 125000.0f,
};

#define RHO_KGM3  1.2f
#define GRAV      9.81f

static float clampf(float x, float lo, float hi)
{
    return x < lo ? lo : (x > hi ? hi : x);
}

float control_feedforward_nm(const vehicle_t *v, float v_ref_mps,
                             float a_ref_mps2, float grade_rad)
{
    float dir = (v_ref_mps == 0.0f) ? 0.0f : (v_ref_mps > 0.0f ? 1.0f : -1.0f);

    float rolling = v->c_rr * v->mass_kg * GRAV * cosf(grade_rad) * dir;
    float aero = 0.5f * RHO_KGM3 * v->cd * v->frontal_area_m2
                 * v_ref_mps * v_ref_mps * dir;
    float grade = v->mass_kg * GRAV * sinf(grade_rad);
    float inertia = v->mass_kg * (1.0f + v->rot_mass_factor) * a_ref_mps2;
    float f_wheel = rolling + aero + grade + inertia;

    if (f_wheel >= 0.0f)
        return f_wheel * v->wheel_radius_m / (v->gear_ratio * v->drivetrain_eta);
    return f_wheel * v->wheel_radius_m * v->drivetrain_eta / v->gear_ratio;
}

float control_torque_limit_nm(const vehicle_t *v, float omega_radps)
{
    float w = fabsf(omega_radps);
    if (w > v->speed_max_radps) return 0.0f;

    float limit = v->torque_max_nm;
    if (w > 0.0f) {
        float envelope = v->power_max_w / w;
        if (envelope < limit) limit = envelope;
    }
    return limit;
}

float control_pid_step(const pid_gains_t *g, pid_state_t *st,
                       float v_ref_mps, float v_meas_mps,
                       float torque_ff_nm, float torque_limit_nm,
                       float dt_s, bool *saturated)
{
    float e = v_ref_mps - v_meas_mps;

    float d_raw = (dt_s > 0.0f) ? (e - st->e_prev_mps) / dt_s : 0.0f;
    float d_filt;
    if (g->tau_d_s > 0.0f) {
        float alpha = dt_s / (g->tau_d_s + dt_s);
        d_filt = st->d_filt + alpha * (d_raw - st->d_filt);
    } else {
        d_filt = d_raw;
    }

    float integral = st->integral_nm + g->ki * e * dt_s;
    integral = clampf(integral, -g->i_limit_nm, g->i_limit_nm);

    float fb = g->kp * e + integral + g->kd * d_filt;
    float raw = torque_ff_nm + fb;
    float torque = clampf(raw, -torque_limit_nm, torque_limit_nm);
    bool sat = (raw != torque);

    /* Conditional integration: undo this step's accumulation only when the
       output is already against the stop it would be driven further into. */
    if (sat && (raw - torque) * e > 0.0f) integral = st->integral_nm;

    fb = g->kp * e + integral + g->kd * d_filt;
    raw = torque_ff_nm + fb;
    torque = clampf(raw, -torque_limit_nm, torque_limit_nm);

    st->integral_nm = integral;
    st->d_filt = d_filt;
    st->e_prev_mps = e;
    if (saturated) *saturated = sat;
    return torque;
}

/* --- speed filter, mirroring evpil.control.speed_filter ------------------ */

float control_speed_filter_step(speed_filter_t *f, float v_meas_mps,
                                float alpha)
{
    /* The comparison is written so that a NaN alpha also lands here. The
       first sample is taken as it comes: starting from zero would hand the
       loop a step equal to the vehicle's speed. */
    if (!(alpha > 0.0f && alpha < 1.0f) || !f->primed) {
        f->y_mps = v_meas_mps;
    } else {
        f->y_mps += alpha * (v_meas_mps - f->y_mps);
    }
    f->primed = true;
    return f->y_mps;
}

/* --- Kalman speed estimate, mirroring evpil.control.speed_estimators ----- */

void control_jitter_push(jitter_meter_t *m, float v_meas_mps)
{
    m->new_block = false;
    if (m->have_prev) m->diffs[m->n_diffs++] = v_meas_mps - m->prev;
    m->prev = v_meas_mps;
    m->have_prev = true;
    if (m->n_diffs < JITTER_BLOCK_STEPS) return;

    float mean = 0.0f;
    for (int i = 0; i < JITTER_BLOCK_STEPS; i++) mean += m->diffs[i];
    mean /= (float) JITTER_BLOCK_STEPS;
    float var = 0.0f;
    for (int i = 0; i < JITTER_BLOCK_STEPS; i++) {
        float d = m->diffs[i] - mean;
        var += d * d;
    }
    var /= (float) JITTER_BLOCK_STEPS;
    m->n_diffs = 0;

    /* White noise of deviation s on each sample spreads the difference of
       two neighbours by s*sqrt(2). */
    m->recent[m->head] = sqrtf(var) / sqrtf(2.0f);
    m->head = (m->head + 1) % JITTER_BLOCKS;
    if (m->n_recent < JITTER_BLOCKS) m->n_recent++;
    float sum = 0.0f;
    for (int i = 0; i < m->n_recent; i++) sum += m->recent[i];
    m->sigma_mps = sum / (float) m->n_recent;
    m->new_block = true;
}

void control_kalman_init(kalman_speed_t *k, float r_mps)
{
    *k = (kalman_speed_t) {0};
    k->r2 = r_mps * r_mps;
    k->p = k->r2;
}

float control_kalman_step(const vehicle_t *v, kalman_speed_t *k,
                          float q_mps, bool adaptive, float r_floor_mps,
                          float v_meas_mps, float torque_prev_nm,
                          float grade_rad, float dt_s)
{
    if (adaptive) {
        control_jitter_push(&k->meter, v_meas_mps);
        if (k->meter.new_block) {
            float r2 = k->meter.sigma_mps * k->meter.sigma_mps;
            float floor2 = r_floor_mps * r_floor_mps;
            k->r2 = (r2 > floor2) ? r2 : floor2;
        }
    }
    if (!k->primed) {
        k->x_mps = v_meas_mps;
        k->primed = true;
        return k->x_mps;
    }

    float x = k->x_mps;
    float omega = (x / v->wheel_radius_m) * v->gear_ratio;

    /* The motor's envelope, as evpil.plant.motor.clamp_torque has it: above
       the speed limit only driving torque is withheld. */
    float torque;
    if (fabsf(omega) > v->speed_max_radps) {
        torque = (omega >= 0.0f) ? fminf(0.0f, torque_prev_nm)
                                 : fmaxf(0.0f, torque_prev_nm);
    } else {
        float limit = v->torque_max_nm;
        if (fabsf(omega) > 0.0f) {
            float envelope = v->power_max_w / fabsf(omega);
            if (envelope < limit) limit = envelope;
        }
        torque = clampf(torque_prev_nm, -limit, limit);
    }

    float f_wheel = (torque >= 0.0f)
        ? torque * v->gear_ratio * v->drivetrain_eta / v->wheel_radius_m
        : torque * v->gear_ratio / (v->drivetrain_eta * v->wheel_radius_m);
    float dir = (x == 0.0f) ? 0.0f : (x > 0.0f ? 1.0f : -1.0f);
    float f_resist = v->c_rr * v->mass_kg * GRAV * cosf(grade_rad) * dir
                   + 0.5f * RHO_KGM3 * v->cd * v->frontal_area_m2 * x * x * dir
                   + v->mass_kg * GRAV * sinf(grade_rad);
    float a = (f_wheel - f_resist) / (v->mass_kg * (1.0f + v->rot_mass_factor));

    float x_pred = x + a * dt_s;
    float p_pred = k->p + q_mps * q_mps;
    float gain = p_pred / (p_pred + k->r2);
    k->x_mps = x_pred + gain * (v_meas_mps - x_pred);
    k->p = (1.0f - gain) * p_pred;
    return k->x_mps;
}

/* --- rule-based energy manager, mirroring evpil.control.rule_ems --------- */

#define SOC_REGEN_TAPER_START  0.85f
#define SOC_REGEN_OFF          0.94f
#define REGEN_BLEND_MAX        1.00f
#define V_REGEN_FADE_MPS       2.00f
#define P_LIMIT_MAX_W          125000.0f
#define P_LIMIT_MIN_W          40000.0f
#define SOC_DERATE_START       0.20f
#define SOC_DERATE_END         0.07f
#define AUX_DERATE_MAX         0.30f
#define SOC_AUX_SHED_START     0.15f

static float taper(float x, float x_full, float x_zero)
{
    if (x_full == x_zero) return (x >= x_full) ? 1.0f : 0.0f;
    return clampf((x - x_zero) / (x_full - x_zero), 0.0f, 1.0f);
}

ems_action_t control_rule_action(float soc_frac, float v_mps)
{
    ems_action_t a;

    float blend = REGEN_BLEND_MAX;
    blend *= 1.0f - taper(soc_frac, SOC_REGEN_OFF, SOC_REGEN_TAPER_START);
    blend *= taper(v_mps, V_REGEN_FADE_MPS, 0.0f);
    a.regen_blend = clampf(blend, 0.0f, 1.0f);

    a.p_limit_w = P_LIMIT_MIN_W + (P_LIMIT_MAX_W - P_LIMIT_MIN_W)
                  * taper(soc_frac, SOC_DERATE_START, SOC_DERATE_END);

    a.aux_derate = clampf(
        AUX_DERATE_MAX * (1.0f - taper(soc_frac, SOC_AUX_SHED_START,
                                       SOC_DERATE_END)),
        0.0f, 1.0f);
    return a;
}
