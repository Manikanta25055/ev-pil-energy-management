/* Dumps the C block features for a fixed sample sequence, so that
   tests/control/test_features_c_parity.py can compare them against
   evpil.control.block_features.

   The inputs are printed as well as the outputs. Python reads the samples
   from here rather than regenerating them, so the two sides cannot disagree
   about what was fed in. */
#include <stdio.h>
#include "features.h"

static void print_row(const char *tag, int k, const float row[FEAT_N])
{
    printf("%s %d", tag, k);
    for (int j = 0; j < FEAT_N; j++) printf(" %.9g", row[j]);
    printf("\n");
}

int main(void)
{
    feat_block_t b = {0};
    feat_window_t w = {0};
    float row[FEAT_N];
    static float out[FEAT_WINDOW][FEAT_N];
    int blocks = 0;

    /* 370 samples: 37 blocks, so the window fills and wraps by five. A ramp
       with a deterministic jitter on it, a torque that crosses zero, and a
       current riding on a large offset. The partial window is dumped once
       before it fills. */
    for (int n = 0; n < 370; n++) {
        float jit = (float) ((n * 37) % 11 - 5) / 5.0f;
        float v = 18.0f + 0.03f * (float) n + 0.08f * jit;
        float a = 0.3f + 0.5f * (float) ((n * 13) % 7 - 3) / 3.0f;
        float tq = 40.0f * (float) ((n * 5) % 9 - 4) / 4.0f
                   + ((n / 60) % 2 ? 25.0f : -25.0f);
        float i = 280.0f + 0.6f * jit + 0.05f * (float) (n % 50);
        float v_ref = 18.0f + 0.03f * (float) n;
        float a_ref = 3.0f;
        printf("in %d %.9g %.9g %.9g %.9g %.9g %.9g\n",
               n, v, a, tq, i, v_ref, a_ref);
        if (features_push(&b, v, a, tq, i, v_ref, a_ref, row)) {
            print_row("blk", blocks, row);
            features_window_push(&w, row);
            blocks++;
            if (blocks == 3) {
                features_window_copy(&w, out);
                for (int r = 0; r < FEAT_WINDOW; r++)
                    print_row("part", r, out[r]);
            }
        }
    }
    features_window_copy(&w, out);
    for (int r = 0; r < FEAT_WINDOW; r++) print_row("win", r, out[r]);
    return 0;
}
