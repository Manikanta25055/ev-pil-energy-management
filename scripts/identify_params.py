# scripts/identify_params.py
"""Identify c_rr, cd and r0 by matching simulated battery power to logged power.

Only these three are fitted. Everything else is a published specification, so
fitting it would trade a citable number for an uncitable one.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import least_squares

from evpil.data.eligibility import eligible_trip_ids
from evpil.data.i3_loader import I3_ARCHIVE, I3_MAPPING, load_all_trips
from evpil.data.splits import Split, apply_split
from evpil.plant.auxiliary import AuxParams, fit_auxiliary
from evpil.plant.battery import BatteryParams
from evpil.plant.motor import MotorParams
from evpil.plant.motor_id import identify_efficiency_grid
from evpil.plant.params import VehicleParams
from evpil.plant.plant import Plant
from evpil.plant.regen import RegenParams

# The real mapping, read off the archive files and recorded in
# docs/dataset-provenance.md. It lives in evpil.data.i3_loader beside the
# dialect that describes the rest of the archive's quirks; re-exported here
# because the validation harness imports it from this module.
MAPPING = I3_MAPPING
DIALECT = I3_ARCHIVE


def load_eligible(root) -> "pd.DataFrame":
    """Load the trips that pass the eligibility rule, and only those."""
    return load_all_trips(root, MAPPING, DIALECT,
                          trip_ids=eligible_trip_ids(root))

# ---------------------------------------------------------------------------
# BMW i3 (I01, 60 Ah, 2013-2017) parameters.
#
# NOTE: this is the ORIGINAL i3 (I01), not the 2026 i3 sedan (NA0), which is a
# different vehicle entirely. The dataset is 2014 I01.
#
# Three parameters are deliberately NOT fixed here: c_rr, cd and r0_ohm are
# identified by least squares below, because they vary with tyre, load and cell
# age more than any published figure can capture.
#
# Sources are listed in REFERENCES at the bottom of this module.
# ---------------------------------------------------------------------------
PUBLISHED = dict(
    mass_kg=1270.0,          # 1195 kg DIN kerb [R1] + 75 kg driver [R6]
    frontal_area_m2=2.38,    # CdA 0.690 / Cd 0.29 [R4] -- see CAVEATS
    wheel_radius_m=0.3498,   # 155/70 R19: (482.6 + 2*108.5)/2 mm [R5]
    gear_ratio=9.665,        # single-speed reduction [R2]
    drivetrain_eta=0.95,     # ASSUMPTION, not a published figure -- see CAVEATS
    capacity_ah=61.7,        # MEASURED by Coulomb counting, see [R9]
    power_max_w=125000.0,    # 125 kW / 170 hp [R1][R2]
    torque_max_nm=250.0,     # 250 Nm from standstill [R1][R2]
)

CITATIONS = {
    "mass_kg": "BMW Group PressClub, 'The BMW i3' technical data: 1195 kg DIN "
               "kerb weight [R1]; +75 kg driver per EU kerb convention [R6]",
    "c_rr": "identified by least squares against training trips, "
            "scripts/identify_params.py",
    "cd": "identified by least squares against training trips, "
          "scripts/identify_params.py; initial value 0.29 (BEV) [R1][R4]",
    "frontal_area_m2": "derived as CdA/Cd = 0.690/0.29 [R4]. ASSUMPTION-GRADE "
                       "source (enthusiast forum); low risk because the fitted "
                       "cd absorbs error in the CdA product",
    "wheel_radius_m": "geometric radius of the standard 155/70 R19 tyre [R5]",
    "gear_ratio": "single-speed reduction gear, 9.665:1 [R2]",
    "drivetrain_eta": "ENGINEERING ASSUMPTION: 0.95, typical single-speed "
                      "reduction gear. Not a published BMW figure",
    "battery": "96s, 360 V nominal, Samsung NCA prismatic cells, 21.6 kWh "
               "gross / 18.8 kWh usable [R3]. capacity_ah is MEASURED at "
               "61.7 Ah by Coulomb counting against the logged SoC channel "
               "[R9]. r0 identified; OCV curve, RC branch and current limits "
               "are ASSUMPTIONS (see CAVEATS)",
    "motor": "125 kW / 250 Nm hybrid-synchronous machine [R1][R2]. The "
             "efficiency map is IDENTIFIED from the archive's own logged motor "
             "torque and battery power on training trips, "
             "evpil.plant.motor_id.identify_efficiency_grid [R8]",
    "regen": "ENGINEERING ASSUMPTION: 50 kW regenerative ceiling. BMW does not "
             "publish a figure for the I01",
    "aux": "k_heat_w_per_c fitted from the heating-circuit channel, "
           "evpil.plant.auxiliary.fit_auxiliary; p_base_w identified against "
           "logged battery power, scripts/identify_params.py, because the "
           "archive does not log the 12 V DC-DC load; k_cool_w_per_c NOT "
           "IDENTIFIED -- no eligible trip is warmer than the cabin setpoint",
    "rot_mass_factor": "identified by least squares against training trips, "
                       "scripts/identify_params.py. Standard rotational mass "
                       "factor of vehicle longitudinal dynamics [R7]",
}

REFERENCES = """
[R1] BMW Group PressClub, "The BMW i3", global press kit, 2013.
     https://www.press.bmwgroup.com/global/article/detail/T0148284EN/the-bmw-i3
     -- 125 kW / 250 Nm; Cd 0.29 (BEV); DIN kerb weight 1195 kg.
[R2] Green Car Congress, "More details on BMW's i3; electric and connected",
     2013-07-10. https://www.greencarcongress.com/2013/07/bmwi3-20130710.html
     -- single-speed transmission, 9.665:1 reduction.
[R3] Battery Design, "2013 BMW i3 - Battery Design".
     https://www.batterydesign.net/bmw-i3-2/
     -- 96 cells in series, 360 V nominal, 60 Ah Samsung NCA prismatic,
        21.6 kWh gross / 18.8 kWh usable.
[R4] InsideEVs / EcoModder community aerodynamic data: CdA 0.690 m2 (BEV),
     0.710 m2 (REx). ASSUMPTION-GRADE SOURCE.
[R5] Wheel-Size.com, BMW i3 (2013-2022) tyre fitment: 155/70 R19 standard.
     https://www.wheel-size.com/tire/iso-metric-155-70-R-19/bmw/i3/2013-2022/
[R6] EU kerb-weight convention (Directive 92/21/EEC): DIN kerb + 75 kg driver.
[R7] Standard rotational mass factor: the inertial force is m(1+e)a, because
     accelerating the vehicle also spins up the wheels, the reduction gear and
     the rotor. See Ehsani, Gao and Emadi, "Modern Electric, Hybrid Electric
     and Fuel Cell Vehicles", and Guzzella and Sciarretta, "Vehicle Propulsion
     Systems". Typical passenger-car values are 0.05-0.15; for a single-speed
     EV the rotor's inertia reflected through a 9.665:1 reduction is the
     dominant contribution.
[R9] Pack capacity measured from this archive: for every trip with more than
     3 pp of SoC change, the time integral of logged battery current divided
     by the logged SoC change. Median 61.7 Ah across 25 trips, 10th-90th
     percentile 61.5-62.0 Ah. See docs/g2-plant-validation.md.
[R8] Efficiency map identified from this archive: shaft power (logged Motor
     Torque times wheel-derived speed) over inverter electrical power (logged
     battery power less the auxiliary load), median per grid cell, training
     trips only. Replaces the representative surface previously assumed.

CAVEATS -- read before trusting any downstream number:

 1. frontal_area_m2 rests on a forum-sourced CdA. Risk is low: the drag term is
    0.5*rho*cd*A*v^2, and cd is fitted, so the identification calibrates the
    CdA PRODUCT against real logs. An error in A is absorbed by cd.
 2. drivetrain_eta, the motor efficiency map, the RC branch (r1, c1), the
    current limits and the regen ceiling are ENGINEERING ASSUMPTIONS. BMW does
    not publish them. They are flagged as such in CITATIONS and must be
    described as assumptions in the paper, never as specifications.
 3. wheel_radius_m is the geometric, not dynamic, rolling radius (typically
    2-3% smaller under load). This largely cancels: simulate_trip inverts
    force to torque with the same radius the plant uses to convert back, so
    P_mech = F*v/eta is radius-independent. It survives only via the omega
    argument to the efficiency map, a second-order effect.
 4. RESOLVED AT G2. capacity_ah was the 60 Ah nameplate, with an open
    question over whether the archive's SoC channel is referenced to usable
    capacity (~52.2 Ah) instead. Coulomb counting settles it: integrating the
    logged current over the logged SoC change gives 61.7 Ah (p10 61.5,
    p90 62.0 over 25 trips). The channel tracks NAMEPLATE capacity, not the
    usable window, and the true figure is 2.8% above nameplate -- consistent
    with a pack whose cells slightly exceed their rating. The 52.2 Ah
    alternative is wrong and is discarded. capacity_ah is now the measurement.
 5. The OCV curve below is a representative 96s NCA characteristic, NOT an i3
    measurement. It is the single most likely cause of a systematic SoC error
    at G2 (see Task 16 troubleshooting step 4).
"""


# Fallback efficiency surface, used only until the map is identified from the
# archive. It is 7.4% pessimistic against the measured one, so it is a starting
# point, not a result. See evpil.plant.motor_id.
ASSUMED_EFFICIENCY_GRID = np.array([
    [0.70, 0.82, 0.85, 0.83],
    [0.78, 0.91, 0.93, 0.90],
    [0.80, 0.93, 0.94, 0.91],
    [0.76, 0.90, 0.91, 0.88],
])
TORQUE_AXIS = (0.0, 62.5, 125.0, 250.0)
SPEED_AXIS = (0.0, 300.0, 700.0, 1151.0)


def build_params(c_rr: float, cd: float, r0: float, aux,
                 rot_mass_factor: float = 0.0,
                 efficiency_grid: np.ndarray | None = None) -> VehicleParams:
    battery = BatteryParams(
        capacity_ah=PUBLISHED["capacity_ah"],
        # Representative 96s NCA pack curve: 3.20 V/cell empty to 4.15 V/cell
        # full. ASSUMPTION -- see CAVEATS note 5.
        ocv_soc_points=(0.0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0),
        ocv_volts=(307.2, 336.0, 348.5, 357.1, 371.5, 388.8, 398.4),
        r0_ohm=r0, r1_ohm=0.01, c1_farad=2000.0,
        # 125 kW at 360 V nominal is ~347 A. Charge limit and regen ceiling are
        # assumptions (CAVEATS note 2).
        i_discharge_max_a=350.0, i_charge_max_a=150.0,
        # 18.8 kWh usable of 21.6 kWh gross is an 87% window.
        soc_min=0.07, soc_max=0.94,
        r0_temp_coeff_per_c=-0.004, t_ref_c=25.0,
    )
    motor = MotorParams(
        torque_axis_nm=TORQUE_AXIS,
        speed_axis_radps=SPEED_AXIS,
        efficiency_grid=(ASSUMED_EFFICIENCY_GRID if efficiency_grid is None
                         else np.asarray(efficiency_grid, dtype=float)),
        torque_max_nm=PUBLISHED["torque_max_nm"],
        # The published 150 km/h limiter [R1] implies 1151 rad/s, but the
        # archive's own speed channel reaches 152.3 km/h (1169 rad/s) on 3
        # trips: speedometers over-read, the geometric wheel radius is not the
        # dynamic one, and a limiter can be overrun downhill. The envelope is
        # therefore set from the data the plant has to reproduce, with a 2%
        # margin, rather than from the brochure figure. Anything else makes the
        # model undefined exactly where the vehicle draws its peak power.
        speed_max_radps=1192.0,
        power_max_w=PUBLISHED["power_max_w"],
    )
    return VehicleParams(
        mass_kg=PUBLISHED["mass_kg"], c_rr=c_rr, cd=cd,
        frontal_area_m2=PUBLISHED["frontal_area_m2"],
        wheel_radius_m=PUBLISHED["wheel_radius_m"],
        gear_ratio=PUBLISHED["gear_ratio"],
        drivetrain_eta=PUBLISHED["drivetrain_eta"],
        rot_mass_factor=rot_mass_factor,
        battery=battery, motor=motor,
        regen=RegenParams(power_limit_w=50000.0), aux=aux,
        citations=CITATIONS,
    )


def simulate_trip(params: VehicleParams, trip: pd.DataFrame,
                  use_logged_aux: bool = True) -> np.ndarray:
    """Replay a trip's logged speed profile and return simulated battery power.

    Torque is inverted from the logged acceleration rather than commanded, so
    this isolates the plant's power model from any controller behaviour.

    `use_logged_aux` feeds the archive's measured auxiliary load in as an
    input. That is deliberate: the HVAC draw is set by the weather, the cabin
    and the driver's temperature dial, none of which the powertrain determines.
    Predicting it from ambient temperature is a separate forecasting problem
    (and a poorly conditioned one -- see the aux R^2 reported by main), so
    folding it into this comparison would test two models at once and localise
    neither. Set False to score the fully autonomous plant instead.
    """
    plant = Plant(params)
    st = plant.reset(soc0=float(trip.soc_frac.iloc[0]),
                     t_ambient_c=float(trip.t_ambient_c.iloc[0]),
                     t_batt_c=float(trip.t_batt_c.iloc[0]))

    out_p = np.empty(len(trip))
    t = trip.t_s.to_numpy()

    for k in range(len(trip)):
        dt = float(t[k] - t[k - 1]) if k > 0 else float(t[1] - t[0])
        v = float(trip.v_mps.iloc[k])
        a = float(trip.a_mps2.iloc[k])
        grade = float(trip.grade_rad.iloc[k])

        # Force needed to follow the logged profile, converted to motor torque.
        from evpil.plant.longitudinal import road_load
        load = road_load(v_mps=v, a_mps2=a, grade_rad=grade,
                         mass_kg=params.mass_kg, c_rr=params.c_rr, cd=params.cd,
                         frontal_area_m2=params.frontal_area_m2,
                         rot_mass_factor=params.rot_mass_factor)
        f = load.tractive_n
        if f >= 0.0:
            torque = f * params.wheel_radius_m / (params.gear_ratio * params.drivetrain_eta)
        else:
            torque = f * params.wheel_radius_m * params.drivetrain_eta / params.gear_ratio

        st = replace_speed(st, v)
        res = plant.step(st, torque_nm=torque, regen_blend=1.0, p_limit_w=1e9,
                         grade_rad=grade, t_ambient_c=float(trip.t_ambient_c.iloc[k]),
                         dt_s=dt,
                         p_aux_w=(float(trip.p_aux_w.iloc[k]) + params.aux.p_base_w
                                  if use_logged_aux else None))
        out_p[k] = res.p_batt_w
        st = res.state

    return out_p


def replace_speed(state, v_mps: float):
    """Pin the simulated speed to the logged value so errors cannot accumulate."""
    from dataclasses import replace
    return replace(state, v_mps=v_mps)


def _measure_base_load(train: pd.DataFrame, min_samples: int = 300) -> float:
    """The unlogged 12 V / DC-DC draw, read off the stationary samples.

    With the vehicle at rest there is no traction power, so battery power is
    the logged auxiliary load plus whatever the archive does not log. Taking
    the median per trip and then across trips keeps one long idle from
    dominating.
    """
    per_trip = []
    for tid, t in train.groupby("trip_id"):
        rest = t[t.v_mps < 0.05]
        if len(rest) < min_samples:
            continue
        p = (rest.v_batt_v * rest.i_batt_a).to_numpy()
        per_trip.append(float(np.median(p - rest.p_aux_w.to_numpy())))
    if not per_trip:
        raise ValueError("no training trip had enough stationary samples")
    return float(np.median(per_trip))


def _identify_map(root: Path, train_ids: list[str], train: pd.DataFrame, aux):
    """Gather (torque, speed, inverter power) over training trips and fit the map.

    Motor torque is read from the raw archive rather than the canonical frame:
    it is a measured channel the canonical schema does not carry, and it is
    needed here precisely because it is independent of our own dynamics.
    """
    tq_all, om_all, pe_all = [], [], []
    for tid in train_ids:
        raw = pd.read_csv(root / f"{tid}.csv", sep=";", encoding="cp1252",
                          low_memory=False)
        raw.columns = [c.strip() for c in raw.columns]
        t = train[train.trip_id == tid].reset_index(drop=True)
        tq = pd.to_numeric(raw["Motor Torque [Nm]"], errors="coerce").to_numpy()
        if len(tq) != len(t):
            continue
        omega = (t.v_mps.to_numpy() / PUBLISHED["wheel_radius_m"]) * PUBLISHED["gear_ratio"]
        p_elec = (t.v_batt_v * t.i_batt_a).to_numpy() - t.p_aux_w.to_numpy() - aux.p_base_w
        tq_all.append(tq); om_all.append(omega); pe_all.append(p_elec)

    return identify_efficiency_grid(
        np.concatenate(tq_all), np.concatenate(om_all), np.concatenate(pe_all),
        TORQUE_AXIS, SPEED_AXIS,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/raw/i3")
    ap.add_argument("--splits", default="data/splits.json")
    ap.add_argument("--out", default="data/i3_params.json")
    args = ap.parse_args()

    sp = json.loads(Path(args.splits).read_text())
    df = load_eligible(Path(args.data))
    train, _, _ = apply_split(df, Split(sp["train"], sp["val"], sp["test"]))

    # k_heat comes from the heating-circuit channel. p_base_w cannot: the
    # archive logs the heater and the compressor but not the 12 V DC-DC load,
    # so the channel's own base is genuinely zero while the vehicle still
    # draws power at rest. It is identified below against battery power
    # instead, which is the only place that load is visible.
    aux_channel = fit_auxiliary(train.t_ambient_c.to_numpy(),
                                train.p_aux_w.to_numpy())
    print(f"auxiliary fit from heating channel: {aux_channel}")
    if aux_channel.k_cool_w_per_c == 0.0:
        warm = float((train.t_ambient_c > aux_channel.t_setpoint_c).mean())
        print(f"  NOTE: k_cool_w_per_c is NOT identified "
              f"({warm*100:.1f}% of training samples are above the "
              f"{aux_channel.t_setpoint_c:.0f} C setpoint). The plant must not "
              f"be used above the setpoint until it is.")

    # The 12 V / DC-DC load is not logged, but it is directly measurable: when
    # the vehicle is stationary, battery power is the auxiliary load plus this
    # base and nothing else. Measured that way it is 543 W with a p25-p75 of
    # 527-553 W over 18 training trips -- a tight, well-determined constant.
    # Fitting it instead let it drift to 719 W, because a free constant will
    # happily absorb the zero-mean torque-inversion noise it sits next to, and
    # a 176 W error over an hour is 0.18 kWh of energy that never existed.
    # A quantity this measurable should be measured.
    p_base_w = _measure_base_load(train)
    print(f"base load measured at rest: {p_base_w:.0f} W")
    aux = replace(aux_channel, p_base_w=p_base_w)

    # Identify the efficiency map before fitting the chassis parameters. Done
    # the other way round, c_rr and cd would spend themselves compensating for
    # a map that is 7.4% wrong, and come out unphysical.
    grid, counts = _identify_map(Path(args.data), sp["train"], train, aux)
    print("\nmotor efficiency map identified from training trips:")
    for i, row in enumerate(grid):
        print("   tq %6.1f Nm: " % TORQUE_AXIS[i]
              + "  ".join(f"{e:.3f}" for e in row)
              + "   (n = " + ", ".join(f"{c}" for c in counts[i]) + ")")

    # Fit on a subset of training trips: identification does not need all of
    # them, and the rest stay available as an independent check.
    trips = sorted(train.trip_id.unique())[:8]
    subsets = [train[train.trip_id == t].reset_index(drop=True) for t in trips]

    def residuals(x: np.ndarray) -> np.ndarray:
        c_rr, cd, r0, rot = x
        params = build_params(c_rr, cd, r0, aux, rot, grid)
        parts = []
        for trip in subsets:
            sim = simulate_trip(params, trip)
            obs = (trip.v_batt_v * trip.i_batt_a).to_numpy()
            parts.append((sim - obs) / 1000.0)     # kW, to keep the scale sane
        return np.concatenate(parts)

    #                c_rr    cd    r0    rot
    x0 = np.array([0.010, 0.290, 0.050, 0.08])
    lo = np.array([0.004, 0.150, 0.010, 0.00])
    hi = np.array([0.025, 0.450, 0.200, 0.30])
    result = least_squares(residuals, x0, bounds=(lo, hi),
                           x_scale=np.array([0.01, 0.1, 0.05, 0.05]),
                           verbose=2, xtol=1e-10, ftol=1e-10)
    c_rr, cd, r0, rot = (float(v) for v in result.x)

    rmse_kw = float(np.sqrt(np.mean(result.fun ** 2)))
    print(f"\nc_rr             = {c_rr:.5f}")
    print(f"cd               = {cd:.5f}")
    print(f"r0               = {r0:.5f} ohm")
    print(f"rot_mass_factor  = {rot:.5f}")
    print(f"aux p_base_w     = {p_base_w:.1f} W (measured, not fitted)")
    at_bound = [n for n, v, l, h in zip(
        ("c_rr", "cd", "r0", "rot_mass_factor"), result.x, lo, hi)
        if abs(v - l) < 1e-9 or abs(v - h) < 1e-9]
    if at_bound:
        print(f"WARNING: parameters pinned at a bound: {at_bound}. "
              f"A bound is doing work the physics should be doing.")
    print(f"training residual RMSE = {rmse_kw:.3f} kW")

    Path(args.out).write_text(json.dumps({
        "identified": {"c_rr": c_rr, "cd": cd, "r0_ohm": r0,
                       "rot_mass_factor": rot},
        "motor_efficiency_grid": grid.tolist(),
        "motor_efficiency_counts": counts.tolist(),
        "motor_torque_axis_nm": list(TORQUE_AXIS),
        "motor_speed_axis_radps": list(SPEED_AXIS),
        "aux": {"p_base_w": aux.p_base_w, "k_heat_w_per_c": aux.k_heat_w_per_c,
                "k_cool_w_per_c": aux.k_cool_w_per_c, "t_setpoint_c": aux.t_setpoint_c},
        "published": PUBLISHED,
        "citations": CITATIONS,
        "fit_trips": trips,
        "train_residual_rmse_kw": rmse_kw,
    }, indent=2))
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
