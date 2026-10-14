import sys; sys.path.insert(0, "paper")
import pandas as pd
import figstyle as fs

cost = pd.read_csv("docs/forecast-deploy-cost.csv").set_index("arm")
persist = cost.loc["persistence", "final_rmse_w"] / 1000.0
g4 = persist * 0.9
# Latency measured on the target (docs/g5-latency.md)
MEAS = {"lstm": 35.07, "transformer plain-1ch": 36.46}
BUDGET = 40.0

fig, ax = fs.figure("col", height=3.2)
arrow = dict(arrowstyle="-", color="0.4", lw=0.5)
# name, arm, colour index, label position (data coordinates)
rows = [("Linear regression", "ridge", 1, (0.35, 11.62)),
        ("LSTM", "lstm", 2, (1.2, 11.28)),
        ("Transformer", "transformer plain-1ch", 0, (1.2, 10.95)),
        ("LSTM, five-model\naverage (est.)", "lstm x5 (as reported)", 3, (60, 12.3))]
for name, arm, ci, pos in rows:
    e = cost.loc[arm, "final_rmse_w"] / 1000.0
    lat = cost.loc[arm, "latency_ms"]
    ax.plot(lat, e, marker="o", mfc="white", mec=fs.C[ci], color=fs.C[ci], ls="none", ms=5)
    tgt = lat
    if arm in MEAS:
        ax.annotate("", xy=(MEAS[arm], e), xytext=(lat * 1.06, e),
                    arrowprops=dict(arrowstyle="->", color=fs.C[ci], lw=0.9))
        ax.plot(MEAS[arm], e, marker="o", color=fs.C[ci], ls="none", ms=5)
        tgt = MEAS[arm] if arm == "transformer plain-1ch" else lat
    ax.annotate(name, (tgt, e), xytext=pos, textcoords="data", fontsize=8,
                va="center", ha="left", arrowprops=arrow)
xe = cost.loc["xgboost", "final_rmse_w"] / 1000.0
ax.plot(250, xe, marker="D", color=fs.C[4], ls="none", ms=5)
ax.annotate("XGBoost\n(no latency,\n3,658 KB)", (250, xe), xytext=(390, 11.7), textcoords="data",
            fontsize=8, va="center", ha="right", arrowprops=arrow)
ax.axhline(persist, color="black", lw=0.9)
ax.text(0.14, persist + 0.05, "Persistence", fontsize=8, va="bottom")
ax.axhline(g4, color=fs.C[3], ls=":", lw=1.0)
ax.text(0.14, g4 + 0.05, "Gate G4 bar", fontsize=8, va="bottom")
ax.axvline(BUDGET, color=fs.C[1], ls="--", lw=1.0)
ax.text(BUDGET * 0.93, 12.75, "40 ms budget", fontsize=8, color=fs.C[1], va="center", ha="right", rotation=90)
ax.set_xscale("log")
ax.set_xlim(0.12, 400)
ax.set_ylim(10.8, 13.5)
ax.set_xlabel("Time per forecast on one core (ms, log scale)")
ax.set_ylabel("Forecast error at 3 s (kW)")
fs.save(fig, "fig-forecast-cost")
