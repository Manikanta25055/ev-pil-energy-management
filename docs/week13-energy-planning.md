# Energy planning: choosing the speed, not only following it

**Run 2026-10-09.** Branch `feature/sensor-arch`. Plan stage P6
(`docs/2026-10-07-model-advancement-research.md`, sections 5, 8 and A8), and
the P7 gate.
**Data:** `docs/week13-energy-planner.json`, from
`scripts/run_energy_planner.py`. **Code:** `src/evpil/plan/`.

SIMULATED on the laptop. No board. One run, reported as it came out: no arm
was tuned after its first result.

## 1. A different task

Every controller before this followed a speed trace it was given. A planner
chooses the trace. That is a new task, and its result is not a revision of
any energy figure in the earlier campaigns.

The task (`src/evpil/plan/route.py`, written before any planner): a route is
a drive cycle with the driver taken out. It keeps the cycle's distance, its
stops and the wait at each, a speed limit at every point (the fastest the
cycle went within 150 m), the hardest acceleration and braking the cycle
used, and the cycle's duration as the arrival time, within 1%. A planner may
drive any profile inside those. Train: UDDS and WLTC. Validation: HWFET.
Test: US06.

**What the task leaves out is other traffic.** Where the cycle slowed
without stopping, a planner here is free not to. So a saving against the
cycle is a saving against a driver in traffic, by a planner on an empty
road. It is an upper bound on what planning buys, not an estimate of it.

## 2. The arms

| Arm | What it is |
|---|---|
| cycle as driven | the reference: the cycle's own trace |
| classical, whole route | dynamic programming over every 10 m of the route, speed grid 0.5 m/s, with a price on time found by bisection so that it arrives on time |
| classical, 300 m ahead | the same, planning 300 m, driving 40 m, planning again |
| 300 m ahead + learned terminal cost | the same, with a network's estimate of what the rest of the route costs from the speed the 300 m ends at |
| student policy | a network that names the next speed directly; no optimisation at run time |

Both networks are 7 inputs, two layers of 48, 2,785 parameters, trained on the
classical planner's solutions for the two training routes at ten prices on
time (1,361,237 node-and-speed rows). Neither sees more of the route
than the limit up to 400 m ahead and the distance to the next stop. Both are
guarded by arithmetic: a speed from which the stops and limits ahead cannot
be met inside the braking bound is never offered to either.

Every profile is driven through the plant with the speed loop and the rule
energy manager. The energy below is the plant's, on the comparable scale.

## 3. Test route (US06, 12.89 km, arrival 600 s within 6 s)

| Arm | Wh/km | Saving | Arrival, s | Top speed, m/s | Peak current, A | Bounds broken | One plan of the route, s |
|---|---|---|---|---|---|---|---|
| cycle as driven | 190.47 | +0.0% | 600.1 | 35.9 | 257 | defines them |  |
| classical, whole route | 170.58 | +10.4% | 598.9 | 26.5 | 319 | 0 | 0.017 |
| classical, 300 m ahead | 172.44 | +9.5% | 596.6 | 26.0 | 340 | 0 | 0.166 |
| 300 m ahead + learned terminal cost | 170.65 | +10.4% | 602.9 | 27.5 | 334 | 0 | 0.186 |
| student policy | 190.41 | +0.0% | 600.8 | 33.5 | 323 | 0 | 0.032 |

## 4. Validation route (HWFET)

| Arm | Wh/km | Saving | Arrival, s | Top speed, m/s | Peak current, A | Bounds broken | One plan of the route, s |
|---|---|---|---|---|---|---|---|
| cycle as driven | 153.90 | +0.0% | 765.1 | 26.8 | 91 | defines them |  |
| classical, whole route | 152.07 | +1.2% | 764.4 | 24.5 | 172 | 0 | 0.024 |
| classical, 300 m ahead | 152.70 | +0.8% | 761.9 | 24.0 | 167 | 0 | 0.171 |
| 300 m ahead + learned terminal cost | 152.28 | +1.1% | 764.8 | 24.0 | 167 | 0 | 0.196 |
| student policy | 153.42 | +0.3% | 764.2 | 25.0 | 179 | 0 | 0.032 |

## 5. What it shows

1. **On the aggressive route the classical planner uses 10.4% less energy
   than the cycle as driven**, making the same stops and arriving at the
   same time. On the steady highway route it uses 1.2% less: there was
   little in that cycle to smooth.
2. **Seeing only 300 m costs about a point** (9.5% against 10.4%).
3. **The learned terminal cost gives that point back** (10.4% on test, 1.1%
   against 1.2% on validation). This is the plan's architecture A8 doing
   what it was proposed for: a short-horizon optimiser with a learned
   estimate of the rest.
4. **The student policy saves nothing on the test route** (0.0%) and 0.3% on
   validation. It keeps every bound, because the guard makes it, and it
   arrives on time, because the price on time is searched for it; but its
   choice of speed is no better than the driver's. It reaches a top speed of
   33.5 m/s where the planners stay under 27.5.
5. **The planners draw a higher peak current than the cycle** (319 to 340 A
   against 257 A on test, 167 to 179 A against 91 A on validation). Energy
   fell; peak current rose. Which part of the profiles does it was not
   examined, and a current bound was not part of the task.

## 6. Limits on these numbers

- No traffic, as section 1 says. This is the largest caveat.
- The arms do not arrive at exactly the same second: 596.6 to 602.9 s on
  test. At the classical arm's price on time (12.7 kW) a second is worth
  3.5 Wh, so the 4 s between the classical and terminal-cost arms is about
  14 Wh of the 2199 Wh drive, 0.6%. The ordering of the two
  is inside that; their distance from the cycle and from the student is not.
- One training seed, one test route. Flat road.
- The planner's own model of the car chose the profiles; it does not model
  the battery. The reported energy does, because it comes from the plant.
- Planning time is Python on the laptop: 0.19 s for all 323 replans of the
  route with the terminal cost. Nothing was ported to the board and no
  on-chip time or memory is claimed.

## 7. The P7 gate

P7 (a planner on a host or in the cloud, sending buffered speed segments) is
to be run only if extra look-ahead or host computation has shown value.
Neither has: the look-ahead gap is closed by the learned terminal cost on
the local planner, and the planning time measured does not call for a host.
Recorded as skipped in `docs/week13-a7-decision.json`, with what would
reopen it: route information the board cannot hold, such as live traffic.

## 8. Not done

- Other traffic, signals, or a lead vehicle.
- A second seed, grades, other routes.
- Any board run of a planner, and its cost on the chip.
- A Jev or other hosted adviser for the planner: not purchased, and the
  gate in section 7 was not met.
