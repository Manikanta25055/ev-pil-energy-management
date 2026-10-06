#pragma once
#include <stdbool.h>

/* What the decision model reads: the last 3.2 s as 32 blocks of 100 ms, each
   reduced to ten numbers by the 10 ms control task as it goes.

   This mirrors evpil.control.block_features, feature for feature and scale
   for scale. tests/control/test_features_c_parity.py drives both with the
   same samples and requires the rows to agree, because a model trained on one
   set of features and fed another returns confident answers to a question
   nobody asked. */

#define FEAT_BLOCK_STEPS 10
#define FEAT_N           10
#define FEAT_WINDOW      32

/* Mean and spread of one channel over a block, summed about the block's first
   value: single precision cannot hold the square of a 300 A current and a
   0.1 A ripple on it in the same sum. */
typedef struct {
    float x0, s1, s2;
} feat_spread_t;

/* Zero-initialise it. */
typedef struct {
    int           n;
    feat_spread_t v, dv, a, i;
    float         tq_sum;
    int           flips;
    float         v_prev, tq_prev;
    bool          have_prev;
} feat_block_t;

/* Zero-initialise it. */
typedef struct {
    float rows[FEAT_WINDOW][FEAT_N];
    int   head;
    int   count;
} feat_window_t;

/* Add one 10 ms sample. Returns true on every FEAT_BLOCK_STEPS-th call, with
   the block's scaled features written to `row`; otherwise `row` is left
   alone. */
bool features_push(feat_block_t *b, float v_meas_mps, float a_meas_mps2,
                   float torque_nm, float i_batt_a, float v_ref_mps,
                   float a_ref_mps2, float row[FEAT_N]);

void features_window_push(feat_window_t *w, const float row[FEAT_N]);

/* Oldest block first, zero-padded at the old end until the window has filled. */
void features_window_copy(const feat_window_t *w,
                          float out[FEAT_WINDOW][FEAT_N]);
