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

    /* Which test fires, first match wins: 1 gross, 2 frozen, 3 mean. */
    uint32_t test = 0;
    float mean_now = gap;
    if (f->gross >= FAULT_GROSS_COUNT) {
        test = 1;
    } else if (f->same >= FAULT_FROZEN_COUNT && k->meter.sigma_mps > 1e-4f) {
        test = 2;
    } else if (f->n_gap == FAULT_WINDOW) {
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
        mean_now = m;
        if (fabsf(m) > FAULT_T_LIMIT * se) test = 3;
    }
    bool fault_now = (test != 0);

    if (!f->flagged && fault_now) {
        f->flagged = true;
        f->quiet = 0;
        f->alarms++;
        f->alarm_test = test;
        f->alarm_v_mps = v_meas_mps;
        f->alarm_gap_mps = mean_now;
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
            /* The sensor has agreed with the dead-reckoned speed, within the
               band, for half a second: move the dead-reckoned speed onto it.
               Dead reckoning drifts while a fault lasts, and carrying that
               drift past the fault makes the mean test raise the flag again
               on a healthy sensor. The move is the mean gap over the window,
               not this one sample's: at ten times the noise floor a single
               reading is 0.2 m/s out. The filter keeps the unknown
               acceleration it held before the fault. */
            float mean_gap = 0.0f;
            for (int i = 0; i < f->n_gap; i++) mean_gap += f->gap[i];
            v_dr += mean_gap / (float) f->n_gap;
            f->n_gap = 0;
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

void control_b7_init(b7_t *f)
{
    control_kalman_init(&f->k, 0.02f);
    f->vigilance = 1.0f;
}

static void kalman_restore(kalman_speed_t *k, const kalman_snapshot_t *g)
{
    k->x_mps = g->x_mps;   k->p = g->p;
    k->d_mps2 = g->d_mps2; k->p_vd = g->p_vd;
    k->p_dd = g->p_dd;
}

/* Which of B7's tests fires, first match wins: 1 gross, 2 frozen, 4 step,
   3 mean. */
static uint32_t b7_test(const b7_t *f, float scale, float dt_s)
{
    const kalman_speed_t *k = &f->k;
    if (f->gross >= B7_GROSS_COUNT) return 1;
    if (f->same >= B7_FROZEN_COUNT && k->meter.sigma_mps > 1e-4f) return 2;
    float r2 = scale * scale;
    const int h = B7_STEP_HALF;
    if (f->n_gap >= 2 * h) {
        const float *old = &f->gap[f->n_gap - 2 * h];
        const float *new = &f->gap[f->n_gap - h];
        float m_new = 0.0f, m_old = 0.0f;
        for (int i = 0; i < h; i++) { m_new += new[i]; m_old += old[i]; }
        m_new /= (float) h;
        m_old /= (float) h;
        float var = 0.0f;
        for (int i = 0; i < h; i++) {
            float e = new[i] - m_new;
            var += e * e;
        }
        for (int i = 0; i < h; i++) {
            float e = old[i] - m_old;
            var += e * e;
        }
        var /= (float) (2 * h - 2);
        float limit = B7_T_STEP * sqrtf(2.0f * fmaxf(var, r2) / (float) h)
                      + B7_STEP_SLOPE_MPS2 * (float) h * dt_s;
        if (fabsf(m_new - m_old) > f->vigilance * limit) return 4;
    }
    if (f->n_gap >= B7_WINDOW) {
        const float *win = &f->gap[f->n_gap - B7_WINDOW];
        float m = 0.0f;
        for (int i = 0; i < B7_WINDOW; i++) m += win[i];
        m /= (float) B7_WINDOW;
        float var = 0.0f;
        for (int i = 0; i < B7_WINDOW; i++) {
            float e = win[i] - m;
            var += e * e;
        }
        var /= (float) (B7_WINDOW - 1);
        float limit = B7_T_LIMIT * sqrtf(fmaxf(var, r2) / (float) B7_WINDOW
                                         + B7_DR_SIGMA_MPS * B7_DR_SIGMA_MPS);
        if (fabsf(m) > f->vigilance * limit) return 3;
    }
    return 0;
}

static float b7_fallback(const b7_t *f, float v_dr)
{
    float w = clampf(f->model_weight, 0.0f, 1.0f);
    if (w >= 1.0f) return f->k.x_mps;
    if (w <= 0.0f) return v_dr;
    return w * f->k.x_mps + (1.0f - w) * v_dr;
}

float control_b7_step(const vehicle_t *v, b7_t *f, float q_mps,
                      float q_d_mps2, float r_floor_mps, float v_meas_mps,
                      float a_meas_mps2, float torque_prev_nm,
                      float grade_rad, float dt_s)
{
    kalman_speed_t *k = &f->k;
    if (!k->primed) {
        k->x_mps = v_meas_mps;
        k->primed = true;
        f->v_dr = v_meas_mps;
        f->last = v_meas_mps;
        return k->x_mps;
    }

    float v_dr = f->v_dr + (a_meas_mps2 - f->b_mps2) * dt_s;
    float gap = v_meas_mps - v_dr;
    f->last_gap = gap;
    float scale = sqrtf(k->r2);
    float gross_limit = fmaxf(B7_GROSS_MPS, 8.0f * scale);

    f->gross = (fabsf(gap) > gross_limit) ? f->gross + 1 : 0;
    f->same = (v_meas_mps == f->last) ? f->same + 1 : 0;
    f->last = v_meas_mps;
    if (f->n_gap == B7_KEEP) {
        for (int i = 1; i < B7_KEEP; i++) {
            f->gap[i - 1] = f->gap[i];
            f->before_v[i - 1] = f->before_v[i];
            f->before_b[i - 1] = f->before_b[i];
            f->adt[i - 1] = f->adt[i];
        }
        f->n_gap--;
    }
    f->gap[f->n_gap] = gap;
    f->before_v[f->n_gap] = f->v_dr;
    f->before_b[f->n_gap] = f->b_mps2;
    f->adt[f->n_gap] = a_meas_mps2 * dt_s;
    f->n_gap++;

    uint32_t test = f->flagged ? 0 : b7_test(f, scale, dt_s);
    float x_pred, p_pred;
    if (test) {
        f->flagged = true;
        f->quiet = 0;
        f->flag_s = 0.0f;
        f->alarms++;
        f->alarm_test = test;
        /* Back to the reference as it stood before the window, brought
           forward on acceleration alone: none of the samples the fault may
           have been in is left in it. */
        float sum_adt = 0.0f;
        for (int i = 0; i < f->n_gap; i++) sum_adt += f->adt[i];
        f->b_mps2 = f->before_b[0];
        v_dr = f->before_v[0] + sum_adt
               - f->before_b[0] * dt_s * (float) f->n_gap;
        /* The model's prediction starts from the same place, on the filter
           state from before the fault could have reached it. */
        if (f->good.valid) kalman_restore(k, &f->good);
        k->x_mps = v_dr;
    } else if (f->flagged) {
        f->flag_s += dt_s;
        kalman_predict(v, k, q_mps, q_d_mps2, torque_prev_nm, grade_rad, dt_s,
                       &x_pred, &p_pred);
        kalman_take_prediction(k, x_pred, p_pred);
        f->last_nu = v_meas_mps - k->x_mps;
        float band = fmaxf(B7_CLEAR_BAND_MPS, 4.0f * scale)
                     + B7_BAND_GROWTH_MPS2 * f->flag_s;
        float w = clampf(f->model_weight, 0.0f, 1.0f);
        float off = (w >= 1.0f) ? f->last_nu : (w <= 0.0f) ? gap
                    : w * f->last_nu + (1.0f - w) * gap;
        bool quiet = fabsf(off) < band && f->same < B7_FROZEN_COUNT
                     && (f->gross == 0 || w > 0.0f);
        f->quiet = quiet ? f->quiet + 1 : 0;
        if (f->hold_release && f->quiet > B7_CLEAR_COUNT - 1)
            f->quiet = B7_CLEAR_COUNT - 1;
        if (f->release_now && f->same < B7_FROZEN_COUNT)
            f->quiet = B7_CLEAR_COUNT;
        f->release_now = false;
        if (f->quiet >= B7_CLEAR_COUNT) {
            f->flagged = false;
            f->clears++;
            int n = (f->n_gap < B7_WINDOW) ? f->n_gap : B7_WINDOW;
            float mean_gap = 0.0f;
            for (int i = f->n_gap - n; i < f->n_gap; i++) mean_gap += f->gap[i];
            v_dr += mean_gap / (float) n;
            f->n_gap = 0;
            if (f->good.valid) kalman_restore(k, &f->good);
            k->x_mps = v_dr;
            k->p = k->r2;
        }
    }

    if (f->flagged) {
        f->flag_steps++;
        f->v_dr = v_dr;
        return b7_fallback(f, v_dr);
    }

    if (fabsf(gap) > gross_limit) {
        f->v_dr = v_dr;
        kalman_predict(v, k, q_mps, q_d_mps2, torque_prev_nm, grade_rad, dt_s,
                       &x_pred, &p_pred);
        return kalman_take_prediction(k, x_pred, p_pred);
    }

    float pull = (dt_s / B7_TAU_S) * gap;
    f->v_dr = v_dr + pull;
    /* The dead reckoning running ahead of the reading means the channel
       reads high: the offset estimate goes up. */
    f->b_mps2 -= pull / B7_TAU_B_S;
    control_jitter_push(&k->meter, v_meas_mps);
    if (k->meter.new_block) {
        float r2 = k->meter.sigma_mps * k->meter.sigma_mps;
        float floor2 = r_floor_mps * r_floor_mps;
        k->r2 = (r2 > floor2) ? r2 : floor2;
        f->good = f->good_next;
        f->good_next = kalman_snapshot(k);
    }
    kalman_predict(v, k, q_mps, q_d_mps2, torque_prev_nm, grade_rad, dt_s,
                   &x_pred, &p_pred);
    f->last_nu = v_meas_mps - x_pred;
    return kalman_correct(k, q_d_mps2, x_pred, p_pred, v_meas_mps);
}

void control_supervisor_init(supervisor_t *s)
{
    control_b7_init(&s->b);
}

/* The monitor's vote on the block just finished, pushed into its three-block
   memory. Two references, one vote: a sensor fault moves the reading away
   from the dead reckoning and from the model by the same amount; a degraded
   acceleration channel moves the dead reckoning and leaves the model. */
static void supervisor_review(supervisor_t *s)
{
    const b7_t *b = &s->b;
    float gm = 0.0f, nm = 0.0f;
    for (int i = 0; i < SUP_BLOCK_STEPS; i++) { gm += s->gap[i]; nm += s->nu[i]; }
    gm /= (float) SUP_BLOCK_STEPS;
    nm /= (float) SUP_BLOCK_STEPS;
    float split = clampf(gm - nm, -5.0f, 5.0f);
    gm = clampf(gm, -5.0f, 5.0f);
    nm = clampf(nm, -5.0f, 5.0f);
    float noise = fmaxf(sqrtf(b->k.r2), 1e-3f);
    float frozen = (float) s->same / (float) SUP_BLOCK_STEPS;
    float lim = fmaxf(MON_OFF_MPS, 2.0f * noise);
    bool fault = frozen > 0.5f;
    if (b->flagged && fabsf(gm) > lim && fabsf(nm) > lim && gm * nm > 0.0f)
        fault = true;
    float b_clip = clampf(b->b_mps2 * 5.0f, -5.0f, 5.0f) / 5.0f;
    bool accel = fabsf(split) > fmaxf(MON_SPLIT_MPS, 2.0f * noise)
                 || fabsf(b_clip) > MON_OFFSET_MPS2;

    if (s->mon_n == SUP_MEMORY) {
        for (int i = 1; i < SUP_MEMORY; i++) {
            s->mon_fault[i - 1] = s->mon_fault[i];
            s->mon_accel[i - 1] = s->mon_accel[i];
        }
        s->mon_n--;
    }
    s->mon_fault[s->mon_n] = fault;
    s->mon_accel[s->mon_n] = accel;
    s->mon_n++;
    int nf = 0, na = 0;
    for (int i = 0; i < s->mon_n; i++) { nf += s->mon_fault[i]; na += s->mon_accel[i]; }
    s->pend_p_fault = (float) nf / (float) s->mon_n;
    s->pend_p_accel = (float) na / (float) s->mon_n;
    s->pend_epoch = s->epoch;
    s->pend_block = s->block;
    s->pend_valid = true;
}

float control_supervisor_step(const vehicle_t *v, supervisor_t *s,
                              float q_mps, float q_d_mps2, float r_floor_mps,
                              float v_meas_mps, float a_meas_mps2,
                              float torque_prev_nm, float grade_rad,
                              float dt_s)
{
    b7_t *b = &s->b;
    float t_s = (float) s->k * dt_s;

    /* The answer sent at the end of the last block arrives now. One about a
       flag that has since changed is dropped. */
    if (s->pend_valid) {
        s->pend_valid = false;
        if (s->pend_epoch == s->epoch) {
            s->have = true;
            s->have_epoch = s->pend_epoch;
            s->have_block = s->pend_block;
            s->p_fault = s->pend_p_fault;
            s->p_accel = s->pend_p_accel;
        }
    }

    /* Apply: only an answer that is fresh and about the present flag. */
    float asked_s = (float) (s->have_block + 1) * (float) SUP_BLOCK_STEPS * dt_s;
    bool usable = s->have && s->have_epoch == s->epoch
                  && (t_s - asked_s) <= SUP_EXPIRY_S;
    b->hold_release = false;
    b->vigilance = 1.0f;
    if (!usable) {
        b->model_weight = 0.0f;
    } else if (b->flagged) {
        float want = (s->p_accel > SUP_P_ACCEL) ? 1.0f : 0.0f;
        if (want != b->model_weight) s->fallbacks++;
        b->model_weight = want;
        if (s->p_fault > SUP_P_HOLD && s->hold_n < SUP_MAX_HOLD_STEPS) {
            b->hold_release = true;
            s->holds++;
        } else if (s->p_fault < SUP_P_RELEASE
                   && s->flag_n >= SUP_MIN_FLAG_STEPS) {
            b->release_now = true;
            s->releases++;
        }
    } else if (s->p_fault > SUP_P_VIGILANT) {
        b->vigilance = SUP_VIGILANCE;
        s->vigilants++;
    }

    float out = control_b7_step(v, b, q_mps, q_d_mps2, r_floor_mps, v_meas_mps,
                                a_meas_mps2, torque_prev_nm, grade_rad, dt_s);

    if (b->flagged != s->was_flagged) {
        s->epoch++;
        s->was_flagged = b->flagged;
        s->flag_n = 0;
        s->hold_n = 0;
        s->have = false;
        if (!b->flagged) b->model_weight = 0.0f;
    } else if (b->flagged) {
        s->flag_n++;
        if (b->hold_release) s->hold_n++;
    }

    s->gap[s->n] = b->last_gap;
    s->nu[s->n] = b->last_nu;
    if (s->have_last && v_meas_mps == s->last) s->same++;
    s->last = v_meas_mps;
    s->have_last = true;
    s->n++;
    s->k++;
    if (s->n == SUP_BLOCK_STEPS) {
        supervisor_review(s);
        s->n = 0;
        s->same = 0;
        /* As the Python side does: the first sample of a block is not
           compared with the last of the one before. */
        s->have_last = false;
        s->block++;
    }
    return out;
}

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
