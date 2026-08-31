# Week 7: the DP optimum, the PID inner loop, and the RL ramp-up

**Date:** 2026-08-31
**Scripts:** `scripts/run_control_baselines.py`, `scripts/run_pid_robustness.py`,
`scripts/run_rl_rampup.py`, `scripts/build_cycles.py`
**Data:** `docs/week7-control-baselines.csv`, `docs/week7-pid-robustness.csv`,
`docs/week7-rl-rampup.json`
**Figures:** `docs/figures/week7-control.png`,
`docs/figures/week7-pid-robustness.png`

Week 7 in the schedule is the DP global optimum, the PID baseline, and an RL
ramp-up on a toy environment. All three are done, and the DP produced a result
that has to be raised before week 8 rather than after it.

---

## 1. The headline, stated plainly

**With the speed trajectory fixed and cabin comfort priced at what it costs,
the optimal energy-management policy is the constant action "regenerate as
much as the pack will take".** The dynamic program agrees with that constant
action to 0.000% on all four cycles. The rule-based manager is within 0.16% of
it. There is no headroom left for a learned policy to find.

| Cycle | Split | no-regen | always-regen | rule-EMS | DP optimum | rule gap |
|---|---|---|---|---|---|---|
| WLTC 3b | train | 204.56 | 175.94 | 175.99 | **175.94** | +0.03% |
| UDDS | train | 207.02 | 167.67 | 167.93 | **167.67** | +0.16% |
| HWFET | val | 162.26 | 153.89 | 153.90 | **153.89** | +0.01% |
| US06 | test | 233.14 | 190.39 | 190.47 | **190.39** | +0.04% |

Wh/km, starting SoC 0.80, ambient 12 degC. Full table with tracking error,
peak current, recovered energy and terminal SoC in
`docs/week7-control-baselines.csv`.

Regeneration itself is worth a great deal -- 5.4% on the highway cycle and up
to 23.5% in city traffic. That is the energy story of this vehicle, and one
threshold and one taper capture essentially all of it.

### Why this is a property of the problem, not of the optimiser

The plant's acceleration is a function of commanded torque and road grade
alone. Neither the regeneration blend nor the auxiliary derate appears in it,
so the speed trajectory is **exactly** invariant to the outer action -- this is
checked in `tests/control/test_sim.py`, not assumed. The discharge ceiling is
the only action that could change the trajectory, and only by starving the
tracker of power it needs, which the tracking constraint forbids. So:

- the discharge ceiling is a safety limiter, not an optimisation lever;
- the auxiliary derate trades cabin comfort for energy, and at a fair price it
  is a wash;
- the regeneration blend is the only real lever, and it is monotone: more
  recovery is never worse, so its optimum is "as much as the limits allow".

An optimiser whose action space is these three, under a fixed trajectory, has
one monotone dimension and two that do nothing. That is why the DP's answer is
a constant.

**The consequence for ablation A3 is now analytic rather than empirical.** A3
asks whether the RL controller needs the forecast in its state. Under a fixed
trajectory the optimal action does not depend on future power at all, so a
preview cannot help, and A3 is predictably null before it is run. The spec
pre-accepted a null A3 (3.2, R3). This is stronger than pre-acceptance: it is
a reason.

### What this does not say

It does not say the project is in trouble. It says the outer loop as currently
scoped is not where a contribution is. Three routes are open, and choosing
between them is the professor's call, not this document's. They are recorded
as an open item in the spec.

---

## 2. The inner loop

PID on speed with a physics feedforward, at 10 ms, mirrored in C as
`firmware/main/control.c` and checked against the Python reference step for
step in `tests/control/test_c_parity.py`.

On a clean run the tracking RMSE is 0.0007 m/s. **That number is not evidence
that the controller is any good.** The feedforward is computed from the same
vehicle the plant simulates, so it is exact and the feedback term corrects
almost nothing. Quoting it as a tracking result would be the control
engineering cousin of testing on the training set.

What the loop is actually worth is the table below, where the nominal model is
wrong in the ways a real one is wrong:

| Case | UDDS RMSE | US06 RMSE | US06 worst |
|---|---|---|---|
| nominal (exact feedforward) | 0.0007 | 0.0013 | 0.017 |
| mass +10% | 0.0183 | 0.0307 | 0.190 |
| drag +30% | 0.0011 | 0.0024 | 0.017 |
| rolling resistance +50% | 0.0020 | 0.0025 | 0.030 |
| road grade unknown to the feedforward | 0.0037 | 0.0035 | 0.029 |
| speed noise, 0.2 m/s | 0.0219 | 0.0232 | 0.100 |
| link delay, 100 ms | 0.0651 | 0.1027 | 0.383 |
| **feedforward switched off entirely** | 0.1683 | 0.2952 | **1.499** |

m/s. Worst case across every perturbation is 0.30 m/s RMSE and 1.5 m/s
instantaneous, on the aggressive cycle with the feedforward removed. Tracking
is a hard constraint the energy comparison rests on, and it holds.

One number in that table is a result rather than a check: **injected speed
noise costs 5.6% of consumption** (167.9 to 179.3 Wh/km on UDDS). The
controller chases the noise and pays for it in torque reversals. That is a
sensor-quality argument with an energy price attached, and it belongs in the
robustness section of the paper.

---

## 3. The dynamic program

Backward value iteration over state of charge, at the 100 ms outer period,
with the regeneration blend and the auxiliary derate as decisions and the
discharge ceiling held at maximum for the reason in section 1.

Two prices for comfort, reported separately rather than blended into one
number:

| Price | Meaning | Result |
|---|---|---|
| 1.0 | a watt of cabin heat is worth the watt it costs | sheds nothing; optimum is always-regen |
| 0.0 | comfort is free | sheds the maximum on every step, 3.4% to 9.6% "saving" |

The comfort-free row is the upper bound on what shedding can buy, and it is
reported precisely so that nobody quotes it as an energy-management result. A
controller that saves energy by turning the heater down in a Munich winter has
done the same thing as a controller that saves energy by driving slower.

**The reported optimum is the plant's number, not the value function's.** The
DP carries SoC as its only state and treats the RC branch as exogenous, so its
value function is an approximation; it is used only to derive a policy, which
is then run through the full plant. Measured agreement between the two:

| Cycle | comfort-free arm | comfort-priced arm |
|---|---|---|
| WLTC 3b | -0.0007% | +0.25% |
| UDDS | +0.0002% | +0.86% |
| HWFET | -0.0010% | +0.35% |
| US06 | -0.0102% | +0.33% |

The priced arm is the looser one because its decisions sit on an exact tie, so
an approximation error of any size can flip one. That is also why the solver
carries an explicit 0.1 W tie-break preference (`DpSpec.tie_break_w`): without
it, ties were broken by floating-point noise in the value interpolation and
the optimiser wrote "no regeneration" into driving stages that contained
braking, losing 0.07% to nothing at all.

---

## 4. The RL ramp-up

Risk R1 names reinforcement learning as the identified skill gap and schedules
a ramp-up week so that week 8 spends its time on convergence rather than on
plumbing. Two runs, in this order, because they fail for different reasons.

| Run | Result |
|---|---|
| SAC on Pendulum-v1, 10k steps | return **-191.0** against a -300 target. PASS. The installation and the default hyperparameters are sound |
| Environment throughput | 2,649 outer steps/s with random actions; 26,487 plant steps/s |
| SAC on the energy environment, 15k steps | 230 steps/s including gradient updates |

Projected cost of week 8: **22 minutes per seed at 300k steps, 1.8 hours for
five seeds** on this machine. That is a measurement, not an estimate, and it
means the five-seed requirement in spec 6.2 is affordable.

After 15k steps -- a ramp-up, not a trained controller -- SAC reaches 45.5 Wh
per evaluation episode against the rule manager's 46.5 Wh, but a slightly
*worse* reward (-47.8 against -46.5). It is buying the energy by shedding
cabin load, and the reward is charging it for that. The reward is doing its
job.

`stable-baselines3` 2.9.0, `gymnasium` 1.3.0. The environment passes both the
Gymnasium and the SB3 environment checkers.

---

## 5. Driving cycles

Fetched from their publishers by `scripts/build_cycles.py` and cached under
`data/raw/cycles/`. Distances reproduce the published figures, which is the
check that catches a unit error or a dropped tail:

| Cycle | Source | Duration | Distance | v_max |
|---|---|---|---|---|
| UDDS | US EPA dynamometer drive schedules | 1369 s | 11.99 km | 91.2 km/h |
| HWFET | US EPA | 765 s | 16.51 km | 96.4 km/h |
| US06 | US EPA | 600 s | 12.89 km | 129.2 km/h |
| FTP-75 | US EPA | 1874 s | 17.77 km | 91.2 km/h |
| WLTC class 3b | UN GTR No. 15 Annex 1, via JRCSTU/wltp | 1800 s | 23.27 km | 131.3 km/h |

Resampled to the 10 ms control period by linear interpolation between
published samples, which is how the regulations define the trace. A
zero-order hold would put a step between every one-second sample and ask the
tracker for an unbounded acceleration once a second.
