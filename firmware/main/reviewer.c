#include "reviewer.h"

#include <math.h>

static float sigmoidf(float x)
{
    return 1.0f / (1.0f + expf(-x));
}

void reviewer_reset(reviewer_state_t *st)
{
    int i;

    for (i = 0; i < REVIEWER_HIDDEN; i++) {
        st->h[i] = 0.0f;
    }
}

void reviewer_step(reviewer_state_t *st, const float *x, float *logits)
{
    float xm[REVIEWER_INPUTS];
    float h_new[REVIEWER_HIDDEN];
    int i;
    int j;

    for (j = 0; j < REVIEWER_INPUTS; j++) {
        xm[j] = x[j] * reviewer_mask[j];
    }

#if REVIEWER_KIND == REVIEWER_KIND_GRU
    /* r, z, n as torch.nn.GRU orders and defines them. */
    for (i = 0; i < REVIEWER_HIDDEN; i++) {
        float gi[3];
        float gh[3];
        float r;
        float z;
        float c;
        int g;

        for (g = 0; g < 3; g++) {
            const int row = g * REVIEWER_HIDDEN + i;

            gi[g] = reviewer_b_ih[row];
            gh[g] = reviewer_b_hh[row];
            for (j = 0; j < REVIEWER_INPUTS; j++) {
                gi[g] += reviewer_w_ih[row][j] * xm[j];
            }
            for (j = 0; j < REVIEWER_HIDDEN; j++) {
                gh[g] += reviewer_w_hh[row][j] * st->h[j];
            }
        }
        r = sigmoidf(gi[0] + gh[0]);
        z = sigmoidf(gi[1] + gh[1]);
        c = tanhf(gi[2] + r * gh[2]);
        h_new[i] = (1.0f - z) * c + z * st->h[i];
    }
#else
    /* FastGRNN: one pair of matrices shared by the gate and the candidate. */
    {
        const float zeta = sigmoidf(reviewer_zeta);
        const float nu = sigmoidf(reviewer_nu);

        for (i = 0; i < REVIEWER_HIDDEN; i++) {
            float pre = 0.0f;
            float z;
            float c;

            for (j = 0; j < REVIEWER_INPUTS; j++) {
                pre += reviewer_w[i][j] * xm[j];
            }
            for (j = 0; j < REVIEWER_HIDDEN; j++) {
                pre += reviewer_u[i][j] * st->h[j];
            }
            z = sigmoidf(pre + reviewer_b_z[i]);
            c = tanhf(pre + reviewer_b_h[i]);
            h_new[i] = (zeta * (1.0f - z) + nu) * c + z * st->h[i];
        }
    }
#endif

    for (i = 0; i < REVIEWER_HIDDEN; i++) {
        st->h[i] = h_new[i];
    }
    for (i = 0; i < REVIEWER_OUTPUTS; i++) {
        float y = reviewer_b_out[i];

        for (j = 0; j < REVIEWER_HIDDEN; j++) {
            y += reviewer_w_out[i][j] * st->h[j];
        }
        logits[i] = y;
    }
}
