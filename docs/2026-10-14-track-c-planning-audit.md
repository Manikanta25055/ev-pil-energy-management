# Track C: information access and timing of the five planning arms

Plan: `docs/2026-10-14-paper-validation-addendum-plan.md`, section C. Source
read at the frozen tree `befecb8` (the commit that holds the planner, both
networks and `docs/week13-energy-planner.json`; the JSON's own `commit` field,
`fe48fb3`, predates those files). Everything here is SIMULATED on the host. The
frozen-price replay results are in `docs/2026-10-14-planner-crossing-replay.json`
(section "Replay" below).

## Information access

Node spacing 10 m (`route.DS_M`); learned look-ahead nodes (0, 10, 20, 40)
(`learned.LOOKAHEAD_NODES`); stop distance capped at 1000 m (`STOP_CAP_M`);
short horizon 30 nodes, replanning every 4 nodes (`HORIZON_NODES`, `apply=4`).

| Arm | Route information used at a decision | Stop information | Feasibility preprocessing | Arrival-price calibration | Execution |
|---|---|---|---|---|---|
| Tracked cycle | The cycle's own time trace (the route is built from it) | All stops and dwells, as driven | None | None; arrival is the cycle duration | Host: plant, speed loop, rule manager |
| Full-route DP (`classical`) | Every node's limit, stop and dwell, whole route | All stops | Node masks and acceleration bounds over the whole route inside the backward pass | `meet_arrival` bisection on planned time | Same |
| Classical 300 m (`classical_short`) | Limits and stops of the next 300 m; zero terminal cost | Stops within 300 m | Node masks within the horizon only; no route-global mask | Same bisection, own price | Same |
| Learned terminal cost | The 300 m horizon, plus at its endpoint k+30: speed, limits at k+30, +100, +200 and +400 m (up to 700 m from the decision node), next-stop distance from the endpoint capped at 1000 m (stop information up to 1300 m) | Stops within 1300 m (as one capped distance) | `drivable()` mask at the endpoint: a backward feasibility pass over the whole remaining route; undrivable speeds cost infinity | Same bisection, own price; network trained at ten fixed prices | Same |
| Student | At each node: speed, limits at +0, +100, +200 and +400 m, next-stop distance capped at 1000 m, price | Next stop within 1000 m | Next speed restricted to `_allowed` pairs and `drivable()` at the next node (route-global feasibility pass) | Same bisection, own price | Same |

Consequences:

- A 300 m classical horizon is not an equal-preview control for the terminal
  cost arm, and a 700 m classical horizon would not be either: the learned
  endpoint sees limits to 700 m, a stop cue to 1300 m, and a feasibility mask
  computed from the whole remaining route.
- The full-route DP solves the planner's own model (a flat-route energy table
  of road load, motor map, drivetrain, regeneration limit and auxiliary load,
  constant acceleration between nodes, no battery resistance or SOC
  dependence). It is a feasible planning reference evaluated through the
  plant, not a certified optimum of the physical plant.
- The corridor planner (`docs/week14-corridor-planner.json`) is a different
  construction and is not a nested feasible set of the empty-road planner.

## Timing and distance

- `arrival_s` in the stored table is `route.planned_time_s` of the node
  profile (segment times plus dwell), not the time at which the driven trace
  crosses the target distance. For the tracked cycle it is the cycle duration.
- The driven trace (`route.profile_to_cycle`) adds 1 s of standstill at the
  end and carries sub-sample rounding between segments, so trace duration,
  planned time and crossing time differ.
- Stored planned arrival on US06 (cycle 600.1 s, tolerance 6.0 s): classical
  -1.18 s, classical 300 m -3.51 s, terminal cost +2.77 s, student +0.66 s. On
  HWFET (765.1 s, tolerance 7.65 s): -0.71, -3.18, -0.33 and -0.93 s.
- The terminal-cost arm planned to arrive 3.94 s later than the full-route DP
  and 6.27 s later than the classical 300 m arm on US06. Its 10.41% saving
  against the DP's 10.44% is therefore not at matched time, and the gap it
  closed against the 300 m arm (9.46%) mixes the learned cost with 6.3 s of
  extra planned time and with information the 300 m arm did not have.
- Final distance: the planned arms drive 12.8900 km on US06 and 16.5100 km on
  HWFET (the route length rounds to whole 10 m nodes); the tracked cycle drives
  12.8876 and 16.5066 km. Energy per km uses each arm's own distance.
- `route.violations()` counts planned-node-profile diagnostics. All four
  planned arms show zero; the tracked cycle's profile snapped to nodes shows
  one over-brake segment and 6.49 s outside the arrival tolerance on US06,
  an artefact of snapping. These counts do not establish closed-loop speed-
  limit or stop compliance, which was not evaluated.

## What the paper may say

- The planning savings are simulated, empty-road, and against the cycle as
  driven; the corridor is a recorded-drive constraint surrogate, not traffic.
- The isolated reading "the learned terminal cost closed the gap left by the
  short horizon" is removed: neither the information nor the planned time is
  matched. The terminal-cost result is reported as a planning diagnostic with
  its information and arrival difference stated.
- The student's 0.03% on US06 stands as measured in simulation; it uses less
  preview than the terminal-cost arm but a route-global feasibility mask.

## Replay

See `docs/2026-10-14-planner-crossing-replay.json` and the paragraph appended
below after the run.
