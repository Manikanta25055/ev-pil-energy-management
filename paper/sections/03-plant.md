# VEHICLE MODEL AND DATA {#sec:plant}

Every controller in this study acts on a simulated vehicle, so an error in that vehicle is an error in every comparison that follows.

## Data

The model was identified and validated on a public archive of 70 trips of a BMW i3 [@i3data]. Each trip logs speed, battery voltage and current, state of charge (SOC), temperatures, elevation and heater power every 0.1 s. Eligibility tests were fixed before any fit: SOC present, no charging, and the two heater-power channels present and in agreement. Of the 70 trips, 33 passed; the summer trips failed, so the validated envelope is winter only, with mean ambient temperature from -3.3 to 10.2 °C.

The 33 trips were split by trip into 19 for identification, 7 for validation and 7 sealed for a final test that has not been opened. Consecutive samples of one drive are near copies, so a row split would put the same moment on both sides.

The Vehicle Energy Dataset (VED) [@ved] served for a transfer check. Its battery-electric subset is three 2013 Nissan Leaf vehicles in Ann Arbor, with 504 trips. The controller campaigns use the dynamometer schedules UDDS (1369 s, 11.99 km), HWFET (765 s, 16.51 km) and US06 (600 s, 12.89 km) [@epacycles].

## Longitudinal Model

The force balance (@eq:plant-force) sets the acceleration.

$$ m(1+e)\dot{v} = F_{t} - m g c_{rr}\cos\theta - \tfrac{1}{2}\rho c_{d} A v^{2} - m g \sin\theta $$ {#eq:plant-force}

Here $m$ is the mass, $e$ the rotational mass factor, $v$ the speed, $F_{t}$ the wheel force, $c_{rr}$ and $c_{d}$ the rolling and drag coefficients, $A$ the frontal area, $\rho$ the air density and $\theta$ the grade. The wheel force follows from the motor torque $T$ through the gear ratio $g_{r}$, wheel radius $r_{w}$ and drivetrain efficiency $\eta_{d}$.

$$ P_{e} = T\omega/\eta(T,\omega) \;\; (T\omega > 0), \qquad P_{e} = T\omega\,\eta(T,\omega) \;\; (T\omega < 0) $$ {#eq:plant-motor}

The electrical power $P_{e}$ uses the motor speed $\omega = v g_{r}/r_{w}$ and an efficiency $\eta$ from a map over torque and speed, identified on training trips only.

$$ V_{t} = V_{oc}(s) - i R_{0} - v_{1}, \qquad \dot{s} = -\frac{i}{3600\,C_{b}}, \qquad \dot{v}_{1} = \frac{i}{C_{1}} - \frac{v_{1}}{R_{1}C_{1}} $$ {#eq:plant-battery}

The battery is a first-order equivalent circuit with terminal voltage $V_{t}$, open-circuit voltage $V_{oc}$ at SOC $s$, discharge current $i$, series resistance $R_{0}$, which the code scales with temperature by -0.4% per °C about 25 °C, branch voltage $v_{1}$ across $R_{1}C_{1}$ and capacity $C_{b}$. The open-circuit curve, branch values and current limits are assumptions.

$$ P_{a} = P_{0} + k_{h}\max(0, T_{s} - T_{a}) + k_{c}\max(0, T_{a} - T_{s}) $$ {#eq:plant-aux}

The auxiliary load $P_{a}$ depends on ambient temperature $T_{a}$ about a 21 °C setpoint $T_{s}$, with base load $P_{0}$ (543 W, measured at rest) and slopes $k_{h}$ (127.3 W/°C, fitted) and $k_{c}$. The cooling slope is unidentified, since every eligible trip is colder than the setpoint.

$$ P_{r} = \max\!\left(b\,P_{br},\; -\min(P_{r,max},\, I_{c}(V_{oc} - v_{1}))\right) $$ {#eq:plant-regen}

Regenerative braking returns a fraction $b$ of the braking power $P_{br}$ (negative), limited by an assumed ceiling $P_{r,max}$ of 50 kW and the charge current $I_{c}$; friction brakes take the rest. Table @tab:plant-params lists the main parameters.

Table: tab:plant-params | Main parameters of the i3 model, with the origin of each value. | width=col
| Parameter | Value | Origin |
|---|---|---|
| Mass $m$ | 1270 kg | published kerb mass plus driver |
| Frontal area $A$ | 2.38 m² | from published drag area and an assumed drag coefficient |
| Wheel radius, gear ratio | 0.3498 m, 9.665 | from tyre size; published |
| Motor limits | 250 Nm, 125 kW | published |
| Drivetrain efficiency $\eta_{d}$ | 0.95 | assumed |
| Rolling coefficient $c_{rr}$ | 0.01947 | identified, training trips |
| Drag coefficient $c_{d}$ | 0.2202 | identified, training trips |
| Rotational factor $e$ | 0.1706 | identified, training trips |
| Resistance $R_{0}$ | 0.010 ohm | identified, at lower bound |
| Capacity $C_{b}$ | 61.7 Ah | Coulomb counting of logged data |

## Validation Against Logged Trips

Gate G2 was written before the fit. It replays a held-out trip's logged speed and passes only if every validation trip meets the bounds. The original single criterion pooled three models; applied literally it failed all seven trips and could not say which model was at fault. The one revision the design allowed split it into three parts and kept both original thresholds. Part A: torque inverted from the speed profile within 50% of the logged-torque standard deviation, the only new number. Part B: battery power, driven by logged torque, within 10% of mean absolute power. Part C: terminal SOC within 2 percentage points (pp).

The gate fails on Part C. Parts A and B pass on 7 of 7 trips (worst case 48.6% and 8.3%, medians 27.4% and 7.0%), and Part C passes on 6 of 7, with a median of 0.19 pp. Trip B08 misses the SOC bound, 2.45 pp against 2.00 pp (Fig. @fig:plant-validation); the bound was kept and the miss recorded. Two other trips sit near it at 1.86 and 1.76 pp. The instantaneous battery-power error of the original pooled criterion correlates at -0.85 with a trip's torque spread, which points to noise from differentiating a 10 Hz speed signal.

![fig:plant-validation](paper/figures/fig-plant-validation.png){width=col}
Caption: Terminal SOC error on the seven validation trips against the 2.00 pp bound of gate G2. Trip B08 (hatched) exceeds it. Replay on the host (SIMULATED against logged trips).

B08 over-predicts energy by 10.4%, and its inverted torque is biased by 13.6% of mechanical energy. Across 26 trips this road-load bias runs from -21% to +30% with no trend against speed, distance or temperature, so one fixed parameter set cannot follow wind, tyre pressure and load. B08 sits in the tail of that spread.

The fitted rolling coefficient is 0.01947, while a published coastdown test of a different battery-electric car, a 2013 Nissan Leaf, gives 0.00878 [@inl2013leaf], a ratio of 2.2. A factor of that size between two passenger cars is unlikely to be tyre rolling resistance alone, so the fitted value probably absorbs drivetrain and brake drag, efficiency-map error and unmodelled load. The same holds for $c_{d}$ and $e$: all are lumped loss coefficients that reproduce logged power, and none measures the quantity it is named after.

## Transfer to Other Vehicles

The model was rebuilt around a Leaf and run on 89 VED validation trips (443 of 504 trips were eligible; the 89 VED test trips remain unopened). Arm A carried every i3 parameter across, arm B replaced only the chassis coefficients with the Leaf's coastdown values, and arm C refitted the chassis on VED as the in-domain ceiling. Median trip energy error was 16.9%, 14.4% and 13.4%; 55, 64 and 67 of 89 trips ended within 2 pp of logged SOC. Carrying the i3 coefficients across costs 3.5 points of energy error; the Leaf's measured road load recovers 2.5 of them (SIMULATED against logged trips).

The efficiency map carries over and the chassis coefficients do not, as the 2.2 ratio predicts. The check does not show transfer to electric vehicles in general: it covers three cars of one model in one city, and instantaneous power could not be scored because the noise floor is 77.7% of mean absolute power. Energy error also slopes with temperature in every arm, including arm C, from -15.8% below freezing to +15.6% above 24 °C.

## A Fault in the Power Limit and Its Correction

Each energy manager sends the model a ceiling $P_{lim}$ on battery discharge power. The model applied it only to the bill, $P_{b} = \min(P_{m} + P_{a}, P_{lim})$ with $P_{m}$ the machine power, and computed acceleration from the torque requested before the cap. A controller that lowered the ceiling was charged less and still received the motion it asked for.

Fig. @fig:plant-correction shows one fixed ceiling held over US06 before and after the fix (SIMULATED on the host). Before, a 5 kW ceiling drove all 12.888 km at 8.05 Wh/km with the same 0.0013 m/s tracking error as an open ceiling at 190.39 Wh/km. After, the same ceiling gives 156.16 Wh/km over 4.453 km with 16.15 m/s tracking error, and a 40 kW ceiling gives 189.80 Wh/km against 174.85 before.

![fig:plant-correction](paper/figures/fig-plant-correction.png){width=col}
Caption: A constant battery power ceiling held over US06, before and after the fix. Before, a lower ceiling cut the billed energy and left the distance unchanged; after, it also cuts the distance. SIMULATED on the host.

The fault was found from three oddities in the campaign tables. The learned policy finished below the offline optimum at equal tracking, which should not be possible; its advantage grew with demand; and it vanished on UDDS and HWFET, where demand stays under 40 kW. An earlier explanation, that the policy saved energy by shaving current peaks, had been recorded as inferred and was wrong. A fixed-ceiling sweep with no controller in the loop reproduced the effect.

The fix gives the motor the power the pack delivered less the auxiliary load, reduces torque to match, and computes acceleration from it. A limit that does not bind leaves the outputs unchanged: in the sweep, the arms whose ceiling never binds give the same energy before and after the fix to the last recorded digit. The rule-based energy manager, whose ceiling rarely binds, should not move. On the microcontroller, across 16 valid settings, the corrected rule arm differed from the earlier campaign by +0.07% on average (95% interval -0.03 to +0.17%), 0.46% at worst, against 0.57% at worst between two campaigns that differed only in the day (MEASURED). Its consequence for the comparison with the learned policy is given in Section @sec:ems.
