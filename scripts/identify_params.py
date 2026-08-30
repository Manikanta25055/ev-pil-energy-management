# scripts/identify_params.py
"""Identify c_rr, cd and r0 by matching simulated battery power to logged power.

Only these three are fitted. Everything else is a published specification, so
fitting it would trade a citable number for an uncitable one.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import least_squares

from evpil.data.i3_loader import load_all_trips
from evpil.data.splits import Split, apply_split
from evpil.plant.auxiliary import fit_auxiliary
from evpil.plant.battery import BatteryParams
from evpil.plant.motor import MotorParams
from evpil.plant.params import VehicleParams
from evpil.plant.plant import Plant
from evpil.plant.regen import RegenParams

# Paste the real mapping recorded in Task 8 Step 1.
MAPPING: dict[str, str] = {}

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
    capacity_ah=60.0,        # nameplate cell capacity, 96s [R3]
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
    "battery": "96s, 360 V nominal, 60 Ah Samsung NCA prismatic cells, 21.6 kWh "
               "gross / 18.8 kWh usable [R3]. r0 identified; OCV curve, RC "
               "branch and current limits are ASSUMPTIONS (see CAVEATS)",
    "motor": "125 kW / 250 Nm hybrid-synchronous machine [R1][R2]. The "
             "efficiency MAP is a representative PMSM surface, not measured "
             "(see CAVEATS)",
    "regen": "ENGINEERING ASSUMPTION: 50 kW regenerative ceiling. BMW does not "
             "publish a figure for the I01",
    "aux": "fitted from the heating-circuit channel, "
           "evpil.plant.auxiliary.fit_auxiliary",
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
 4. capacity_ah is the 60 Ah NAMEPLATE. If the dataset's SoC channel is
    referenced to USABLE capacity (18.8/21.6 = 87%), the correct value is
    ~52.2 Ah with a [0, 1] window instead. Resolve this at G2: a systematic
    SoC drift of roughly 13% is the signature of getting it wrong.
 5. The OCV curve below is a representative 96s NCA characteristic, NOT an i3
    measurement. It is the single most likely cause of a systematic SoC error
    at G2 (see Task 16 troubleshooting step 4).
"""


def build_params(c_rr: float, cd: float, r0: float, aux) -> VehicleParams:
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
        torque_axis_nm=(0.0, 62.5, 125.0, 250.0),
        speed_axis_radps=(0.0, 300.0, 700.0, 1151.0),
        # Representative PMSM efficiency surface -- ASSUMPTION, see CAVEATS.
        efficiency_grid=np.array([
            [0.70, 0.82, 0.85, 0.83],
            [0.78, 0.91, 0.93, 0.90],
            [0.80, 0.93, 0.94, 0.91],
            [0.76, 0.90, 0.91, 0.88],
        ]),
        torque_max_nm=PUBLISHED["torque_max_nm"],
        # 150 km/h limited [R1] = 41.67 m/s; omega_motor = v/r * G = 1151 rad/s.
        speed_max_radps=1151.0,
        power_max_w=PUBLISHED["power_max_w"],
    )
    return VehicleParams(
        mass_kg=PUBLISHED["mass_kg"], c_rr=c_rr, cd=cd,
        frontal_area_m2=PUBLISHED["frontal_area_m2"],
        wheel_radius_m=PUBLISHED["wheel_radius_m"],
        gear_ratio=PUBLISHED["gear_ratio"],
        drivetrain_eta=PUBLISHED["drivetrain_eta"],
        battery=battery, motor=motor,
        regen=RegenParams(power_limit_w=50000.0), aux=aux,
        citations=CITATIONS,
    )


def simulate_trip(params: VehicleParams, trip: pd.DataFrame) -> np.ndarray:
    """Replay a trip's logged speed profile and return simulated battery power.

    Torque is inverted from the logged acceleration rather than commanded, so
    this isolates the plant's power model from any controller behaviour.
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
                         frontal_area_m2=params.frontal_area_m2)
        f = load.tractive_n
        if f >= 0.0:
            torque = f * params.wheel_radius_m / (params.gear_ratio * params.drivetrain_eta)
        else:
            torque = f * params.wheel_radius_m * params.drivetrain_eta / params.gear_ratio

        st = replace_speed(st, v)
        res = plant.step(st, torque_nm=torque, regen_blend=1.0, p_limit_w=1e9,
                         grade_rad=grade, t_ambient_c=float(trip.t_ambient_c.iloc[k]),
                         dt_s=dt)
        out_p[k] = res.p_batt_w
        st = res.state

    return out_p


def replace_speed(state, v_mps: float):
    """Pin the simulated speed to the logged value so errors cannot accumulate."""
    from dataclasses import replace
    return replace(state, v_mps=v_mps)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/raw/i3")
    ap.add_argument("--splits", default="data/splits.json")
    ap.add_argument("--out", default="data/i3_params.json")
    args = ap.parse_args()

    sp = json.loads(Path(args.splits).read_text())
    df = load_all_trips(Path(args.data), MAPPING)
    train, _, _ = apply_split(df, Split(sp["train"], sp["val"], sp["test"]))

    aux = fit_auxiliary(train.t_ambient_c.to_numpy(), train.p_aux_w.to_numpy())
    print(f"auxiliary fit: {aux}")

    # Fit on a subset of training trips: identification does not need all of
    # them, and the rest stay available as an independent check.
    trips = sorted(train.trip_id.unique())[:8]
    subsets = [train[train.trip_id == t].reset_index(drop=True) for t in trips]

    def residuals(x: np.ndarray) -> np.ndarray:
        c_rr, cd, r0 = x
        params = build_params(c_rr, cd, r0, aux)
        parts = []
        for trip in subsets:
            sim = simulate_trip(params, trip)
            obs = (trip.v_batt_v * trip.i_batt_a).to_numpy()
            parts.append((sim - obs) / 1000.0)     # kW, to keep the scale sane
        return np.concatenate(parts)

    x0 = np.array([0.010, 0.29, 0.05])
    result = least_squares(
        residuals, x0,
        bounds=([0.004, 0.15, 0.01], [0.025, 0.45, 0.20]),
        verbose=2, xtol=1e-8,
    )
    c_rr, cd, r0 = (float(v) for v in result.x)

    rmse_kw = float(np.sqrt(np.mean(result.fun ** 2)))
    print(f"\nc_rr = {c_rr:.5f}\ncd   = {cd:.5f}\nr0   = {r0:.5f}")
    print(f"training residual RMSE = {rmse_kw:.3f} kW")

    Path(args.out).write_text(json.dumps({
        "identified": {"c_rr": c_rr, "cd": cd, "r0_ohm": r0},
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
