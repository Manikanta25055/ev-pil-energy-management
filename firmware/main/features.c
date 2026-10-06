#include "features.h"

#include <math.h>
#include <string.h>

/* Divisors that put each feature roughly in [-1, 1]; the same numbers as
   evpil.control.block_features.FEATURE_SCALE, in the same order:
   v_mean dv_std a_mean a_std tq_mean tq_flips i_mean i_std v_ref a_ref. */
static const float k_scale[FEAT_N] = {
    40.0f, 0.5f, 5.0f, 5.0f, 250.0f, 10.0f, 350.0f, 100.0f, 40.0f, 5.0f,
};

static void spread_add(feat_spread_t *s, float x, bool first)
{
    if (first) {
        s->x0 = x;
        s->s1 = 0.0f;
        s->s2 = 0.0f;
        return;
    }
    float d = x - s->x0;
    s->s1 += d;
    s->s2 += d * d;
}

static float spread_mean(const feat_spread_t *s, int n)
{
    return s->x0 + s->s1 / (float) n;
}

static float spread_std(const feat_spread_t *s, int n)
{
    float m = s->s1 / (float) n;
    float var = s->s2 / (float) n - m * m;
    return (var > 0.0f) ? sqrtf(var) : 0.0f;
}

bool features_push(feat_block_t *b, float v_meas_mps, float a_meas_mps2,
                   float torque_nm, float i_batt_a, float v_ref_mps,
                   float a_ref_mps2, float row[FEAT_N])
{
    bool first = (b->n == 0);

    /* The very first sample has no predecessor; its difference is zero. */
    float dv = b->have_prev ? v_meas_mps - b->v_prev : 0.0f;
    if (first) {
        b->tq_sum = 0.0f;
        b->flips = 0;
    }
    spread_add(&b->v, v_meas_mps, first);
    spread_add(&b->dv, dv, first);
    spread_add(&b->a, a_meas_mps2, first);
    spread_add(&b->i, i_batt_a, first);
    b->tq_sum += torque_nm;
    /* A product below zero is a change of sign; passing through zero, or
       resting at it, is not. */
    if (b->have_prev && torque_nm * b->tq_prev < 0.0f) b->flips++;

    b->v_prev = v_meas_mps;
    b->tq_prev = torque_nm;
    b->have_prev = true;
    b->n++;
    if (b->n < FEAT_BLOCK_STEPS) return false;

    int n = FEAT_BLOCK_STEPS;
    row[0] = spread_mean(&b->v, n);
    row[1] = spread_std(&b->dv, n);
    row[2] = spread_mean(&b->a, n);
    row[3] = spread_std(&b->a, n);
    row[4] = b->tq_sum / (float) n;
    row[5] = (float) b->flips;
    row[6] = spread_mean(&b->i, n);
    row[7] = spread_std(&b->i, n);
    row[8] = v_ref_mps;
    row[9] = a_ref_mps2;
    for (int k = 0; k < FEAT_N; k++) row[k] /= k_scale[k];
    b->n = 0;
    return true;
}

void features_window_push(feat_window_t *w, const float row[FEAT_N])
{
    memcpy(w->rows[w->head], row, sizeof w->rows[0]);
    w->head = (w->head + 1) % FEAT_WINDOW;
    if (w->count < FEAT_WINDOW) w->count++;
}

void features_window_copy(const feat_window_t *w,
                          float out[FEAT_WINDOW][FEAT_N])
{
    for (int r = 0; r < FEAT_WINDOW; r++)
        memcpy(out[r], w->rows[(w->head + r) % FEAT_WINDOW], sizeof out[0]);
    if (w->count < FEAT_WINDOW)
        memset(out, 0, (size_t) (FEAT_WINDOW - w->count) * sizeof out[0]);
}
