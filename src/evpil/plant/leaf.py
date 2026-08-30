"""Vehicle parameters for the 2013 Nissan Leaf, the BEV in the VED fleet.

This exists to answer one question: does a plant identified on a BMW i3
transfer to a different battery-electric vehicle, logged by different people,
in a different country, with a different logger? Fitting a model and then
validating it on the same vehicle shows that it fits. It does not show that it
transfers, and transfer is what a reviewer asks about.

The parameters split three ways, and keeping the split visible is the point:

  PUBLISHED  the vehicle's own specification, from an Idaho National Laboratory
             test report on a specific car [L1]
  MEASURED   read out of VED itself, the way pack capacity and the efficiency
             map were read out of the i3 archive
  TRANSFERRED carried over unchanged from the i3 identification. These are the
             parameters under test

Everything in the third group is a hypothesis. If the transfer arm fails and
the measured-chassis arm succeeds, the hypothesis was wrong about the chassis
and right about the powertrain, and the report says so.
"""

from __future__ import annotations

import numpy as np

from evpil.plant.auxiliary import AuxParams
from evpil.plant.battery import BatteryParams
from evpil.plant.motor import MotorParams
from evpil.plant.params import VehicleParams
from evpil.plant.regen import RegenParams

LBF_N = 4.4482216
MPH_MPS = 0.44704

# --- PUBLISHED [L1] ---------------------------------------------------------
CURB_MASS_KG = 3302 * 0.45359237      # delivered curb weight, 3302 lb
DRIVER_KG = 75.0                      # same convention used for the i3
MASS_KG = CURB_MASS_KG + DRIVER_KG
GEAR_RATIO = 7.9377                   # single-speed reduction; [L1] rounds to 7.9
WHEEL_RADIUS_M = (16 * 0.0254 / 2) + (0.205 * 0.55)   # 205/55 R16, unloaded
MOTOR_POWER_W = 80_000.0
MOTOR_TORQUE_NM = 253.0
FRONTAL_AREA_M2 = 2.27                # [L2]

# Coastdown road load from [L1]: F = A + B*v + C*v^2, A in lbf, B in lbf/mph,
# C in lbf/mph^2, measured on a track and matched on a chassis dynamometer.
# This is the Leaf's own measured road load, so it is the honest reference
# against which a transferred c_rr and cd can be judged.
COASTDOWN_A_LBF = 31.911
COASTDOWN_B_LBF_PER_MPH = 0.11588
COASTDOWN_C_LBF_PER_MPH2 = 0.017756
COASTDOWN_MASS_KG = (3302 + 332) * 0.45359237   # curb plus driver and equipment

COASTDOWN_A_N = COASTDOWN_A_LBF * LBF_N
COASTDOWN_C_N = COASTDOWN_C_LBF_PER_MPH2 * LBF_N / MPH_MPS**2
# 141.9 N over 1648 kg, and 2C/rho = 0.659 m^2 of CdA. At the 2.27 m^2 frontal
# area that is Cd 0.29, which is what Nissan published, so the unit conversion
# checks out against something it was not fitted to.
MEASURED_C_RR = COASTDOWN_A_N / (COASTDOWN_MASS_KG * 9.81)     # 0.00878
MEASURED_CD = (2.0 * COASTDOWN_C_N / 1.2) / FRONTAL_AREA_M2    # 0.290

# --- MEASURED from VED ------------------------------------------------------
# Capacity by Coulomb counting: the current integral over the SoC change. 41.9 Ah
# by least squares through the origin over 314 trips (R^2 0.806), and stable at
# 42 Ah whether the trip moved 3 pp of SoC or 20. Nameplate is 66.2 Ah [L1], so
# these five-year-old air-cooled packs read 63% of it. Whether that is
# degradation or a compressed SoC channel does not matter here: the plant uses
# this number only to turn a current integral into SoC, and that ratio is
# exactly what was measured.
CAPACITY_AH = 42.0

# Open-circuit voltage as the zero-current intercept of terminal voltage
# regressed on current inside each 5% SoC bin, which extrapolates out the
# ohmic drop instead of hoping a low-current sample has none. Forced monotonic:
# the raw 0.175 and 0.225 points invert by 0.5 V on a few hundred samples, and
# a non-monotonic OCV curve is unphysical.
OCV_SOC_POINTS = (0.125, 0.175, 0.225, 0.275, 0.325, 0.375, 0.425, 0.475,
                  0.525, 0.575, 0.625, 0.675, 0.725, 0.775, 0.825, 0.875,
                  0.925, 0.975)
OCV_VOLTS = (355.2, 360.3, 360.3, 362.6, 365.2, 367.3, 370.2, 371.8,
             374.3, 375.5, 378.0, 379.6, 380.5, 381.5, 382.6, 383.0,
             385.0, 389.1)

# Slope of the same regression, median over the bins. 0.084 ohm across 96
# series groups is 0.87 milliohm per group, which is what a 2p96s LMO pack of
# this age looks like. The single-sample dV/dI estimator gives 0.001 ohm and is
# wrong: the voltage channel is quantised to 0.5 V, which swamps the step.
MEASURED_R0_OHM = 0.079

MAX_SPEED_MPS = 91.0 * MPH_MPS        # 91.0 mph at the one-mile mark [L1]
SPEED_MAX_RADPS = 1.05 * MAX_SPEED_MPS / WHEEL_RADIUS_M * GEAR_RATIO

REFERENCES = """
[L1] Idaho National Laboratory / Intertek for the U.S. Department of Energy,
     "2013 Nissan Leaf, Advanced Vehicle Testing, Baseline Testing Results",
     Vehicle Technologies Program. VIN 1N4AZ0C0DC405045, trim SV.
     https://www.energy.gov/sites/prod/files/2015/01/f19/fact2013nissanleaf.pdf
     -- delivered curb weight 3302 lb; PM AC synchronous motor, 80 kW,
        253 Nm; automatic fixed gear, final drive 7.9; 192 cells as 2 parallel
        by 96 series, LMO, 364.8 V nominal, 66.2 Ah rated, 24 kWh rated;
        205/55 R16 tyres; maximum speed 91.0 mph at the one-mile mark;
        coastdown coefficients A 31.911 lb, B 0.11588 lb/mph,
        C 0.017756 lb/mph^2 at curb plus 332 lb.
[L2] Frontal area 2.27 m^2 is not published by Nissan and is taken from the
     usual figure for this body. ASSUMPTION-GRADE. The risk is low because it
     enters only as the CdA product, and CdA itself is measured in [L1].
[L3] Vehicle Energy Dataset, Oh, LeBlanc and Peng, IEEE Transactions on
     Intelligent Transportation Systems, 2020. doi:10.1109/TITS.2020.3035596.
     Source of every MEASURED value above.

CAVEATS:

 1. VED identifies its vehicles only as EngineType "EV" with a 3500 lb
    generalised weight class, and the static sheet names no model. That they
    are 2013 Nissan Leafs is stated by the dataset authors in the repository
    README, not derived from the logs. The three cars are not the specific
    vehicle [L1] tested, so its coastdown describes the model and not the unit.
 2. No battery temperature channel exists in VED, so the pack thermal model
    runs on ambient. In Ann Arbor winters that is wrong in the direction of an
    optimistically warm, and therefore too conductive, pack.
 3. The regenerative braking ceiling is an ENGINEERING ASSUMPTION, as it was
    for the i3. Nissan does not publish one.
"""

CITATIONS_COMMON = {
    "mass_kg": "delivered curb weight 3302 lb [L1] plus a 75 kg driver",
    "frontal_area_m2": "2.27 m2, ASSUMPTION-GRADE [L2]; enters only through "
                       "the CdA product, and CdA is measured in [L1]",
    "wheel_radius_m": "unloaded radius of the 205/55 R16 fitment [L1]",
    "gear_ratio": "single-speed final drive, 7.9377; [L1] rounds it to 7.9",
    "drivetrain_eta": "TRANSFERRED from the i3 plant: 0.95, an engineering "
                      "assumption there and still one here",
    "motor": "80 kW / 253 Nm permanent-magnet AC synchronous machine [L1]. "
             "The efficiency map is TRANSFERRED from the i3 identification",
    "regen": "ENGINEERING ASSUMPTION: 40 kW ceiling, scaled from the i3's "
             "assumed 50 kW by the ratio of rated motor powers",
    "aux": "fitted from VED's own heater and air-conditioning channels [L3]",
    "battery": "192 cells as 2p96s LMO, 364.8 V nominal [L1]. capacity_ah and "
               "the OCV curve are MEASURED from VED [L3]; r0 is measured from "
               "VED unless the arm under test transfers it",
}


def _battery(r0_ohm: float) -> BatteryParams:
    return BatteryParams(
        capacity_ah=CAPACITY_AH,
        ocv_soc_points=OCV_SOC_POINTS,
        ocv_volts=OCV_VOLTS,
        r0_ohm=r0_ohm, r1_ohm=0.01, c1_farad=2000.0,
        # 80 kW at 364.8 V nominal is about 219 A. The charge limit and the
        # SoC window are assumptions, as they were for the i3.
        i_discharge_max_a=300.0, i_charge_max_a=120.0,
        soc_min=0.05, soc_max=1.0,
        r0_temp_coeff_per_c=-0.004, t_ref_c=25.0,
    )


def _motor(efficiency_grid: np.ndarray, torque_axis, speed_axis) -> MotorParams:
    return MotorParams(
        torque_axis_nm=tuple(torque_axis),
        speed_axis_radps=tuple(speed_axis),
        efficiency_grid=np.asarray(efficiency_grid, dtype=float),
        torque_max_nm=MOTOR_TORQUE_NM,
        speed_max_radps=SPEED_MAX_RADPS,
        power_max_w=MOTOR_POWER_W,
    )


def build_leaf(
    *,
    c_rr: float,
    cd: float,
    r0_ohm: float,
    rot_mass_factor: float,
    aux: AuxParams,
    efficiency_grid: np.ndarray,
    torque_axis=(0.0, 62.5, 125.0, 250.0),
    speed_axis=(0.0, 300.0, 700.0, 1151.0),
    c_rr_source: str = "TRANSFERRED from the i3 identification",
    cd_source: str = "TRANSFERRED from the i3 identification",
    rot_source: str = "TRANSFERRED from the i3 identification",
) -> VehicleParams:
    """A Leaf plant. What varies between arms is where c_rr, cd and r0 come from."""
    citations = dict(CITATIONS_COMMON)
    citations["c_rr"] = c_rr_source
    citations["cd"] = cd_source
    citations["rot_mass_factor"] = rot_source
    return VehicleParams(
        mass_kg=MASS_KG, c_rr=c_rr, cd=cd,
        frontal_area_m2=FRONTAL_AREA_M2,
        wheel_radius_m=WHEEL_RADIUS_M,
        gear_ratio=GEAR_RATIO,
        drivetrain_eta=0.95,
        rot_mass_factor=rot_mass_factor,
        battery=_battery(r0_ohm),
        motor=_motor(efficiency_grid, torque_axis, speed_axis),
        regen=RegenParams(power_limit_w=40_000.0),
        aux=aux,
        citations=citations,
    )
