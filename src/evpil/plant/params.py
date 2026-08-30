"""Vehicle parameters, every one of them cited.

A parameter without a source is a parameter a reviewer can reject, so
construction fails when a citation is missing rather than at review time.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from evpil.plant.auxiliary import AuxParams
from evpil.plant.battery import BatteryParams
from evpil.plant.motor import MotorParams
from evpil.plant.regen import RegenParams

_CITED_FIELDS = (
    "mass_kg", "c_rr", "cd", "frontal_area_m2", "wheel_radius_m",
    "gear_ratio", "drivetrain_eta", "battery", "motor", "regen", "aux",
)


@dataclass(frozen=True)
class VehicleParams:
    mass_kg: float
    c_rr: float
    cd: float
    frontal_area_m2: float
    wheel_radius_m: float
    gear_ratio: float
    drivetrain_eta: float
    battery: BatteryParams
    motor: MotorParams
    regen: RegenParams
    aux: AuxParams
    citations: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        missing = [name for name in _CITED_FIELDS if not self.citations.get(name)]
        if missing:
            raise ValueError(
                f"missing citation for: {missing}. Every vehicle parameter must "
                f"name its source (published specification, or identification "
                f"against logged data)."
            )
        for name in ("mass_kg", "wheel_radius_m", "gear_ratio"):
            if getattr(self, name) <= 0.0:
                raise ValueError(f"{name} must be positive, got {getattr(self, name)}")
        if not 0.0 < self.drivetrain_eta <= 1.0:
            raise ValueError(f"drivetrain_eta must be in (0, 1], got {self.drivetrain_eta}")
