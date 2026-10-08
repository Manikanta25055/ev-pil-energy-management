/* Runs B7, alone or with the on-chip monitor around it, over a drive read
 * from stdin: one line per 10 ms step, "v_meas a_meas torque". Prints the
 * estimate and the state a parity test needs.
 * tests/control/test_b7_c_parity.py and test_monitor_c_parity.py compare the
 * output with the Python classes step for step.
 *
 *   ./test_b7 b7  < drive      B7 alone
 *   ./test_b7 sup < drive      B7 with the rule monitor (architecture A2)
 */
#include <stdio.h>
#include <string.h>

#include "control.h"

int main(int argc, char **argv)
{
    static supervisor_t sup;
    b7_t *b = &sup.b;
    const int with_monitor = argc > 1 && strcmp(argv[1], "sup") == 0;
    float v, a, tq;

    control_supervisor_init(&sup);
    while (scanf("%f %f %f", &v, &a, &tq) == 3) {
        float est = with_monitor
            ? control_supervisor_step(&k_vehicle, &sup, 0.002f, 0.02f, 0.005f,
                                      v, a, tq, 0.0f, 0.01f)
            : control_b7_step(&k_vehicle, b, 0.002f, 0.02f, 0.005f, v, a, tq,
                              0.0f, 0.01f);
        printf("%.9g %d %u %u %.9g %.9g %u %d %.9g %.9g %u\n", (double) est,
               b->flagged ? 1 : 0, (unsigned) b->alarms, (unsigned) b->clears,
               (double) b->v_dr, (double) b->b_mps2, (unsigned) b->alarm_test,
               b->hold_release ? 1 : 0, (double) b->model_weight,
               (double) b->vigilance, (unsigned) sup.epoch);
    }
    return 0;
}
