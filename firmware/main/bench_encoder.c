#include "bench_encoder.h"

#include <math.h>
#include <stdio.h>
#include <string.h>

#include "esp_timer.h"

/* Deployed configuration, from docs/g1-compute-budget.md and matched to the
   trained model in src/evpil/forecast/models.py. */
#define SEQ      32
#define D_MODEL  32
#define N_HEADS   4
#define D_HEAD   (D_MODEL / N_HEADS)
#define D_FF     (2 * D_MODEL)
#define N_FEAT    8
#define HORIZON  30
#define LAYERS    2

/* Activations stay int8 between operations, exactly as they would on the
   device; accumulation is int32 and the result is requantised on the way out.
   Two buffers are enough because every operation reads one and writes the
   other. */
static int8_t  s_x[SEQ * D_MODEL];
static int8_t  s_y[SEQ * D_MODEL];
static int8_t  s_qkv[SEQ * 3 * D_MODEL];
static int8_t  s_ff[SEQ * D_FF];
static int32_t s_scores[SEQ * SEQ];
static int8_t  s_out[HORIZON];

static int8_t  s_w_embed[N_FEAT * D_MODEL];
static int8_t  s_w_qkv[LAYERS][D_MODEL * 3 * D_MODEL];
static int8_t  s_w_proj[LAYERS][D_MODEL * D_MODEL];
static int8_t  s_w_ff1[LAYERS][D_MODEL * D_FF];
static int8_t  s_w_ff2[LAYERS][D_FF * D_MODEL];
static int8_t  s_w_head[D_MODEL * HORIZON];
static int8_t  s_input[SEQ * N_FEAT];

static volatile int32_t s_sink;

static void fill_i8(int8_t *dst, int n, int seed)
{
    for (int i = 0; i < n; i++) {
        dst[i] = (int8_t) (((i * 31 + seed * 17) & 0x3F) - 32);
    }
}

/* C[m,n] = requantise(A[m,k] * B[k,n]). The shift stands in for the
   multiplier-and-shift requantisation a real int8 kernel applies; it costs the
   same arithmetic, which is what is being timed. */
static void matmul_i8(const int8_t *a, const int8_t *b, int8_t *c,
                      int m, int k, int n, int shift)
{
    for (int i = 0; i < m; i++) {
        for (int j = 0; j < n; j++) {
            int32_t acc = 0;
            const int8_t *arow = a + i * k;
            const int8_t *bcol = b + j;
            for (int p = 0; p < k; p++) {
                acc += (int32_t) arow[p] * (int32_t) bcol[p * n];
            }
            acc >>= shift;
            if (acc > 127) acc = 127;
            if (acc < -128) acc = -128;
            c[i * n + j] = (int8_t) acc;
        }
    }
}

/* Mean and variance over the feature axis, then rescale. Integer mean, integer
   variance, one reciprocal square root per row: the shape of what an int8
   kernel does, and the part a MAC count does not see at all. */
static void layernorm_i8(int8_t *x, int rows, int cols)
{
    for (int r = 0; r < rows; r++) {
        int8_t *row = x + r * cols;
        int32_t sum = 0;
        for (int c = 0; c < cols; c++) sum += row[c];
        int32_t mean = sum / cols;

        int32_t var = 0;
        for (int c = 0; c < cols; c++) {
            int32_t d = row[c] - mean;
            var += d * d;
        }
        float inv = 1.0f / sqrtf((float) var / (float) cols + 1e-3f);

        for (int c = 0; c < cols; c++) {
            int32_t v = (int32_t) ((row[c] - mean) * inv * 32.0f);
            if (v > 127) v = 127;
            if (v < -128) v = -128;
            row[c] = (int8_t) v;
        }
    }
}

/* Softmax over each row of the score matrix. One exponential per element is
   the expensive part, and there are SEQ * SEQ * N_HEADS of them. */
static void softmax_rows(int32_t *scores, int8_t *dst, int rows, int cols)
{
    for (int r = 0; r < rows; r++) {
        int32_t *row = scores + r * cols;
        int32_t peak = row[0];
        for (int c = 1; c < cols; c++) if (row[c] > peak) peak = row[c];

        float total = 0.0f;
        float tmp[SEQ];
        for (int c = 0; c < cols; c++) {
            tmp[c] = expf((float) (row[c] - peak) * 0.02f);
            total += tmp[c];
        }
        float inv = 127.0f / total;
        for (int c = 0; c < cols; c++) {
            dst[r * cols + c] = (int8_t) (tmp[c] * inv);
        }
    }
}

static void relu_i8(int8_t *x, int n)
{
    for (int i = 0; i < n; i++) if (x[i] < 0) x[i] = 0;
}

static void attention(int layer)
{
    /* One projection produces query, key and value together, which is how
       PyTorch stores it and how it would be exported. */
    matmul_i8(s_x, s_w_qkv[layer], s_qkv, SEQ, D_MODEL, 3 * D_MODEL, 7);

    static int8_t heads[SEQ * D_MODEL];
    static int8_t probs[SEQ * SEQ];

    for (int h = 0; h < N_HEADS; h++) {
        const int8_t *q = s_qkv + h * D_HEAD;
        const int8_t *k = s_qkv + D_MODEL + h * D_HEAD;
        const int8_t *v = s_qkv + 2 * D_MODEL + h * D_HEAD;

        for (int i = 0; i < SEQ; i++) {
            for (int j = 0; j < SEQ; j++) {
                int32_t acc = 0;
                for (int p = 0; p < D_HEAD; p++) {
                    acc += (int32_t) q[i * 3 * D_MODEL + p]
                         * (int32_t) k[j * 3 * D_MODEL + p];
                }
                s_scores[i * SEQ + j] = acc;
            }
        }
        softmax_rows(s_scores, probs, SEQ, SEQ);

        for (int i = 0; i < SEQ; i++) {
            for (int p = 0; p < D_HEAD; p++) {
                int32_t acc = 0;
                for (int j = 0; j < SEQ; j++) {
                    acc += (int32_t) probs[i * SEQ + j]
                         * (int32_t) v[j * 3 * D_MODEL + p];
                }
                acc >>= 7;
                if (acc > 127) acc = 127;
                if (acc < -128) acc = -128;
                heads[i * D_MODEL + h * D_HEAD + p] = (int8_t) acc;
            }
        }
    }
    matmul_i8(heads, s_w_proj[layer], s_y, SEQ, D_MODEL, D_MODEL, 7);
    memcpy(s_x, s_y, sizeof s_x);
}

static void encoder_layer(int layer)
{
    layernorm_i8(s_x, SEQ, D_MODEL);
    attention(layer);
    layernorm_i8(s_x, SEQ, D_MODEL);
    matmul_i8(s_x, s_w_ff1[layer], s_ff, SEQ, D_MODEL, D_FF, 7);
    relu_i8(s_ff, SEQ * D_FF);
    matmul_i8(s_ff, s_w_ff2[layer], s_x, SEQ, D_FF, D_MODEL, 7);
}

static void forward_once(void)
{
    matmul_i8(s_input, s_w_embed, s_x, SEQ, N_FEAT, D_MODEL, 5);
    for (int l = 0; l < LAYERS; l++) encoder_layer(l);
    /* The head reads the final token only, so it is paid once per inference. */
    matmul_i8(s_x + (SEQ - 1) * D_MODEL, s_w_head, s_out, 1, D_MODEL, HORIZON, 7);
    s_sink = s_out[0];
}

/* ---- the LSTM arm, for comparison --------------------------------------

   The Transformer's measured time exceeded its MAC-count estimate by 64%, and
   most of the excess was softmax. That raises an obvious question about the
   LSTM, whose estimate was produced the same way: it has no softmax, but four
   gates per timestep means 4 * H sigmoid or tanh evaluations on every one of
   SEQ steps, which is the same order of nonlinear work. Measuring both is the
   only way to know whether the gap is a property of attention or of the
   estimating method. */

#define H_LSTM 64

static int8_t  s_w_ih[4 * H_LSTM * N_FEAT];
static int8_t  s_w_hh[4 * H_LSTM * H_LSTM];
static int8_t  s_w_lstm_head[H_LSTM * HORIZON];
static int8_t  s_h[H_LSTM];
static int8_t  s_c[H_LSTM];
static int32_t s_gates[4 * H_LSTM];

/* Same shape as a real int8 kernel: a table would replace expf on the device,
   and swapping it in is exactly the optimisation this measurement prices. */
static float sigmoid_f(float x) { return 1.0f / (1.0f + expf(-x)); }

static void lstm_forward_once(void)
{
    memset(s_h, 0, sizeof s_h);
    memset(s_c, 0, sizeof s_c);

    for (int t = 0; t < SEQ; t++) {
        const int8_t *x = s_input + t * N_FEAT;

        for (int g = 0; g < 4 * H_LSTM; g++) {
            int32_t acc = 0;
            const int8_t *wi = s_w_ih + g * N_FEAT;
            for (int p = 0; p < N_FEAT; p++) acc += (int32_t) wi[p] * (int32_t) x[p];
            const int8_t *wh = s_w_hh + g * H_LSTM;
            for (int p = 0; p < H_LSTM; p++) acc += (int32_t) wh[p] * (int32_t) s_h[p];
            s_gates[g] = acc;
        }

        for (int j = 0; j < H_LSTM; j++) {
            float i_g = sigmoid_f((float) s_gates[j] * 0.001f);
            float f_g = sigmoid_f((float) s_gates[H_LSTM + j] * 0.001f);
            float g_g = tanhf((float) s_gates[2 * H_LSTM + j] * 0.001f);
            float o_g = sigmoid_f((float) s_gates[3 * H_LSTM + j] * 0.001f);

            float c = f_g * (float) s_c[j] + i_g * g_g * 127.0f;
            if (c > 127.0f) c = 127.0f;
            if (c < -128.0f) c = -128.0f;
            s_c[j] = (int8_t) c;

            float h = o_g * tanhf(c / 127.0f) * 127.0f;
            if (h > 127.0f) h = 127.0f;
            if (h < -128.0f) h = -128.0f;
            s_h[j] = (int8_t) h;
        }
    }
    matmul_i8(s_h, s_w_lstm_head, s_out, 1, H_LSTM, HORIZON, 7);
    s_sink = s_out[0];
}

static void bench_lstm(void)
{
    fill_i8(s_w_ih, sizeof s_w_ih, 21);
    fill_i8(s_w_hh, sizeof s_w_hh, 22);
    fill_i8(s_w_lstm_head, sizeof s_w_lstm_head, 23);

    lstm_forward_once();

    const int reps = 50;
    int64_t t0 = esp_timer_get_time();
    for (int r = 0; r < reps; r++) lstm_forward_once();
    int64_t t1 = esp_timer_get_time();

    size_t weights = sizeof s_w_ih + sizeof s_w_hh + sizeof s_w_lstm_head;
    printf("EVPIL-G5 lstm hidden=%d layers=1 forward_us=%.1f weight_bytes=%u\n",
           H_LSTM, (double) (t1 - t0) / reps, (unsigned) weights);
}

void bench_encoder_report(void)
{
    fill_i8(s_input, sizeof s_input, 1);
    fill_i8(s_w_embed, sizeof s_w_embed, 2);
    fill_i8(s_w_head, sizeof s_w_head, 3);
    for (int l = 0; l < LAYERS; l++) {
        fill_i8(s_w_qkv[l], sizeof s_w_qkv[l], 4 + l);
        fill_i8(s_w_proj[l], sizeof s_w_proj[l], 6 + l);
        fill_i8(s_w_ff1[l], sizeof s_w_ff1[l], 8 + l);
        fill_i8(s_w_ff2[l], sizeof s_w_ff2[l], 10 + l);
    }

    forward_once();                 /* warm the caches before timing */

    const int reps = 50;
    int64_t t0 = esp_timer_get_time();
    for (int r = 0; r < reps; r++) forward_once();
    int64_t t1 = esp_timer_get_time();
    double per_us = (double) (t1 - t0) / reps;

    /* The pieces, timed separately, so the report can say where the time goes
       rather than only how much there is. */
    int64_t a0 = esp_timer_get_time();
    for (int r = 0; r < reps; r++)
        matmul_i8(s_x, s_w_ff1[0], s_ff, SEQ, D_MODEL, D_FF, 7);
    int64_t a1 = esp_timer_get_time();

    int64_t b0 = esp_timer_get_time();
    for (int r = 0; r < reps; r++) softmax_rows(s_scores, s_ff, SEQ, SEQ);
    int64_t b1 = esp_timer_get_time();

    int64_t c0 = esp_timer_get_time();
    for (int r = 0; r < reps; r++) layernorm_i8(s_x, SEQ, D_MODEL);
    int64_t c1 = esp_timer_get_time();

    size_t weights = sizeof s_w_embed + sizeof s_w_qkv + sizeof s_w_proj
                   + sizeof s_w_ff1 + sizeof s_w_ff2 + sizeof s_w_head;
    size_t arena = sizeof s_x + sizeof s_y + sizeof s_qkv + sizeof s_ff
                 + sizeof s_scores + sizeof s_out;

    printf("EVPIL-G5 seq=%d d_model=%d layers=%d heads=%d horizon=%d\n",
           SEQ, D_MODEL, LAYERS, N_HEADS, HORIZON);
    printf("EVPIL-G5 forward_us=%.1f reps=%d\n", per_us, reps);
    printf("EVPIL-G5 matmul32x32x64_us=%.2f softmax32x32_us=%.2f "
           "layernorm32x32_us=%.2f\n",
           (double) (a1 - a0) / reps, (double) (b1 - b0) / reps,
           (double) (c1 - c0) / reps);
    printf("EVPIL-G5 weight_bytes=%u arena_bytes=%u\n",
           (unsigned) weights, (unsigned) arena);

    bench_lstm();
}
