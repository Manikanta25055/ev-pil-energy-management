# scripts/plot_g2.py
"""Figures for the G2 report: parity scatter for the best and worst trips,
and a time-series overlay for a representative one.

A summary statistic can hide a model that is right on average and wrong
everywhere, so the gate is reported with the traces that produced it.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from evpil.data.splits import Split, apply_split
from evpil.plant.auxiliary import AuxParams
from scripts.identify_params import build_params, load_eligible, simulate_trip


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/raw/i3")
    ap.add_argument("--splits", default="data/splits.json")
    ap.add_argument("--params", default="data/i3_params.json")
    ap.add_argument("--per-trip", default="docs/g2-per-trip.csv")
    ap.add_argument("--outdir", default="docs/figures")
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    cfg = json.loads(Path(args.params).read_text())
    ident = cfg["identified"]
    params = build_params(ident["c_rr"], ident["cd"], ident["r0_ohm"],
                          AuxParams(**cfg["aux"]),
                          ident.get("rot_mass_factor", 0.0))

    per = pd.read_csv(args.per_trip).sort_values("power_rmse_frac")
    best, worst = per.iloc[0].trip_id, per.iloc[-1].trip_id

    sp = json.loads(Path(args.splits).read_text())
    df = load_eligible(Path(args.data))
    _, val, _ = apply_split(df, Split(sp["train"], sp["val"], sp["test"]))

    def trace(trip_id):
        t = val[val.trip_id == trip_id].reset_index(drop=True)
        return t, simulate_trip(params, t), (t.v_batt_v * t.i_batt_a).to_numpy()

    # Parity: best and worst validation trip side by side, same axes.
    fig, axes = plt.subplots(1, 2, figsize=(11, 5.2), constrained_layout=True)
    for ax, tid, label in ((axes[0], best, "best"), (axes[1], worst, "worst")):
        t, sim, obs = trace(tid)
        row = per[per.trip_id == tid].iloc[0]
        ax.plot(obs / 1e3, sim / 1e3, ".", ms=1, alpha=0.15, color="#1f77b4",
                rasterized=True)
        lim = [min(obs.min(), sim.min()) / 1e3, max(obs.max(), sim.max()) / 1e3]
        ax.plot(lim, lim, "-", lw=1.0, color="#d62728", label="ideal")
        ax.set_xlim(lim), ax.set_ylim(lim)
        ax.set_xlabel("logged battery power (kW)")
        ax.set_ylabel("simulated battery power (kW)")
        ax.set_title(f"{label}: {tid}\n"
                     f"RMSE {row.power_rmse_w/1e3:.2f} kW "
                     f"({row.power_rmse_frac*100:.1f}% of mean |P|)")
        ax.legend(loc="upper left", frameon=False)
        ax.grid(alpha=0.25)
    fig.savefig(outdir / "g2-parity.png", dpi=150)
    plt.close(fig)

    # Time series: the median trip, so the picture is typical rather than flattering.
    mid = per.iloc[len(per) // 2].trip_id
    t, sim, obs = trace(mid)
    win = slice(0, min(len(t), 6000))          # first 600 s keeps detail visible
    fig, axes = plt.subplots(3, 1, figsize=(11, 8), sharex=True,
                             constrained_layout=True,
                             gridspec_kw={"height_ratios": [1, 2, 1]})
    axes[0].plot(t.t_s[win], t.v_mps[win] * 3.6, lw=0.8, color="#333333")
    axes[0].set_ylabel("speed (km/h)"), axes[0].grid(alpha=0.25)
    axes[0].set_title(f"representative validation trip: {mid}")
    axes[1].plot(t.t_s[win], obs[win] / 1e3, lw=0.8, label="logged", color="#1f77b4")
    axes[1].plot(t.t_s[win], sim[win] / 1e3, lw=0.8, label="simulated",
                 color="#d62728", alpha=0.8)
    axes[1].set_ylabel("battery power (kW)"), axes[1].grid(alpha=0.25)
    axes[1].legend(loc="upper right", frameon=False)
    axes[2].plot(t.t_s[win], (sim[win] - obs[win]) / 1e3, lw=0.7, color="#555555")
    axes[2].axhline(0, lw=0.8, color="#d62728")
    axes[2].set_ylabel("error (kW)"), axes[2].set_xlabel("time (s)")
    axes[2].grid(alpha=0.25)
    fig.savefig(outdir / "g2-timeseries.png", dpi=150)
    plt.close(fig)

    # The gate as actually evaluated: part B against part C, plus part A.
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.4), constrained_layout=True)
    ax = axes[0]
    ax.scatter(per.floor_rmse_frac * 100, per.soc_abs_error * 100, s=55,
               color="#1f77b4", zorder=3)
    for _, r in per.iterrows():
        ax.annotate(r.trip_id.replace("Trip", ""),
                    (r.floor_rmse_frac * 100, r.soc_abs_error * 100),
                    textcoords="offset points", xytext=(7, 3), fontsize=9)
    ax.axvline(10.0, color="#d62728", lw=1.2, ls="--")
    ax.axhline(2.0, color="#d62728", lw=1.2, ls="--")
    ax.set_xlim(0, 12), ax.set_ylim(0, 3)
    ax.set_xlabel("B: battery-power RMSE, logged torque (% of mean |P|)")
    ax.set_ylabel("C: terminal SoC error (percentage points)")
    ax.set_title("G2 parts B and C\npass region is below and left of the dashed lines")
    ax.grid(alpha=0.25, zorder=0)

    # Part A, and the reason the original pooled number could not be met.
    ax = axes[1]
    order = per.sort_values("torque_rel")
    y = np.arange(len(order))
    ax.barh(y - 0.2, order.torque_rel * 100, height=0.38, color="#1f77b4",
            label="A: torque RMSE / logged-torque sd")
    ax.barh(y + 0.2, order.power_rmse_frac * 100, height=0.38, color="#999999",
            label="end-to-end instantaneous RMSE (not gated)")
    ax.set_yticks(y)
    ax.set_yticklabels([t.replace("Trip", "") for t in order.trip_id])
    ax.axvline(50.0, color="#d62728", lw=1.2, ls="--", label="part A bound")
    ax.set_xlabel("percent")
    ax.set_title("G2 part A, with the superseded pooled number for contrast\n"
                 "both are driven by the same torque-inversion noise")
    ax.legend(loc="lower right", frameon=False, fontsize=8)
    ax.grid(alpha=0.25, axis="x")
    fig.savefig(outdir / "g2-criteria.png", dpi=150)
    plt.close(fig)

    print(f"wrote {outdir}/g2-parity.png, g2-timeseries.png, g2-criteria.png")
    print(f"best={best} worst={worst} representative={mid}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
