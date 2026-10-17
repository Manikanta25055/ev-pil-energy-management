# EV energy management on a microcontroller: processor-in-the-loop study

This repository holds the code, firmware, run logs and write-ups for a study of
electric-vehicle (EV) energy management running on an ESP32-S3 microcontroller.
A rule-based energy manager and a learned one (Soft Actor-Critic, SAC) run on
the board at 100 Hz. The laptop simulates the vehicle and talks to the board
over USB serial; this arrangement is called processor-in-the-loop (PIL).

## Where to start

| If you want | Open |
|---|---|
| The paper (mock IEEE Access manuscript, 24 pages) | [`paper/EV-PIL-mock-paper-IEEE-Access.pdf`](paper/EV-PIL-mock-paper-IEEE-Access.pdf) |
| The full project report (weeks 1 to 14) | [`reports/EV-PIL-status-report.docx`](reports/EV-PIL-status-report.docx) |
| The note correcting the earlier 8.28% claim | [`reports/supervisor-correction-note.docx`](reports/supervisor-correction-note.docx) |
| The simulated peer review of the paper | [`paper/reviews/2026-10-14/`](paper/reviews/2026-10-14/) |
| The last measurement round and its fixed decision rules | [`docs/2026-10-14-measurement-plan.md`](docs/2026-10-14-measurement-plan.md) |

The paper is the most recent summary. Where the report and the paper differ,
the paper is newer.

## Main findings

1. **The early learned saving was not real.** In the first campaign the learned
   policy appeared to use 8.28% less energy than the rules. The cause was the
   vehicle model: it billed battery power at the policy's power ceiling but
   computed acceleration from the uncapped torque, so the policy learned to set
   a low ceiling and drive above it without paying. A sweep with no controller
   showed it: a fixed 5 kW ceiling "drove" all of US06 on 8.05 Wh/km. The
   8.28% result is withdrawn.
2. **After the fix, the learned policy does not beat the rules.** Over 36 runs
   on the board it used 0.94% more energy on average and was lower in 1 of 16
   settings. A second campaign with new noise seeds gave more energy in 12 of
   12 conditions (median +0.50%, Wilcoxon p = 0.0005).
3. **There was little to gain in the first place.** With the speed profile set
   by the tracking loop, a dynamic-programming bound puts the rules within
   0.01% to 0.16% of the optimum.
4. **The measured gain came from estimation.** A two-state Kalman speed
   estimator on the board cut the energy lost at ten times the sensor-noise
   floor from 9.44 to 0.24 Wh/km.
5. **Every learned component is reported with its on-board cost** (memory,
   latency), next to its accuracy.

Results are labelled MEASURED (on the board) or SIMULATED (host only)
throughout the documents.

## Repository layout

| Folder | Contents |
|---|---|
| `src/evpil/` | Python package: `plant/` vehicle model, `control/` controllers, `forecast/` prediction models, `plan/` speed planning, `data/` datasets and splits |
| `firmware/main/` | C firmware for the ESP32-S3 (controllers, Kalman estimator, fault monitor, serial protocol) |
| `firmware/arduino_g1/` | Arduino-core build entry point |
| `firmware/host_test/` | Native C test harnesses (protocol and control) |
| `scripts/` | Simulation, training, PIL campaign runners, statistics, plotting, report builders |
| `tests/` | pytest suite |
| `docs/` | Experiment records (JSON/CSV/Markdown), dated plans, figures |
| `paper/` | Manuscript sections, figures, build script, audits and simulated review |
| `reports/` | Project report and supervisor note (Word) |
| `data/` | Vehicle parameters and train/validation/test split definitions |
| `models/` | Trained model files (speed planner, sensor-fault reviewer) |

## Data

Raw datasets are not stored in Git. Sources and exact files are listed in
[`docs/dataset-provenance.md`](docs/dataset-provenance.md):

- BMW i3 real driving cycles, IEEE DataPort, doi
  [10.21227/6jr9-5235](https://dx.doi.org/10.21227/6jr9-5235), used to
  identify and validate the vehicle model.
- Vehicle Energy Dataset (VED), used as an independent second source.

## Hardware

- ESP32-S3 DevKitM-1, connected through its native USB port.
- MacBook (Apple M2) as the simulation host.

Details: [`docs/hardware-inventory.md`](docs/hardware-inventory.md).

## Running it

Python 3.11 or newer.

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e '.[dev]'
pytest tests -q
```

Some tests need the drive-cycle traces in `data/raw/`; fetch them first with
`python3 scripts/build_cycles.py`.

Native C checks: `make -C firmware/host_test check`.
Firmware build (Arduino ESP32 core via `arduino-cli`): `scripts/arduino_build.sh`.
Board campaigns: `scripts/run_pil_campaign.py` (needs the board attached).

## Limits

The claims cover one vehicle model, one board, one learned algorithm, and a
speed profile fixed by the tracking loop. Nothing here was tested on a real
vehicle.

## Author

Manikanta Gonugondla
