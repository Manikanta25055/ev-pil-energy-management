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

/* Where the model says the speed is now, and how sure it is. The covariance
   of [speed, unknown acceleration] is carried forward one step; with the
   second state off every extra term is exactly zero. */
static void kalman_predict(const vehicle_t *v, kalman_speed_t *k, float q_mps,
                           float q_d_mps2, float torque_prev_nm,
                           float grade_rad, float dt_s,
                           float *x_pred, float *p_pred)
{
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

    k->pred_vd = k->p_vd + dt_s * k->p_dd;
    k->pred_dd = k->p_dd + q_d_mps2 * q_d_mps2;
    *p_pred = k->p + 2.0f * dt_s * k->p_vd + dt_s * dt_s * k->p_dd
              + q_mps * q_mps;
    *x_pred = x + (a + k->d_mps2) * dt_s;
}

/* Take the prediction as the estimate, with no measurement. */
static float kalman_take_prediction(kalman_speed_t *k, float x_pred,
                                    float p_pred)
{
    k->x_mps = x_pred;
    k->p = p_pred;
    k->p_vd = k->pred_vd;
    k->p_dd = k->pred_dd;
    return k->x_mps;
}

static float kalman_correct(kalman_speed_t *k, float q_d_mps2, float x_pred,
                            float p_pred, float v_meas_mps)
{
    float nu = v_meas_mps - x_pred;
    float s = p_pred + k->r2;
    float gain = p_pred / s;
    k->x_mps = x_pred + gain * nu;
    k->p = (1.0f - gain) * p_pred;
    if (q_d_mps2 > 0.0f) {
        float gain_d = k->pred_vd / s;
        k->d_mps2 += gain_d * nu;
        k->p_vd = (1.0f - gain) * k->pred_vd;
        k->p_dd = k->pred_dd - gain_d * k->pred_vd;
    }
    return k->x_mps;
}

static void kalman_learn_noise(kalman_speed_t *k, float v_meas_mps,
                               float r_floor_mps)
{
    control_jitter_push(&k->meter, v_meas_mps);
    if (k->meter.new_block) {
        float r2 = k->meter.sigma_mps * k->meter.sigma_mps;
        float floor2 = r_floor_mps * r_floor_mps;
        k->r2 = (r2 > floor2) ? r2 : floor2;
    }
}

float control_kalman_step(const vehicle_t *v, kalman_speed_t *k,
                          float q_mps, float q_d_mps2, bool adaptive,
                          float r_floor_mps, float v_meas_mps,
                          float torque_prev_nm, float grade_rad, float dt_s)
{
    if (adaptive) kalman_learn_noise(k, v_meas_mps, r_floor_mps);
    if (!k->primed) {
        k->x_mps = v_meas_mps;
        k->primed = true;
        return k->x_mps;
    }
    float x_pred, p_pred;
    kalman_predict(v, k, q_mps, q_d_mps2, torque_prev_nm, grade_rad, dt_s,
                   &x_pred, &p_pred);
    return kalman_correct(k, q_d_mps2, x_pred, p_pred, v_meas_mps);
}

float control_kalman_coast(const vehicle_t *v, kalman_speed_t *k,
                           float q_mps, float q_d_mps2,
                           float torque_prev_nm, float grade_rad, float dt_s)
{
    if (!k->primed) return k->x_mps;
    float x_pred, p_pred;
    kalman_predict(v, k, q_mps, q_d_mps2, torque_prev_nm, grade_rad, dt_s,
                   &x_pred, &p_pred);
    return kalman_take_prediction(k, x_pred, p_pred);
}

/* --- B6, mirroring evpil.control.speed_estimators.KinematicFaultKalman ---- */

void control_fault_kalman_init(fault_kalman_t *f)
{
    *f = (fault_kalman_t) {0};
    control_kalman_init(&f->k, 0.02f);
}

static kalman_snapshot_t kalman_snapshot(const kalman_speed_t *k)
{
    return (kalman_snapshot_t) {k->x_mps, k->p, k->d_mps2, k->p_vd, k->p_dd,
                                true};
}

float control_fault_kalman_step(const vehicle_t *v, fault_kalman_t *f,
                                float q_mps, float q_d_mps2, float r_floor_mps,
                                float tau_s, float v_meas_mps, float a_meas_mps2,
                                float torque_prev_nm, float grade_rad,
                                float dt_s)
{
    kalman_speed_t *k = &f->k;
    if (!k->primed) {
        k->x_mps = v_meas_mps;
        k->primed = true;
        f->v_dr = v_meas_mps;
        f->last = v_meas_mps;
        return k->x_mps;
    }

    /* Dead reckoning, before this sample is allowed to pull on it. */
    float v_dr = f->v_dr + a_meas_mps2 * dt_s;
    float gap = v_meas_mps - v_dr;
    float scale = sqrtf(k->r2);
    float gross_limit = fmaxf(FAULT_GROSS_MPS, 8.0f * scale);

    f->gross = (fabsf(gap) > gross_limit) ? f->gross + 1 : 0;
    f->same = (v_meas_mps == f->last) ? f->same + 1 : 0;
    f->last = v_meas_mps;
    if (f->n_gap == FAULT_WINDOW) {
        for (int i = 1; i < FAULT_WINDOW; i++) {
            f->gap[i - 1] = f->gap[i];
            f->pull[i - 1] = f->pull[i];
        }
        f->n_gap--;
    }
    f->pull[f->n_gap] = 0.0f;       /* zero unless this sample is accepted */
    f->gap[f->n_gap++] = gap;

    bool fault_now = f->gross >= FAULT_GROSS_COUNT;
    if (f->same >= FAULT_FROZEN_COUNT && k->meter.sigma_mps > 1e-4f)
        fault_now = true;
    if (f->n_gap == FAULT_WINDOW) {
        float m = 0.0f;
        for (int i = 0; i < FAULT_WINDOW; i++) m += f->gap[i];
        m /= (float) FAULT_WINDOW;
        float var = 0.0f;
        for (int i = 0; i < FAULT_WINDOW; i++) {
            float e = f->gap[i] - m;
            var += e * e;
        }
        var /= (float) (FAULT_WINDOW - 1);
        /* The scatter is not allowed below what the filter itself expects,
           or a noiseless stretch would make any offset look significant. */
        float se = sqrtf(fmaxf(var, k->r2) / (float) FAULT_WINDOW);
        if (fabsf(m) > FAULT_T_LIMIT * se) fault_now = true;
    }

    if (!f->flagged && fault_now) {
        f->flagged = true;
        f->quiet = 0;
        f->alarms++;
        /* Undo the pull the faulty samples had on the dead-reckoned speed
           while the test was making up its mind. A sample that was refused
           pulled nothing and has nothing to undo. */
        float pulled = 0.0f;
        for (int i = 0; i < f->n_gap - 1; i++) pulled += f->pull[i];
        v_dr -= pulled;
    } else if (f->flagged) {
        float band = fmaxf(FAULT_CLEAR_BAND_MPS, 4.0f * scale);
        bool quiet = fabsf(gap) < band && f->same < FAULT_FROZEN_COUNT
                     && f->gross == 0;
        f->quiet = quiet ? f->quiet + 1 : 0;
        if (f->quiet >= FAULT_CLEAR_COUNT) {
            f->flagged = false;
            f->n_gap = 0;
            /* The sensor has agreed with the dead-reckoned speed, within the
               band, for half a second: take its reading as the new starting
               point for both. Dead reckoning drifts while a fault lasts, and
               carrying that drift past the fault makes the mean test raise
               the flag again on a healthy sensor. The filter keeps the
               unknown acceleration it held before the fault. */
            v_dr = v_meas_mps;
            if (f->good.valid) {
                k->x_mps = f->good.x_mps;   k->p = f->good.p;
                k->d_mps2 = f->good.d_mps2; k->p_vd = f->good.p_vd;
                k->p_dd = f->good.p_dd;
            }
            k->x_mps = v_dr;
            k->p = k->r2;
        }
    }

    if (f->flagged) {
        f->flag_steps++;
        f->v_dr = v_dr;
        return v_dr;
    }

    float x_pred, p_pred;
    if (fabsf(gap) > gross_limit) {
        /* A single wild sample is not blended in even before the flag goes
           up, and is not allowed to pull on the dead-reckoned speed. */
        f->v_dr = v_dr;
        kalman_predict(v, k, q_mps, q_d_mps2, torque_prev_nm, grade_rad, dt_s,
                       &x_pred, &p_pred);
        return kalman_take_prediction(k, x_pred, p_pred);
    }

    /* The window is empty on the step the flag has just dropped. */
    if (f->n_gap > 0) f->pull[f->n_gap - 1] = (dt_s / tau_s) * gap;
    f->v_dr = v_dr + (dt_s / tau_s) * gap;
    /* The noise level is only learned from samples believed to be good. */
    control_jitter_push(&k->meter, v_meas_mps);
    if (k->meter.new_block) {
        float r2 = k->meter.sigma_mps * k->meter.sigma_mps;
        float floor2 = r_floor_mps * r_floor_mps;
        k->r2 = (r2 > floor2) ? r2 : floor2;
        /* A state believed clean, to come back to after a fault. Taken once
           a block, so it is at least a block old when a flag goes up. */
        f->good = f->good_next;
        f->good_next = kalman_snapshot(k);
    }
    kalman_predict(v, k, q_mps, q_d_mps2, torque_prev_nm, grade_rad, dt_s,
                   &x_pred, &p_pred);
    return kalman_correct(k, q_d_mps2, x_pred, p_pred, v_meas_mps);
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
