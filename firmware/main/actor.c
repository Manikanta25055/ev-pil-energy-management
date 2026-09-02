#include "actor.h"

/* Angle brackets, deliberately. A quoted include is resolved against the
   including file's own directory FIRST, before any -I path, so
   `#include "sac_actor_weights.h"` from this file always picks up
   firmware/main/sac_actor_weights.h no matter what the caller puts on the
   include path. The host parity harness generates its own weights into a
   temporary directory and compiles this file against them; with a quoted
   include it silently tested the deployed policy instead, agreed with itself,
   and passed. It only started failing once a deployed header existed, which
   is the worst possible moment to learn that a test was not testing anything.
   Angle brackets search the -I path only, so the caller decides. */
#include <sac_actor_weights.h>

#include <math.h>
#include <string.h>

#if defined(ESP_PLATFORM)
#include "esp_timer.h"
static inline uint32_t now_us(void) { return (uint32_t) esp_timer_get_time(); }
#else
#include <time.h>
static inline uint32_t now_us(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint32_t) (ts.tv_sec * 1000000u + ts.tv_nsec / 1000u);
}
#endif

#define MAXW SAC_ACTOR_MAX_WIDTH

/* The weight-pointer tables below are written out per layer, so a network
   with a different depth would compile against the wrong arrays rather than
   fail. Fail here instead, at build time, with the reason. */
_Static_assert(SAC_ACTOR_N_LAYERS == 3,
               "actor.c expects two hidden layers plus an output layer; "
               "regenerate the pointer tables for a different net_arch");

static const float *const k_w[SAC_ACTOR_N_LAYERS] = {
    sac_actor_w0, sac_actor_w1, sac_actor_w2,
};
static const float *const k_b[SAC_ACTOR_N_LAYERS] = {
    sac_actor_b0, sac_actor_b1, sac_actor_b2,
};

void actor_scale_observation(const float *raw, float *scaled, int n)
{
    for (int i = 0; i < n; i++) {
        float v = raw[i] / sac_actor_obs_scale[i];
        if (v >  sac_actor_obs_clip) v =  sac_actor_obs_clip;
        if (v < -sac_actor_obs_clip) v = -sac_actor_obs_clip;
        scaled[i] = v;
    }
}

uint32_t actor_forward(const float *scaled, float *action)
{
    uint32_t t0 = now_us();

    float buf_a[MAXW], buf_b[MAXW];
    const float *in = scaled;
    float *out = buf_a;
    int n_in = sac_actor_sizes[0];

    for (int layer = 0; layer < SAC_ACTOR_N_LAYERS; layer++) {
        int n_out = sac_actor_sizes[layer + 1];
        const float *w = k_w[layer];        /* row-major, (n_out, n_in) */
        const float *b = k_b[layer];

        for (int j = 0; j < n_out; j++) {
            /* Accumulating in double would cost more than it buys: the host
               reference is float64 and the tolerance in the parity test is
               set by that difference, which is measured rather than assumed. */
            float acc = b[j];
            const float *row = w + (size_t) j * n_in;
            for (int i = 0; i < n_in; i++) acc += row[i] * in[i];
            out[j] = acc;
        }

        if (layer + 1 < SAC_ACTOR_N_LAYERS) {
            for (int j = 0; j < n_out; j++)
                if (out[j] < 0.0f) out[j] = 0.0f;        /* ReLU */
        } else {
            for (int j = 0; j < n_out; j++)
                out[j] = tanhf(out[j]);                  /* squash */
        }

        in = out;
        out = (out == buf_a) ? buf_b : buf_a;
        n_in = n_out;
    }

    memcpy(action, in, (size_t) sac_actor_sizes[SAC_ACTOR_N_LAYERS]
                       * sizeof(float));
    return now_us() - t0;
}

/* Reported by the inference code itself rather than by whatever else got
   compiled alongside it. That distinction is the whole point: the checksum has
   to identify the weights this function multiplies by. */
uint32_t actor_checksum(void) { return SAC_ACTOR_CHECKSUM; }

int actor_n_in(void)  { return sac_actor_sizes[0]; }
int actor_n_out(void) { return sac_actor_sizes[SAC_ACTOR_N_LAYERS]; }

int actor_n_params(void)
{
    int n = 0;
    for (int layer = 0; layer < SAC_ACTOR_N_LAYERS; layer++) {
        int a = sac_actor_sizes[layer], b = sac_actor_sizes[layer + 1];
        n += a * b + b;
    }
    return n;
}


void actor_decode_action_raw(const float *action, float *regen_blend,
                             float *p_limit_w, float *aux_derate)
{
    /* Clip first. The policy's tanh cannot leave [-1, 1], but the contract
       this mirrors clips before mapping, and a decode that agrees with the
       host only for well-behaved inputs is not a parity anyone can rely on. */
    float a0 = action[0], a1 = action[1], a2 = action[2];
    if (a0 < -1.0f) a0 = -1.0f; else if (a0 > 1.0f) a0 = 1.0f;
    if (a1 < -1.0f) a1 = -1.0f; else if (a1 > 1.0f) a1 = 1.0f;
    if (a2 < -1.0f) a2 = -1.0f; else if (a2 > 1.0f) a2 = 1.0f;

    *regen_blend = 0.5f * (a0 + 1.0f);
    *p_limit_w   = sac_actor_p_limit_lo_w
                 + 0.5f * (a1 + 1.0f)
                   * (sac_actor_p_limit_hi_w - sac_actor_p_limit_lo_w);
    *aux_derate  = 0.5f * (a2 + 1.0f) * sac_actor_derate_max;
}
