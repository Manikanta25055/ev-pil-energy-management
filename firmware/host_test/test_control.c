/* Dumps the C controller's output for a fixed input sequence, so that
   tests/control/test_c_parity.py can compare it against the Python
   implementation the simulation results came from.

   It prints rather than asserts: the reference values live in Python, and
   duplicating them here would mean maintaining the same numbers twice and
   discovering a divergence only when someone updated both. */
#include <stdio.h>
#include "control.h"

int main(void)
{
    printf("# feedforward: v_ref a_ref grade torque\n");
    const float vs[] = {0.0f, 5.0f, 15.0f, 30.0f, 40.0f};
    const float as[] = {-2.0f, -0.5f, 0.0f, 0.5f, 2.0f};
    const float gs[] = {-0.05f, 0.0f, 0.03f};
    for (unsigned i = 0; i < sizeof vs / sizeof *vs; i++)
        for (unsigned j = 0; j < sizeof as / sizeof *as; j++)
            for (unsigned k = 0; k < sizeof gs / sizeof *gs; k++)
                printf("ff %.6f %.6f %.6f %.6f\n", vs[i], as[j], gs[k],
                       control_feedforward_nm(&k_vehicle, vs[i], as[j], gs[k]));

    printf("# torque limit: omega limit\n");
    const float ws[] = {0.0f, 100.0f, 500.0f, 900.0f, 1191.0f, 1300.0f};
    for (unsigned i = 0; i < sizeof ws / sizeof *ws; i++)
        printf("lim %.6f %.6f\n", ws[i],
               control_torque_limit_nm(&k_vehicle, ws[i]));

    /* A closed sequence: constant reference, a measurement that lags, then a
       saturating demand. It exercises the integrator, the derivative filter
       and the anti-windup branch in one run. */
    printf("# pid: step v_ref v_meas torque integral\n");
    pid_state_t st = {0};
    for (int n = 0; n < 200; n++) {
        float v_ref = (n < 100) ? 12.0f : 30.0f;
        float v_meas = (n < 100) ? 11.5f : 5.0f;
        float limit = (n < 150) ? 250.0f : 8.0f;
        float tq = control_pid_step(&k_pid_gains, &st, v_ref, v_meas,
                                    3.5f, limit, 0.01f, NULL);
        printf("pid %d %.6f %.6f %.6f %.6f\n", n, v_ref, v_meas, tq,
               st.integral_nm);
    }

    /* A ramp with a deterministic disturbance on it, through each alpha the
       decision table uses plus two that must behave as no filter. */
    printf("# filt: alpha step v_meas v_out\n");
    const float alphas[] = {1.0f, 0.3f, 0.1f, 0.03f, 0.0f, 1.5f};
    for (unsigned i = 0; i < sizeof alphas / sizeof *alphas; i++) {
        speed_filter_t f = {0};
        for (int n = 0; n < 120; n++) {
            float v = 20.0f + 0.05f * (float) n
                      + 0.4f * (float) ((n * 37) % 11 - 5) / 5.0f;
            printf("filt %.6f %d %.6f %.6f\n", alphas[i], n, v,
                   control_speed_filter_step(&f, v, alphas[i]));
        }
    }

    /* The Kalman estimate, fixed and adaptive, over one sequence: a launch,
       a cruise, a braking phase on a grade, with a jitter on the measurement
       that grows tenfold half way so the adaptive arm has something to adapt
       to. The measurement is not a simulation of anything; parity only needs
       both sides to see the same numbers. */
    printf("# kf: mode step v_meas torque grade v_est sigma\n");
    for (int mode = 0; mode < 2; mode++) {
        kalman_speed_t kf;
        control_kalman_init(&kf, mode ? 0.02f : 0.06f);
        for (int n = 0; n < 600; n++) {
            float jit = (float) ((n * 37) % 11 - 5) / 5.0f;
            float amp = (n < 300) ? 0.03f : 0.3f;
            float base = (n < 200) ? 0.02f * (float) n
                       : (n < 400) ? 4.0f + 0.002f * (float) (n - 200)
                       : 4.4f - 0.015f * (float) (n - 400);
            float v = 25.0f + base + amp * jit;
            float tq = (n < 200) ? 180.0f : (n < 400) ? 35.0f : -120.0f;
            float grade = (n < 400) ? 0.0f : 0.03f;
            float est = control_kalman_step(&k_vehicle, &kf,
                                            mode ? 0.002f : 0.0005f, mode,
                                            0.005f, v, tq, grade, 0.01f);
            printf("kf %d %d %.6f %.6f %.6f %.6f %.6f\n", mode, n, v, tq,
                   grade, est, kf.meter.sigma_mps);
        }
    }

    printf("# rule: soc v blend p_limit derate\n");
    const float socs[] = {0.05f, 0.07f, 0.12f, 0.20f, 0.50f, 0.85f, 0.90f,
                          0.94f, 0.99f};
    const float vms[] = {0.0f, 1.0f, 2.0f, 20.0f};
    for (unsigned i = 0; i < sizeof socs / sizeof *socs; i++)
        for (unsigned j = 0; j < sizeof vms / sizeof *vms; j++) {
            ems_action_t a = control_rule_action(socs[i], vms[j]);
            printf("rule %.6f %.6f %.6f %.6f %.6f\n", socs[i], vms[j],
                   a.regen_blend, a.p_limit_w, a.aux_derate);
        }
    return 0;
}
