"""Block diagram of the processor-in-the-loop arrangement (no data plotted)."""
import sys; sys.path.insert(0, "paper")
import figstyle as fs
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

fig, ax = fs.figure("page", height=3.7)
ax.set_xlim(0, 100)
ax.set_ylim(0, 62)
ax.axis("off")
ax.grid(False)


def box(x, y, w, h, text, ls="-", fc="white", lw=0.7, fs_=8):
    p = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.8",
                       fc=fc, ec="black", lw=lw, ls=ls)
    ax.add_patch(p)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs_,
            linespacing=1.15)


def outer(x, y, w, h, fc, ls, title):
    p = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=1.2",
                       fc=fc, ec="black", lw=1.2, ls=ls)
    ax.add_patch(p)
    ax.text(x + w / 2, y + h + 1.2, title, ha="center", va="bottom",
            fontsize=8.5)


# Host (simulated) on the left, target (real) on the right.
outer(1, 3, 33, 52, "#ececec", (0, (4, 2)), "Host computer: SIMULATED side")
outer(66, 3, 33, 52, "#d9e2f3", "-", "ESP32-S3 target: REAL side")

hx, hw, bh = 2.5, 30, 9.2
for i, t in enumerate([
        "Vehicle model: motion, motor,\nbattery and heater",
        "Driver and drive cycle\n(reference speed, road grade)",
        "Sensor noise and\nsoftware fault injection",
        "Logger: energy, tracking error,\ndiagnostic counters"]):
    box(hx, 44 - i * 10.8, hw, bh, t, fc="white")

tx = 67.5
box(tx, 44, hw, bh, "Speed loop, 100 Hz, core 0:\nPID with feedforward")
box(tx, 33.2, hw, bh, "Speed estimator and sensor-fault\ndetector (build option)")
box(tx, 22.4, hw, bh, "Energy manager, 10 Hz, core 1:\nrule-based or learned policy")
box(tx, 11.6, hw, bh, "Forecaster: benchmarked on the\ntarget, not in the shipped image",
    ls=(0, (3, 2)))
box(tx, 4.2, hw, 6.0, "Diagnostics, 2 Hz, core 1", fc="white")


def arrow(x0, x1, y, text, num):
    a = FancyArrowPatch((x0, y), (x1, y), arrowstyle="-|>", mutation_scale=9,
                        lw=0.9, color="black")
    ax.add_patch(a)
    ax.text((x0 + x1) / 2, y + 1.0, f"{num}  {text}", ha="center", va="bottom",
            fontsize=8)


arrow(66, 34, 49, "STEP_REQ, every 10 ms", "1")
arrow(34, 66, 38.5, "STATE: 11 floats, 44 B", "2")
arrow(66, 34, 28, "ACTUATION: 4 floats, 16 B", "3")
arrow(66, 34, 17.5, "DIAG: counters, every 500 ms", "4")

ax.text(50, 58.2, "Serial link, CRC-16 frames", ha="center", va="bottom",
        fontsize=8)
ax.text(50, 8.4, "Target is the clock master;\nthe state used at step k\nis one period (10 ms) old",
        ha="center", va="center", fontsize=8, linespacing=1.15)

fs.save(fig, "fig-platform-architecture")
