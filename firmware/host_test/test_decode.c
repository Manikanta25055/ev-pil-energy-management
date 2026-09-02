/* Runs the firmware's action decode on policy outputs read from stdin, so the
   same C code the board runs can be checked against the training environment's
   decode without a board.

   Separate from test_actor.c because this is a different claim. That one asks
   whether the network was exported correctly; this asks whether the action it
   produces is turned into the same physical command the environment used while
   the policy was learning. A mismatch here is invisible: every output stays in
   range and only the energy result is wrong. */
#include <stdio.h>
#include "actor.h"

int main(void)
{
    float a[3], blend, p_limit, derate;

    for (;;) {
        if (scanf("%f %f %f", &a[0], &a[1], &a[2]) != 3) return 0;
        actor_decode_action_raw(a, &blend, &p_limit, &derate);
        printf("%.9e %.9e %.9e\n", blend, p_limit, derate);
        fflush(stdout);
    }
}
