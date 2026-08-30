"""Which VED battery-electric trips may be used, and why each rejection happened.

Same discipline as the i3 rule in `evpil.data.eligibility`: mechanical tests,
fixed before any model is fitted, with a recorded reason per exclusion.

The tests differ because the datasets fail differently. VED's BEV channels are
fully populated, so there is no missing-data test to run. What VED has instead
is time: a "trip" is whatever the logger bracketed, and some brackets contain
gaps of twenty minutes. A gap is not a measurement, and interpolating across
one invents driving that did not happen.

One i3 test has no VED counterpart. The i3 heater is measured twice, on
separate buses, so the two can be required to agree; VED logs each auxiliary
channel once and there is nothing to corroborate it against. That is a real
gap in what can be checked here, not an oversight.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

MAX_GAP_S = 30.0          # longest tolerable hole in the timestamp series
MIN_DURATION_S = 120.0    # shorter trips cannot support a terminal-SoC test
MIN_SAMPLES = 60
MAX_SOC_RISE_PP = 0.0     # a rising SoC means the trip contains charging
MIN_DISTANCE_KM = 0.5


@dataclass(frozen=True)
class TripVerdict:
    trip_id: str
    eligible: bool
    reason: str
    n: int
    duration_s: float
    max_gap_s: float
    distance_km: float
    soc_net_pp: float
    mean_oat_c: float


def assess_trip(trip_id: str, block: pd.DataFrame) -> TripVerdict:
    """Apply the five eligibility tests to one raw BEV trip block."""
    ts = block["Timestamp(ms)"].to_numpy(dtype=float) / 1000.0
    soc = pd.to_numeric(block["HV Battery SOC[%]"], errors="coerce").to_numpy()
    v = pd.to_numeric(block["Vehicle Speed[km/h]"],
                      errors="coerce").to_numpy() / 3.6
    oat = float(np.nanmean(pd.to_numeric(block["OAT[DegC]"], errors="coerce")))

    n = len(block)
    dts = np.diff(ts)
    duration = float(ts[-1] - ts[0]) if n > 1 else 0.0
    gap = float(dts.max()) if len(dts) else 0.0
    km = float(np.nansum(v[:-1] * dts) / 1000.0) if len(dts) else 0.0
    present = soc[np.isfinite(soc)]
    net = float(present[-1] - present[0]) if len(present) > 1 else np.nan

    if n < MIN_SAMPLES:
        reason = f"only {n} samples, below {MIN_SAMPLES}"
    elif duration < MIN_DURATION_S:
        reason = f"lasts {duration:.0f} s, below {MIN_DURATION_S:.0f} s"
    elif gap > MAX_GAP_S:
        reason = f"{gap:.0f} s gap in the log: not one continuous trip"
    elif km < MIN_DISTANCE_KM:
        reason = f"covers {km:.2f} km, below {MIN_DISTANCE_KM} km"
    elif not np.isfinite(net):
        reason = "SoC channel unusable"
    elif net > MAX_SOC_RISE_PP:
        reason = f"net SoC rose {net:+.1f} pp: trip includes charging"
    else:
        reason = "eligible"

    return TripVerdict(
        trip_id=trip_id, eligible=(reason == "eligible"), reason=reason,
        n=n, duration_s=duration, max_gap_s=gap, distance_km=km,
        soc_net_pp=net, mean_oat_c=oat,
    )


def assess_all(raw: pd.DataFrame) -> pd.DataFrame:
    """Assess every BEV trip in a raw frame."""
    from evpil.data.ved_loader import raw_trips
    return pd.DataFrame([assess_trip(tid, block).__dict__
                         for tid, block in raw_trips(raw)])


def eligible_trip_ids(raw: pd.DataFrame) -> list[str]:
    df = assess_all(raw)
    return sorted(df.loc[df.eligible, "trip_id"].tolist())
