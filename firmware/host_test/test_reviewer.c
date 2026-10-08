/* Reads rows of REVIEWER_INPUTS features on stdin, one block per line, and
 * prints the reviewer's logits for each. A line holding only "reset" clears
 * the state. tests/control/test_reviewer_c_parity.py compares the output
 * with evpil.control.tiny_rnn. */
#include <stdio.h>
#include <string.h>

#include "reviewer.h"

int main(void)
{
    reviewer_state_t st;
    float x[REVIEWER_INPUTS];
    float y[REVIEWER_OUTPUTS];
    char line[1024];
    int i;

    reviewer_reset(&st);
    while (fgets(line, sizeof line, stdin) != NULL) {
        char *p = line;
        int used = 0;

        if (strncmp(line, "reset", 5) == 0) {
            reviewer_reset(&st);
            continue;
        }
        for (i = 0; i < REVIEWER_INPUTS; i++) {
            if (sscanf(p, "%f%n", &x[i], &used) != 1) {
                return 1;
            }
            p += used;
        }
        reviewer_step(&st, x, y);
        for (i = 0; i < REVIEWER_OUTPUTS; i++) {
            printf("%.9g%c", (double) y[i], i + 1 < REVIEWER_OUTPUTS ? ' ' : '\n');
        }
    }
    return 0;
}
