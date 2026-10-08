/* The learned reviewer: one recurrent cell step per 100 ms block.
 *
 * The same arithmetic as evpil.control.tiny_rnn, in float32. The weights and
 * the cell kind come from a generated header, reviewer_weights.h, written by
 * evpil.control.tiny_rnn.write_c_header. tests/control/test_reviewer_c_parity.py
 * builds this for the host and compares it with the Python cell.
 *
 * Not yet called from tasks.c: no reviewer has earned a place on the board. */
#pragma once

#include "reviewer_weights.h"

typedef struct {
    float h[REVIEWER_HIDDEN];
} reviewer_state_t;

void reviewer_reset(reviewer_state_t *st);

/* x: REVIEWER_INPUTS block features, scaled as the Python side scales them.
 * logits: REVIEWER_OUTPUTS values, before the temperature and the softmax. */
void reviewer_step(reviewer_state_t *st, const float *x, float *logits);
