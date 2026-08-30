"""Which i3 trips may be used, and why each rejected one was rejected.

The archive's own readme warns that its summer trips (category A) "do not
contain all measured data due to trouble with the measurement system", while
the winter trips (category B) are "consistent". That warning is turned into
four mechanical tests here rather than applied by eye, so the eligible set is
reproducible and every exclusion carries a reason.

The rule is fixed before any model is fitted. Choosing trips after seeing which
ones the plant reproduces well would make the G2 verdict meaningless.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

# Thresholds, all set from the physics or the instrument, not from model error.
MAX_SOC_GAP_FRAC = 0.01      # SoC must be present for 99% of samples
MIN_HEATER_CORR = 0.90       # CAN vs LIN Pearson r
MAX_HEATER_MAE_W = 100.0     # CAN vs LIN mean absolute difference
MAX_SOC_RISE_PP = 0.0        # net SoC must not increase: no charging mid-trip

_HEAT_CAN = "Heating Power CAN [kW]"
_HEAT_LIN = "Heating Power LIN [W]"
_SOC = "SoC [%]"


@dataclass(frozen=True)
class TripVerdict:
    trip_id: str
    eligible: bool
    reason: str
    soc_gap_frac: float
    soc_net_pp: float
    heater_corr: float
    heater_mae_w: float


def _read_probe(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, sep=";", encoding="cp1252", low_memory=False)
    df.columns = [c.replace("Velocity [km/h]]]", "Velocity [km/h]").strip()
                  for c in df.columns]
    return df.loc[:, ~df.columns.duplicated()]


def assess_trip(path: Path) -> TripVerdict:
    """Apply the four eligibility tests to one raw archive file."""
    path = Path(path)
    df = _read_probe(path)
    num = lambda c: (pd.to_numeric(df[c], errors="coerce")
                     if c in df.columns else None)

    soc = num(_SOC)
    gap = float(soc.isna().mean()) if soc is not None else 1.0
    present = soc.dropna() if soc is not None else pd.Series(dtype=float)
    net = float(present.iloc[-1] - present.iloc[0]) if len(present) > 1 else np.nan

    can, lin = num(_HEAT_CAN), num(_HEAT_LIN)
    corr, mae = np.nan, np.nan
    if can is not None and lin is not None and lin.nunique() > 1:
        m = can.notna() & lin.notna()
        if m.sum() > 2:
            corr = float(np.corrcoef(can[m] * 1000.0, lin[m])[0, 1])
            mae = float(np.mean(np.abs(can[m] * 1000.0 - lin[m])))

    # Ordered so the reported reason is the most fundamental failure.
    if gap > MAX_SOC_GAP_FRAC:
        reason = f"SoC missing for {gap*100:.1f}% of samples"
    elif not np.isfinite(net):
        reason = "SoC channel unusable"
    elif net > MAX_SOC_RISE_PP:
        reason = f"net SoC rose {net:+.1f} pp: trip includes charging"
    elif not np.isfinite(corr):
        reason = "heater power has no independent LIN measurement to corroborate it"
    elif corr < MIN_HEATER_CORR:
        reason = f"heater CAN vs LIN correlation {corr:.2f} below {MIN_HEATER_CORR}"
    elif mae > MAX_HEATER_MAE_W:
        reason = f"heater CAN vs LIN disagree by {mae:.0f} W mean"
    else:
        reason = "eligible"

    return TripVerdict(
        trip_id=path.stem, eligible=(reason == "eligible"), reason=reason,
        soc_gap_frac=gap, soc_net_pp=net, heater_corr=corr, heater_mae_w=mae,
    )


def assess_all(root: Path) -> pd.DataFrame:
    """Assess every trip under `root`, newest rule applied uniformly."""
    rows = [assess_trip(p) for p in sorted(Path(root).glob("Trip*.csv"))]
    return pd.DataFrame([r.__dict__ for r in rows])


def eligible_trip_ids(root: Path) -> list[str]:
    df = assess_all(root)
    return sorted(df.loc[df.eligible, "trip_id"].tolist())
