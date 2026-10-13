import sys; sys.path.insert(0, "paper")
import json
import pandas as pd
import figstyle as fs

lad = pd.read_csv("docs/forecast-ladder.csv")
a1 = json.load(open("docs/transformer-a1.json"))
t = a1["arms"]["plain-1ch"]["rmse_w"]
sec = lad["seconds"]
fig, ax = fs.figure("col", height=2.5)
ax.plot(sec, lad["persistence_rmse_w"] / 1000, label="Persistence", **fs.line(3), markevery=5)
ax.plot(sec, lad["ridge_rmse_w"] / 1000, label="Linear regression", **fs.line(1), markevery=5)
ax.plot(sec, [x / 1000 for x in t], label="Transformer (3-model mean)", **fs.line(0), markevery=5)
ax.set_xlabel("Forecast horizon (s)")
ax.set_ylabel("Forecast error (kW)")
ax.legend(loc="upper left")
fs.save(fig, "fig-forecast-horizon")
