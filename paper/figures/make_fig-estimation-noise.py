import sys, json; sys.path.insert(0, "paper")
import figstyle as fs

SC = {"floor": 1, "elevated": 3, "severe": 10}
series = {}
for arm in ("b0", "b5"):
    d = json.load(open(f"docs/week12-speed-arms-{arm}.json"))
    pts = {SC[r["level"]]: r["equivalent_wh_per_km"]
           for r in d["runs"] if r["scenario"] == "sensor_noise"}
    series[arm] = pts

fig, ax = fs.figure("col")
xs = sorted(series["b0"])
ax.plot(xs, [series["b0"][x] for x in xs], label="Baseline speed loop", **fs.line(1))
ax.plot(xs, [series["b5"][x] for x in xs], label="Two-state Kalman estimator", **fs.line(0))
ax.set_xscale("log")
ax.set_xticks(xs)
ax.set_xticklabels([str(x) for x in xs])
ax.minorticks_off()
ax.set_xlabel("Sensor noise (multiple of the noise floor)")
ax.set_ylabel("Energy, US06 (Wh/km)")
ax.set_ylim(189.5, 202)
ax.legend(loc="upper left")
fs.save(fig, "fig-estimation-noise")
