/* Runs the firmware's actor inference on observations read from stdin, so the
   same C code that runs on the board can be checked against numpy without a
   board attached.

   One line in, one line out: N_IN floats become N_OUT floats. Reading the
   probes rather than compiling them in lets the Python test drive this with
   whatever inputs it likes, including random ones, instead of only the fixed
   set the on-device benchmark carries. */
#include <stdio.h>
#include "actor.h"

int main(void)
{
    float in[64], out[64];
    int n_in = actor_n_in(), n_out = actor_n_out();

    printf("# geometry %d %d %d\n", n_in, n_out, actor_n_params());
    /* From actor.c, not from a copy of the header included here: this file
       and the inference code can resolve the same include to different
       files, and that is exactly the failure this line has to expose. */
    printf("# checksum %08x\n", (unsigned) actor_checksum());

    for (;;) {
        for (int i = 0; i < n_in; i++)
            if (scanf("%f", &in[i]) != 1) return 0;
        actor_forward(in, out);
        for (int j = 0; j < n_out; j++)
            printf("%.9e%s", out[j], j + 1 == n_out ? "\n" : " ");
        fflush(stdout);
    }
}
