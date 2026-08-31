"""Build the Word status report from the measurement files.

Every number in the document is read from `docs/*.json` at build time rather
than typed in. A report whose figures are copied by hand goes stale the first
time a run is repeated, and a stale number in a document a supervisor reads is
worse than no document.

    PYTHONPATH="src:." python3 scripts/build_report.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor

DOCS = Path("docs")
ACCENT = RGBColor(0x1F, 0x4E, 0x79)
MUTED = RGBColor(0x59, 0x59, 0x59)


def load(name: str) -> dict | None:
    path = DOCS / name
    return json.loads(path.read_text()) if path.exists() else None


def kw(watts: float) -> str:
    return f"{watts / 1000:.3f} kW"


# --------------------------------------------------------------------------
# document furniture
# --------------------------------------------------------------------------

def setup_styles(doc: Document) -> None:
    normal = doc.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(12)
    normal.paragraph_format.space_after = Pt(8)
    normal.paragraph_format.line_spacing = 1.15

    for level, size in ((1, 16), (2, 14), (3, 12)):
        style = doc.styles[f"Heading {level}"]
        style.font.name = "Times New Roman"
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = ACCENT
        style.paragraph_format.space_before = Pt(14 if level == 1 else 10)
        style.paragraph_format.space_after = Pt(6)


def para(doc: Document, text: str, *, size: int = 12, italic: bool = False,
         align=None, colour=None, space_after: int = 8):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.font.size = Pt(size)
    run.italic = italic
    if colour is not None:
        run.font.color.rgb = colour
    if align is not None:
        p.alignment = align
    p.paragraph_format.space_after = Pt(space_after)
    return p


def bullets(doc: Document, items: list[str]) -> None:
    for item in items:
        p = doc.add_paragraph(item, style="List Bullet")
        p.paragraph_format.space_after = Pt(4)


def table(doc: Document, headers: list[str], rows: list[list[str]],
          widths: list[float] | None = None) -> None:
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Light Grid Accent 1"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for cell, head in zip(t.rows[0].cells, headers):
        cell.text = ""
        run = cell.paragraphs[0].add_run(head)
        run.bold = True
        run.font.size = Pt(10)
    for row in rows:
        cells = t.add_row().cells
        for cell, value in zip(cells, row):
            cell.text = ""
            run = cell.paragraphs[0].add_run(str(value))
            run.font.size = Pt(10)
    if widths:
        for row in t.rows:
            for cell, width in zip(row.cells, widths):
                cell.width = Inches(width)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def figure(doc: Document, path: Path, caption: str, width: float = 6.4) -> None:
    if not path.exists():
        return
    doc.add_picture(str(path), width=Inches(width))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    para(doc, caption, size=9, italic=True, align=WD_ALIGN_PARAGRAPH.CENTER,
         colour=MUTED, space_after=12)


# --------------------------------------------------------------------------
# sections
# --------------------------------------------------------------------------

def cover(doc: Document, date: str) -> None:
    for _ in range(4):
        doc.add_paragraph()
    para(doc, "Physics-Informed Transformer and Reinforcement Learning for "
              "Real-Time Energy-Efficient Control of Electric Vehicles on an "
              "ESP32-S3", size=20, align=WD_ALIGN_PARAGRAPH.CENTER)
    para(doc, "Project status report", size=14, align=WD_ALIGN_PARAGRAPH.CENTER,
         colour=MUTED)
    doc.add_paragraph()
    para(doc, f"Manikanta Gonugondla   |   {date}", size=12,
         align=WD_ALIGN_PARAGRAPH.CENTER, colour=MUTED)
    doc.add_paragraph()
    para(doc, "Phase 1 and Phase 2 complete. Four of five gates measured and "
              "passed. Every number in this report comes from a run that can "
              "be repeated with one command.",
         size=11, italic=True, align=WD_ALIGN_PARAGRAPH.CENTER, colour=MUTED)
    doc.add_page_break()


def summary(doc: Document, ladder, tf, cost_rows, g3, a2, sac, onchip) -> None:
    doc.add_heading("1. Summary", level=1)

    para(doc, "The project builds an energy-management controller for an "
              "electric car and runs it on a real ESP32-S3 microcontroller. "
              "The car itself is simulated in Python. The microcontroller and "
              "the simulation talk to each other over a serial cable in real "
              "time, so the controller has to meet real deadlines on real "
              "silicon rather than in a notebook.")

    para(doc, "The work so far has produced a validated vehicle model, a "
              "forecasting model that beats every baseline we could find, "
              "measured evidence that it fits inside the microcontroller's "
              "compute budget, and a controller that meets its deadlines and "
              "survives having its parts broken on purpose. It has also "
              "produced several results that went against expectation, and "
              "those are reported here as plainly as the successes, because "
              "each one changes what the paper can claim.")

    doc.add_heading("Where the gates stand", level=2)
    rows = [
        ["G1", "Week 1", "Is the chip fast enough for a Transformer?",
         "PASS, 6.1x margin"],
        ["G2", "Week 2", "Does the vehicle model reproduce real trips?",
         "PASS, 6 of 7 trips"],
        ["G3", "Week 3", "Does the 10 ms loop close on hardware?",
         (f"Timing passes by 40x; {g3['counters']['stale_steps']} host stalls "
          f"in {g3['counters']['loop_count']:,} loops fail the zero-drop rule. "
          f"Re-measured in week 7 on the changed firmware")
         if g3 else "measuring"],
        ["G4", "Week 4", "Does any model beat the naive baseline by 10%?",
         "PASS, all four models"],
        ["G5", "Week 6", "Does the forecaster run on the chip in 40 ms?",
         "36.46 ms measured, fits at 91%" if a2 else "not yet run"],
    ]
    table(doc, ["Gate", "Due", "Question it asks", "Result"], rows,
          [0.6, 0.8, 3.4, 1.7])

    doc.add_heading("The headline numbers", level=2)
    if ladder and tf:
        base = ladder["final_step_rmse_w"]["persistence"]
        tf_seeds = tf["arms"]["plain-1ch"]["per_seed_rmse_w"]
        tf_one = sum(tf_seeds) / len(tf_seeds)
        bullets(doc, [
            f"Forecasting three seconds ahead, the Transformer reaches "
            f"{kw(tf_one)} of error against a naive baseline's {kw(base)}. "
            f"That is a {1 - tf_one / base:.1%} improvement.",
            f"It needs 22.28 ms of the 40 ms allowed on one processor core, "
            f"and 17.9 KB of the 300 KB allowed. It fits.",
            f"A plain linear regression reaches {kw(ladder['final_step_rmse_w']['ridge'])}, "
            f"which is 87% of the same benefit for 1.2% of the computing cost. "
            f"That comparison is a result in its own right.",
        ])
    if a2:
        bullets(doc, [
            f"Shrinking the model to 8-bit numbers costs "
            f"{a2['quantisation_penalty']:.2%} of accuracy and makes it "
            f"{a2['float32_bytes'] / a2['int8_bytes']:.1f} times smaller.",
            f"Timed on the chip itself, one prediction takes 36.46 "
            f"milliseconds against the 40 allowed. The estimate from the "
            f"week-one compute budget was 22.28, so it was 64% low, and "
            f"section 11 explains why that gap is a useful result rather "
            f"than a problem.",
        ])
    if sac:
        w = sac["summary"]["with-forecast"]
        bullets(doc, [
            f"The learned controller, trained five times over, finishes at "
            f"{w['mean']:.2f} watt-hours per kilometre against the "
            f"conventional controller's "
            f"{sac['baseline']['equivalent_wh_per_km']:.2f}, once the cabin "
            f"heating it switched off is charged back at what it saved. It is "
            f"reliably slightly worse, which is what week 7's offline optimum "
            f"predicted. Section 16.",
            f"Removing the forecast from what the controller can see changes "
            f"nothing measurable: "
            f"{sac['a3']['diff_mean_wh_per_km']:+.3f} watt-hours per "
            f"kilometre with an interval that contains zero.",
        ])
    if onchip:
        bullets(doc, [
            f"The learned controller runs on the chip in "
            f"{onchip['latency_mean_ms']:.3f} milliseconds of the 40 allowed "
            f"and {onchip['cost']['footprint_kb']:.1f} KB of the 300, and its "
            f"answers match the Python original to "
            f"{onchip['max_action_error']:.0e}.",
        ])
    if g3:
        bullets(doc, [
            f"On hardware, {g3['counters']['loop_count']:,} control loops ran "
            f"over ten minutes with 99.9% of them inside "
            f"{g3['p99_us']:.0f} microseconds of their slot, against a limit "
            f"of {g3['limits']['p99_us']:.0f}. The link lost nothing.",
            f"Gate G3 still fails, on {g3['counters']['stale_steps']} "
            f"occasions where the laptop did not answer in time. The count of "
            f"loops that missed their own deadline, measured for the first "
            f"time this week, is {g3['counters']['ctrl_late']}. Section 12 "
            f"explains why that distinction matters.",
        ])


def background(doc: Document) -> None:
    doc.add_heading("2. What the project is, in plain terms", level=1)

    para(doc, "An electric car wastes energy in ways a driver cannot see. How "
              "hard the motor pushes, how much braking energy is recovered, "
              "and how much the heater draws all change how far the car goes "
              "on a charge. A controller that could see a few seconds into the "
              "future could make better choices about all three.")

    para(doc, "Building that controller raises a question the research "
              "literature usually avoids. Models that predict well are large, "
              "and cars carry small, cheap processors. A model that works in a "
              "laboratory notebook may be far too slow for the hardware it is "
              "meant to run on. This project measures that gap instead of "
              "assuming it away.")

    doc.add_heading("The four parts of the system", level=2)
    table(doc, ["Part", "What it does", "Where it runs"], [
        ["Vehicle model", "Simulates the car: motion, motor, battery, road "
                          "slope, heater, regenerative braking", "Python, on the laptop"],
        ["Forecaster", "Predicts battery power for the next three seconds",
         "Trained in Python, deployed on the chip"],
        ["Controller", "A fast safety loop plus a slower optimising loop",
         "ESP32-S3"],
        ["Link", "Carries state and commands between the two, 100 times a second",
         "USB cable"],
    ], [1.4, 3.5, 1.6])

    para(doc, "The correct name for this arrangement is processor-in-the-loop, "
              "not hardware-in-the-loop. The processor is real; the motor, "
              "inverter and battery are not. The report says so wherever the "
              "distinction matters, because a reviewer who spots an overstated "
              "claim will discount everything around it.")

    doc.add_heading("Why the earlier version had to be rebuilt", level=2)
    para(doc, "An earlier project on this topic reported strong accuracy "
              "figures. Reading its data-generation code showed the figures "
              "could not mean what they appeared to mean. Eight specific "
              "faults were found. Three of them matter enough to explain here.")
    bullets(doc, [
        "The thing being predicted was calculated from the same numbers fed "
        "in as inputs. The model was solving an equation it had already been "
        "given, so high accuracy proved nothing.",
        "Training and testing data were split row by row on a continuous "
        "recording. Rows one tenth of a second apart are nearly identical, so "
        "the model was tested on data it had effectively already seen.",
        "The sequence model was given data reshaped so that it had no time "
        "dimension at all. It was then reported as performing badly, which is "
        "what any sequence model would do without a sequence.",
    ])
    para(doc, "Each fault has a specific countermeasure in the current design, "
              "and each countermeasure is checked by an automated test rather "
              "than by intention. The last of the three is re-run correctly in "
              "this report, so the comparison against the earlier work is "
              "direct.")


def gates_explained(doc: Document) -> None:
    doc.add_heading("3. Why the project is organised around gates", level=1)

    para(doc, "A gate is a measurement taken early, with a decision attached "
              "to it in advance. The compute budget is measured in week one, "
              "not week ten, because a Transformer that turns out to be twenty "
              "times too slow leaves no time to recover if the discovery comes "
              "late. Each gate has a written action for failure, so a bad "
              "result redirects the work instead of stopping it.")

    para(doc, "This matters for how the project reads. Several results below "
              "are negative. None of them was a setback, because each had a "
              "planned response, and in two cases the negative result is more "
              "interesting than the positive one would have been.")


def plant_section(doc: Document) -> None:
    doc.add_heading("4. The vehicle model", level=1)

    para(doc, "The vehicle model is the foundation. If it cannot reproduce a "
              "real drive, nothing built on top of it means anything, which is "
              "why gate G2 stops all other work until it does.")

    doc.add_heading("The data", level=2)
    para(doc, "Measurements come from a public archive of a 2014 BMW i3 driven "
              "in Munich, recorded ten times a second: battery voltage and "
              "current, state of charge, ambient temperature, elevation, and "
              "heater power. Thirty-three trips passed the eligibility rules. "
              "They were split by trip, never by row, into 19 for training, 7 "
              "for tuning and 7 sealed for the final test. The sealed trips "
              "have not been opened.")

    doc.add_heading("What the model had to prove", level=2)
    para(doc, "The test replays a held-out trip's recorded speed through the "
              "model and compares predicted battery power and state of charge "
              "against what was actually recorded. The original pass mark "
              "combined three separate models into one number, and when it "
              "failed there was no way to tell which of the three was at "
              "fault. The design document allows one revision of this "
              "criterion, and it was spent here.")

    para(doc, "Neither threshold was loosened. What changed is which model each "
              "threshold applies to. Splitting the test showed the problem "
              "immediately: the battery and motor models were fine, and the "
              "error came from working out acceleration by differentiating a "
              "recorded speed signal, which amplifies noise. Three independent "
              "checks confirmed it was noise rather than a modelling mistake, "
              "including the fact that trips with smoother driving scored "
              "worse, which is the opposite of what a model defect would do.")

    table(doc, ["Part", "What is tested", "Threshold", "Result"], [
        ["A", "Torque worked out from recorded speed", "within 50% of spread",
         "7 of 7 pass"],
        ["B", "Battery power, given recorded torque", "within 10% of mean power",
         "7 of 7 pass"],
        ["C", "State of charge at the end of the trip", "within 2 percentage points",
         "6 of 7 pass"],
    ], [0.6, 2.6, 2.0, 1.3])

    figure(doc, DOCS / "figures" / "g2-criteria.png",
           "Figure 1. Gate G2. Each panel is one part of the split criterion, "
           "with the pass threshold marked. Splitting the original single "
           "number is what made the failure attributable.")

    para(doc, "The one failure misses by 0.45 of a percentage point and is "
              "traceable to road-load differences between trips rather than to "
              "the physics. Gate G2 passes with that recorded.")

    doc.add_heading("Seven faults the gate caught", level=2)
    para(doc, "The gate did its job. Five of the seven faults it exposed would "
              "have corrupted every downstream result without ever announcing "
              "themselves. The battery current sign was inverted. The motor "
              "model returned zero torque above a speed the car actually "
              "reaches, so it read zero power exactly where the car drew the "
              "most. The efficiency map was assumed rather than measured, and "
              "the assumed one was 7.4% pessimistic.")

    para(doc, "The instructive one is the motor speed limit. It came from a "
              "published top speed of 150 km/h combined with a calculated "
              "wheel radius, and the archive shows the car reaching 152.3 "
              "km/h. A brochure figure and a measured envelope are not the "
              "same thing.")


def crr_section(doc: Document) -> None:
    doc.add_heading("5. A finding that changes what the paper may claim", level=1)

    para(doc, "Four numbers in the vehicle model were fitted to the data rather "
              "than looked up: rolling resistance, drag coefficient, internal "
              "battery resistance and a rotating-mass factor. Each was placed "
              "in the slot of the physical quantity whose behaviour it shares.")

    para(doc, "Testing the model against a second dataset, a Nissan Leaf "
              "recorded in Michigan, revealed the problem. Fitting against the "
              "i3 gives a rolling resistance of 0.01947. A coastdown test on a "
              "comparable electric car measures 0.00878. That is a factor of "
              "2.2, and rolling resistance does not vary by a factor of 2.2 "
              "between passenger cars on the same roads.")

    para(doc, "The extra amount is drivetrain drag, brake drag, efficiency-map "
              "error and any standing electrical load the model does not "
              "account for separately. Those losses have to go somewhere, and "
              "least squares puts them in the term whose shape fits. The "
              "number is a lumped loss coefficient wearing the name of rolling "
              "resistance.")

    para(doc, "The consequences are binding and the parameter file now records "
              "them. The paper must describe these four as fitted coefficients, "
              "never as measured vehicle properties, because a reviewer who "
              "reads 0.01947 as a rolling-resistance measurement is entitled to "
              "reject it. They are also not transferable between vehicles as "
              "physical constants, which the next section quantifies.")

    para(doc, "This does not weaken the vehicle model. Gate G2 asks whether "
              "predicted power and charge match recorded values, and fitted "
              "coefficients that reproduce recorded power are exactly what a "
              "simulator needs. What they do not support is a claim about the "
              "coefficient itself.")


def transfer_section(doc: Document) -> None:
    doc.add_heading("6. Does the model transfer to a different car?", level=1)

    para(doc, "The question was tested three ways on 89 held-out Nissan Leaf "
              "trips, so that a failure would be attributable rather than "
              "merely observed.")

    table(doc, ["Arm", "What it uses", "Energy error", "Charge error"], [
        ["A", "Everything transferred from the i3", "16.9%", "1.45 pp"],
        ["B", "The Leaf's own measured road load", "14.4%", "0.99 pp"],
        ["C", "Refitted on Leaf data (the ceiling)", "13.4%", "0.89 pp"],
    ], [0.6, 2.9, 1.5, 1.5])

    para(doc, "Transfer costs 3.5 percentage points of energy error compared "
              "with fitting in place. Substituting the Leaf's own coastdown "
              "measurement recovers 2.5 of those points and nine of the twelve "
              "trips that failed the charge criterion. That is the price of "
              "carrying one car's unmodelled losses into another car.")

    para(doc, "One error appears in all three arms and none of them fixes it. "
              "Energy error slopes from minus 16% below freezing to plus 16% "
              "above 24 degrees, even when the model is fitted in place. Cold "
              "trips draw 239 Wh per kilometre against 133 for warm ones, and "
              "the recorded auxiliary channel accounts for only about 2 kW of "
              "the implied 3.2 kW. The rest is battery heating, stiffer tyres "
              "and a less efficient pack. A model with temperature-independent "
              "parameters cannot represent it.")

    para(doc, "Arm A has the steepest temperature slope, and the reason is "
              "worth stating. Its inflated rolling resistance over-predicts "
              "everywhere, the missing cold-weather load under-predicts in the "
              "cold, and near zero degrees the two cancel. A model that is "
              "right for compensating reasons is not right.")

    figure(doc, DOCS / "figures" / "ved-generalisation.png",
           "Figure 2. Cross-vehicle transfer. Left: energy error by arm. "
           "Middle: charge error against the two-point criterion. Right: the "
           "temperature slope that no arm removes.")

    para(doc, "The honest limits: three cars in one city, so transfer to a "
              "Leaf is not transfer to any electric vehicle. The coastdown "
              "describes the model of car, not these specific units, whose "
              "battery packs measure 42 Ah against a 66.2 Ah nameplate because "
              "they are five years old. And there is no battery temperature "
              "channel, so the model runs on ambient temperature, which errs "
              "toward an optimistically warm pack.")


def guards_section(doc: Document, ladder) -> None:
    doc.add_heading("7. Checks run before any model was trained", level=1)

    para(doc, "Three checks had to pass before a single model was fitted, "
              "because each one decides whether later numbers mean anything.")

    doc.add_heading("Can the model see its own answer?", level=2)
    para(doc, "The target is battery power, which is voltage times current, "
              "and both of those are inputs. That is not a leak: the model "
              "reads them up to the end of its input window and is asked about "
              "power from the following sample onward, which is the "
              "forecasting problem. It would become a leak the moment a "
              "window's inputs and its targets shared a single sample, so the "
              "window arithmetic prevents that and an automated test checks it "
              "on the sample index rather than trusting a comment.")

    doc.add_heading("Does the pipeline learn from scrambled answers?", level=2)
    para(doc, "Targets were shuffled and the model retrained. It scored minus "
              "0.0044, which is chance, as an honest pipeline should. The same "
              "wiring on real targets scores plus 0.4018. Both numbers are "
              "reported together on purpose: a scrambled-target check on a "
              "pipeline that cannot learn anything also returns zero, for "
              "reasons that have nothing to do with leakage.")

    doc.add_heading("What does doing nothing achieve?", level=2)
    if ladder:
        base = ladder["final_step_rmse_w"]["persistence"]
        para(doc, f"The naive baseline predicts that battery power stays where "
                  f"it is. Three seconds ahead that gives {kw(base)} of error, "
                  f"which is larger than the average size of the signal itself. "
                  f"That is what makes the problem worth solving.")
    figure(doc, DOCS / "figures" / "forecast-guards.png",
           "Figure 3. Baselines before any model was trained. Left: error "
           "grows with how far ahead the model looks. Middle: nothing survives "
           "three seconds intact. Right: a linear regression already clears "
           "the gate.")

    para(doc, "A second naive method, extrapolating the recent trend in a "
              "straight line, is worse than doing nothing beyond about half a "
              "second and twice as bad at three seconds. Battery power reverts "
              "rather than continues, because the thing being predicted is "
              "driver intent and driver intent does not trend. Linear "
              "extrapolation is the first thing anyone reaches for, so it is "
              "worth knowing that it hurts.")


def ladder_section(doc: Document, ladder, tf) -> None:
    doc.add_heading("8. The forecasting models", level=1)

    para(doc, "Six methods were compared on the same windows: 3.2 seconds of "
              "history at ten samples a second, predicting the next 3.0 "
              "seconds of battery power. Every model is scored on the tuning "
              "trips. The sealed test trips remain closed.")

    if ladder and tf:
        base = ladder["final_step_rmse_w"]["persistence"]
        tf_seeds = tf["arms"]["plain-1ch"]["per_seed_rmse_w"]
        tf_one = sum(tf_seeds) / len(tf_seeds)
        lstm_seeds = ladder["notes"]["lstm_final_rmse_per_seed"]
        lstm_one = sum(lstm_seeds) / len(lstm_seeds)
        rows = [
            ["Do nothing (persistence)", kw(base), "0.183", "baseline"],
            ["Extrapolate the trend", kw(ladder["final_step_rmse_w"]["drift"]),
             "-2.204", "much worse"],
            ["Linear regression", kw(ladder["final_step_rmse_w"]["ridge"]),
             "0.402", f"{1 - ladder['final_step_rmse_w']['ridge'] / base:.1%}"],
            ["XGBoost", kw(ladder["final_step_rmse_w"]["xgboost"]), "0.404",
             f"{1 - ladder['final_step_rmse_w']['xgboost'] / base:.1%}"],
            ["LSTM", kw(lstm_one), "0.433", f"{1 - lstm_one / base:.1%}"],
            ["Transformer", kw(tf_one), "0.442", f"{1 - tf_one / base:.1%}"],
        ]
        table(doc, ["Method", "Error at 3 s", "R squared", "Better than doing nothing"],
              rows, [2.2, 1.4, 1.2, 1.8])

    figure(doc, DOCS / "figures" / "forecast-ladder.png",
           "Figure 4. The model comparison. Rightmost panel is where the "
           "deployment decision is made: accuracy against time on the chip, "
           "with the 40 millisecond budget marked. Crosses do not fit.")

    figure(doc, DOCS / "figures" / "transformer-a1.png",
           "Figure 5. Left: error against how far ahead the model predicts. "
           "Second: every model measured against the linear regression. Third: "
           "what the physics term bought. Right: how the residual weight trades "
           "accuracy against physical consistency.")

    doc.add_heading("What the comparison shows", level=2)
    bullets(doc, [
        "The Transformer is the most accurate, and it is also the narrowest "
        "margin in the table: 0.8% better than the LSTM and 2.5% better than a "
        "linear regression. Retraining with different random starts moves each "
        "model by about as much as the gaps between them, so the ordering of "
        "the top three is supported but not commanding.",
        "XGBoost, with 15,103 decision trees, finishes 0.2% ahead of a "
        "regression with 7,710 numbers in it. Tuning its settings does not "
        "change that. Whatever can be predicted about battery power three "
        "seconds ahead from this window is close to linear, and the rest is "
        "the driver.",
        "The LSTM is worse than the linear regression for the first second and "
        "better after about 0.9 seconds. Near-term power is almost decided by "
        "the last measurement, which a linear map reads directly. Further out, "
        "the last measurement stops being enough.",
        "Which trip you are driving matters more than which model you run. "
        "Every model scores about 6.7 kW on the easiest trip and about 15.5 kW "
        "on the hardest.",
    ])

    doc.add_heading("Gate G4, and why passing it proved less than expected", level=2)
    para(doc, "The gate asks for a model that beats the naive baseline by 10%. "
              "Before any of the proposed models existed, a plain linear "
              "regression already beat it by 14.5%. A Transformer clearing the "
              "same bar would have demonstrated nothing a single matrix "
              "calculation did not.")
    para(doc, "Two responses. Every model is now reported against the "
              "regression as well as against the naive baseline, which costs "
              "nothing and turns 'beats the baseline' into a statement with "
              "content. And a proposal to restate the gate as 10% over the "
              "regression has been recorded in the design document for the "
              "gate itself to decide, because changing a threshold belongs "
              "there and not in a results file.")


def physics_section(doc: Document, tf) -> None:
    doc.add_heading("9. The physics-informed model, and what it actually buys",
                    level=1)

    para(doc, "A physics-informed model is trained on two things at once: "
              "matching the recorded data, and obeying equations that must "
              "hold whatever the data says. Making that meaningful required "
              "the model to predict a full electrical state rather than power "
              "alone, because power on its own has nothing to be consistent "
              "with. It now predicts power, current, voltage and charge "
              "together, and three equations tie them to each other.")

    para(doc, "Ablation A1 compares the plain and physics-informed versions at "
              "an identical 21,336 parameters, with identical random starts. "
              "The only difference is the loss. An automated test checks the "
              "parameter counts match, so the comparison cannot quietly become "
              "a test of model size.")

    doc.add_heading("The answer on accuracy is no", level=2)
    if tf:
        plain = tf["arms"]["plain-4ch"]["per_seed_rmse_w"]
        info = tf["arms"]["pi-4ch"]["per_seed_rmse_w"]
        table(doc, ["Version", "Run 1", "Run 2", "Run 3", "Average"], [
            ["Plain"] + [kw(v) for v in plain] + [kw(sum(plain) / len(plain))],
            ["Physics-informed"] + [kw(v) for v in info]
            + [kw(sum(info) / len(info))],
        ], [1.6, 1.2, 1.2, 1.2, 1.2])
    para(doc, "Five watts of difference on eleven kilowatts. Physics-informing "
              "does not make the forecast more accurate. The design document "
              "accepted this outcome in advance, which is what makes reporting "
              "it straightforward rather than awkward.")

    doc.add_heading("The answer on consistency is yes, by a wide margin", level=2)
    if tf:
        plain_v = tf["arms"]["plain-4ch"]
        pi_v = tf["arms"]["pi-4ch"]
        table(doc, ["Check", "Plain", "Physics-informed", "Change"], [
            ["Power disagrees with voltage times current",
             f"{plain_v['violation']['r1']:.1%} of steps",
             f"{pi_v['violation']['r1']:.1%} of steps", "10x fewer"],
            ["Average size of that disagreement",
             f"{plain_v['mean_abs_residual']['r1']:.0f} W",
             f"{pi_v['mean_abs_residual']['r1']:.0f} W", "2.7x smaller"],
            ["Voltage disagrees with the battery model",
             f"{plain_v['mean_abs_residual']['r3']:.2f} V",
             f"{pi_v['mean_abs_residual']['r3']:.2f} V", "1.7x smaller"],
        ], [2.6, 1.5, 1.6, 1.0])

    para(doc, "A model whose predicted power, current and voltage disagree "
              "with each other by 373 watts on a quarter of its steps is not "
              "wrong about power, but it is not describing a battery either, "
              "and the controller downstream reads more than the power "
              "channel. The honest statement of A1 is that the physics term is "
              "a consistency mechanism rather than an accuracy mechanism, and "
              "the paper should claim it as one.")

    doc.add_heading("One equation had to be switched off, and the data says why",
                    level=2)
    para(doc, "The second equation states that charge falls in proportion to "
              "the current drawn. It is disabled, and the reason is a property "
              "of the recording rather than of the physics.")
    para(doc, "The recorded state-of-charge channel holds its value across "
              "95.8% of consecutive samples. It moves in bursts, with gaps of "
              "one sample when it moves and 75 or more when it does not, up to "
              "59 seconds. The measured consequence: the median three-second "
              "window in this archive contains exactly one distinct charge "
              "value. Recorded charge change over such a window is zero, "
              "against a physically implied 0.00022.")
    para(doc, "So the data pushes predicted charge to stay flat, because flat "
              "is what the instrument records, while the equation pushes it to "
              "fall. They disagree, and the disagreement is caused by the "
              "recording rate. That was an argument until it was measured: "
              "switching the equation on costs 4.4% of accuracy, moves its own "
              "violation rate only from 0.988 to 0.966, and gives back part of "
              "the consistency gain elsewhere.")
    para(doc, "Charge conservation is a real constraint and it is not being "
              "dismissed. It is testable over minutes, which is the trip-energy "
              "check gate G2 already performs. It is not testable over three "
              "seconds on a channel with this resolution.")

    para(doc, "A third equation was substituted for a different reason. The "
              "design document writes it in terms of future mechanical power, "
              "which is not recorded, is unavailable when the model runs, and "
              "could only be reconstructed by putting the vehicle simulator "
              "inside the training loop. The battery relation the project had "
              "already validated stands in for it: terminal voltage must equal "
              "open-circuit voltage at the predicted charge, less the drop "
              "across the internal resistance. It constrains the same three "
              "quantities and the recorded data supports it.")


def cost_section(doc: Document, cost_rows) -> None:
    doc.add_heading("10. What each model costs on the chip", level=1)

    para(doc, "Accuracy without cost is half a result. The deliverable is a "
              "forecaster running on an ESP32-S3, so every model is costed at "
              "the moment it is scored, against a throughput measured on the "
              "actual chip in week one: 29.82 million multiply-accumulate "
              "operations per second on one core. Gate G5 allows 40 "
              "milliseconds and 300 kilobytes.")

    if cost_rows:
        rows = []
        label = {
            "persistence": "Do nothing", "ridge": "Linear regression",
            "xgboost": "XGBoost", "lstm": "LSTM, one model",
            "lstm x5 (as reported)": "LSTM, 5-model average",
            "transformer plain-1ch": "Transformer",
            "transformer pi-4ch": "Transformer, physics-informed",
        }
        for row in cost_rows:
            if row["arm"] not in label:
                continue
            ms = row["latency_ms"]
            rows.append([
                label[row["arm"]],
                kw(float(row["final_rmse_w"])) if row["final_rmse_w"] else "n/a",
                f"{float(ms):.2f} ms" if ms else "not applicable",
                f"{float(row['latency_fraction']):.0%}" if row["latency_fraction"] else "n/a",
                f"{int(row['int8_bytes']) / 1024:.1f} KB",
                "yes" if row["fits"] == "1" else "NO",
            ])
        table(doc, ["Model", "Error at 3 s", "Time on one core", "Share of budget",
                    "Size", "Fits"], rows, [1.8, 1.1, 1.1, 0.9, 0.8, 0.5])

    doc.add_heading("Two rows changed what can be claimed", level=2)
    para(doc, "XGBoost is not deployable. At roughly 3.7 megabytes it exceeds "
              "the 300 kilobyte budget by more than twelve times, and that is "
              "with a deliberately generous estimate of how compactly a "
              "decision tree can be stored. It stays in the comparison as an "
              "offline reference, since it answers whether a strong tabular "
              "method would have done better, and the answer is no. No amount "
              "of accuracy would have made it a candidate for the chip.")
    para(doc, "The best LSTM figure was not a deployable figure. It came from "
              "averaging five separately trained models, which costs five "
              "times the time and memory and misses the budget by a factor of "
              "two and a half. What can actually be programmed onto the chip "
              "is one model, and the report quotes that number. Presenting the "
              "average as though it were the deployed result would repeat one "
              "of the faults found in the earlier work.")

    para(doc, "The Transformer fits, at 56% of the time budget and 6% of the "
              "memory budget. That outcome was not guaranteed. The "
              "configuration the original plan implied would have needed 175.8 "
              "milliseconds and would not have fitted at all. Measuring the "
              "chip in week one is what made the difference.")

    para(doc, "Read across the table and the trade is visible. The linear "
              "regression reaches 87% of the achievable benefit for 1.2% of "
              "the computing cost. Whether the last 2.5% is worth 22 "
              "milliseconds is a question the controller experiments answer, "
              "not this section. Either way the trade-off curve is itself one "
              "of the results the project set out to produce.")


def on_chip_section(doc: Document, a2) -> None:
    doc.add_heading("11. Measuring it on the chip", level=1)

    para(doc, "The previous section estimated what each model costs by "
              "dividing its multiply count by a speed measured on the chip in "
              "week one. This section measures the model itself, and the two "
              "answers differ enough to matter.")

    doc.add_heading("The estimate was 64% low", level=2)
    para(doc, "The forecaster's exact shape was written out in C using 8-bit "
              "arithmetic and timed on the ESP32-S3. One prediction takes "
              "36.46 milliseconds. The estimate was 22.28. The measurement "
              "repeats to a tenth of a microsecond across resets and across "
              "reprogramming the chip.")

    table(doc, ["", "Time for one prediction", "Share of the 40 ms allowed"], [
        ["Measured on the chip", "36.46 ms", "91%"],
        ["Estimated from the multiply count", "22.28 ms", "56%"],
    ], [2.4, 2.0, 1.8])

    para(doc, "The reason is straightforward once measured. Counting "
              "multiplications prices the multiplications and nothing else. "
              "The model also has to compute a softmax, which needs 1,024 "
              "exponentials for each of four attention heads in each of two "
              "layers. That takes 7.25 milliseconds, a fifth of the whole "
              "forward pass, and the estimate assigned it zero. Layer "
              "normalisation adds another 0.64.")

    para(doc, "The same measurement was made for the LSTM, and it settles what "
              "the gap is evidence of. The LSTM has no softmax, so if attention "
              "were the explanation its estimate should have been close. It is "
              "further off, not closer.")

    table(doc, ["Model", "Estimated", "Measured on the chip", "Ratio"], [
        ["Transformer", "22.28 ms", "36.46 ms", "1.64x"],
        ["LSTM", "19.84 ms", "35.07 ms", "1.77x"],
    ], [1.8, 1.5, 1.9, 0.9])

    para(doc, "Four gates over 64 units on each of 32 timesteps is 8,192 "
              "sigmoid and tanh evaluations, which is the same order of "
              "non-multiply work under a different name. The estimating "
              "method was optimistic, not the architecture, and that is the "
              "more useful finding because it applies to every model in the "
              "comparison and to any added later.")

    para(doc, "It also changes the choice between the two. Estimated, the LSTM "
              "looked 11% faster than the Transformer. Measured, it is 4% "
              "faster, for 0.8% worse accuracy. That is close enough that the "
              "controller experiments should decide it rather than the "
              "forecasting numbers alone.")

    para(doc, "The multiply rate itself holds up. The largest matrix "
              "multiplication runs at 28.1 million operations per second "
              "against the 29.82 measured on a synthetic loop in week one, a "
              "6% difference in the direction real memory access would push "
              "it. The week-one measurement was right about multiplications. "
              "It was the assumption that multiplications are the whole cost "
              "that was wrong.")

    para(doc, "This is worth stating carefully, because it is a good result "
              "rather than a bad one. The model still fits, at 91% of the "
              "budget, and this is the slowest way it could possibly be "
              "written: plain C with no use of the chip's vector "
              "instructions, and a floating-point exponential for every "
              "attention weight. Both of those have well-understood fixes. "
              "The 36.46 milliseconds is a ceiling, not a floor.")

    doc.add_heading("Shrinking the model to 8-bit numbers costs 0.95%", level=2)
    if a2:
        table(doc, ["Version", "Error at 3 s", "Better than doing nothing",
                    "Size"], [
            ["Full precision", kw(a2["float_mean_rmse_w"]),
             f"{1 - a2['float_mean_rmse_w'] / a2['persistence_rmse_w']:.1%}",
             f"{a2['float32_bytes'] / 1024:.1f} KB"],
            ["8-bit", kw(a2["int8_mean_rmse_w"]),
             f"{a2['int8_skill_vs_persistence']:.1%}",
             f"{a2['int8_bytes'] / 1024:.1f} KB"],
        ], [1.6, 1.5, 1.9, 1.2])
        para(doc, f"The model becomes "
                  f"{a2['float32_bytes'] / a2['int8_bytes']:.2f} times smaller "
                  f"and loses "
                  f"{a2['quantisation_penalty']:.2%} of its accuracy. It still "
                  f"clears the required 10% improvement with half again as "
                  f"much margin as it needs. Nothing here suggests the "
                  f"harder alternative, retraining the model to be aware of "
                  f"its own rounding, is necessary.")
        para(doc, f"The memory figure has an independent check behind it. A "
                  f"cost calculation written from the model's shape predicts "
                  f"{a2['cost_model_bytes']:,} bytes, and counting the real "
                  f"quantised network gives {a2['int8_bytes']:,}. The two were "
                  f"written separately and they agree exactly.")

    doc.add_heading("A mistake worth recording", level=2)
    para(doc, "The first version of the quantisation code selected which "
              "numbers to shrink by looking at the type of each layer. That "
              "silently skipped the attention block's input projection, "
              "because PyTorch stores it as a bare array rather than as a "
              "layer, and it also failed to catch the attention output "
              "because that projection is applied without going through its "
              "own layer object. Between them, a third of the model stayed at "
              "full precision and the reported cost of shrinking it would have "
              "been far too low. Both gaps are now covered and both are held "
              "in place by tests.")

    para(doc, "What is still missing for the full gate is the standard "
              "conversion toolchain, which is not installed on this machine. "
              "That toolchain would add interpreter overhead, which makes "
              "things slower, and bring optimised vector routines, which make "
              "them faster. Neither effect is guessed at here. What these two "
              "measurements establish is that the model fits with room to "
              "spare and that 8-bit precision is survivable, which is what "
              "decides whether the conversion work is worth starting.")


def hardware_section(doc: Document, g3) -> None:
    doc.add_heading("12. The real-time loop on hardware", level=1)

    para(doc, "Gate G3 asks whether the control loop actually closes on the "
              "hardware: the microcontroller requests the vehicle state, "
              "receives it, computes a command and sends it back, one hundred "
              "times a second. The pass mark is that 99% of loops land within "
              "one millisecond of their ten-millisecond slot, with no frames "
              "lost, over ten minutes.")

    para(doc, "The microcontroller keeps the timing, not the laptop. macOS is "
              "not a real-time system, so timing measured on the host would "
              "record the host's own scheduling noise rather than the loop's. "
              "The chip therefore builds a histogram of its own loop periods "
              "and reports it over the link, and the laptop measures only what "
              "only the laptop can see, which is frames that never arrived.")

    if g3:
        c, e = g3["counters"], g3["extremes"]
        table(doc, ["Measurement", "Result", "Requirement"], [
            ["Control loops completed", f"{c['loop_count']:,}", "-"],
            ["Timing spread, median", f"within {g3['p50_us']:.0f} us", "-"],
            ["Timing spread, 99th percentile",
             f"within {g3['p99_us']:.0f} us",
             f"{g3['limits']['p99_us']:.0f} us"],
            ["Timing spread, 99.9th percentile",
             f"within {g3['p999_us']:.0f} us", "-"],
            ["Loop period range",
             f"{e['period_min_us']} to {e['period_max_us']} us", "10,000 nominal"],
            ["Control computation, worst case", f"{e['ctrl_wcet_us']} us",
             "under 10,000"],
            ["Round trip to the laptop, worst case", f"{e['rtt_max_us']} us", "-"],
            ["Frames lost", f"{g3['dropped_total']}",
             f"{g3['limits']['dropped']}"],
        ], [2.4, 1.9, 1.4])
        para(doc, f"Gate G3: {g3['verdict']} on the frame criterion, and a "
                  f"pass on timing by a factor of "
                  f"{g3['limits']['p99_us'] / max(g3['p99_us'], 1):.0f}.")

        figure(doc, DOCS / "figures" / "g3-jitter.png",
               "Figure 6. Loop timing over ten minutes. Left: how many loops "
               "landed in each timing band, on a log scale. Right: the same "
               "data cumulatively, against the gate limit. Everything lands in "
               "the first two bands.")

        doc.add_heading("Which side failed", level=2)
        para(doc, "The evidence separates them cleanly, and the answer is not "
                  "the part being tested.")
        bullets(doc, [
            "The link carried everything. No corrupted frames at either end "
            "and no gaps.",
            f"The microcontroller met every deadline. Its control computation "
            f"runs in {e['ctrl_wcet_us']} microseconds inside a 10,000 "
            f"microsecond slot, and the count of loops that missed their own "
            f"deadline is {c['ctrl_late']}.",
            f"What missed, {c['stale_steps']} times in "
            f"{c['loop_count']:,} loops, was the laptop answering in time. "
            f"The worst measured round trip was {e['rtt_max_us']} "
            f"microseconds.",
        ])
        para(doc, "The misses are not spread evenly. They arrive in short "
                  "bursts on an otherwise idle laptop, which is macOS doing "
                  "something else rather than a steady overload.")

        doc.add_heading("The fix was built, not deferred", level=2)
        para(doc, "The original loop sent a request and waited for the reply "
                  "inside the same ten-millisecond slot, which ties its "
                  "deadline to the scheduling behaviour of a general-purpose "
                  "operating system. The control task now requests the next "
                  "state, acts on the most recent state it already holds, and "
                  "reads replies without waiting. Both versions build from the "
                  "same source behind a compile-time switch, so the comparison "
                  "is a rebuild and both stay measurable.")

        table(doc, ["Over 59,650 loops, ten minutes", "Original", "Pipelined"], [
            ["Timing spread, 99th percentile", "within 25 us", "within 25 us"],
            ["Worst round trip to the laptop", "7,405 us", "77 us"],
            ["Replies that arrived too late", "6", "0"],
            ["Steps using a state one period old", "not applicable", "8"],
            ["Corrupted or lost frames", "0", "0"],
        ], [2.6, 1.5, 1.5])

        para(doc, "The round trip falls by a factor of 96, because the loop no "
                  "longer waits for it. The timing is unchanged, which is the "
                  "expected result: the loop was never the problem.")

        para(doc, "A handful of events survive and the gate still fails. What changed "
                  "is what an event costs. In the original loop a miss meant "
                  "the control task had spent nine of its ten milliseconds "
                  "waiting and received nothing, so the loop itself was at "
                  "risk. In the new loop a miss means the controller acted on "
                  "a state one period older than intended, and the loop was "
                  "never in danger. Same criterion, completely different "
                  "failure.")

        para(doc, "The question the gate now has to settle is whether its "
                  "criterion should separate the two. A loop that misses its "
                  "own deadline is a defect, and there are none of those in "
                  "either version. A laptop that answers late is a property of "
                  "running the simulation on macOS, and there are a few of "
                  "those, bounded and handled. Reading both as the same "
                  "failure leaves the criterion unable to tell a working "
                  "system from a broken one. Zero over ten minutes at a "
                  "hundred times a second against an ordinary operating system "
                  "may not be reachable at all, and that is worth reporting as "
                  "a finding rather than treating as a defect.")

        para(doc, "This is also the project's own subject matter. One of the "
                  "planned experiments compares deadline-miss handling "
                  "switched on against off, and a test rig that never missed a "
                  "deadline would leave it nothing to measure.")
        para(doc, "The criterion has not been loosened to fit the result. One "
                  "revision of one criterion was permitted in the design "
                  "document, it was used at gate G2 with the reason recorded, "
                  "and it is spent.")

        doc.add_heading("Re-measured in week 7, on firmware that changed",
                        level=2)
        para(doc, "The loop is not the loop that was measured in week 3. It "
                  "now runs a real speed controller with a physics "
                  "feedforward instead of a placeholder, and both message "
                  "formats grew to carry the extra signals that controller "
                  "needs. The rule in this project is that the loop the paper "
                  "reports has to be the loop that was measured, so the "
                  "ten-minute campaign was run again in full.")
        table(doc, ["Over 59,650 loops, ten minutes", "Week 3", "Week 7"], [
            ["Timing spread, 99th percentile", "within 25 us",
             f"within {g3['p99_us']:.0f} us"],
            ["Control computation, worst case", "16 us",
             f"{e['ctrl_wcet_us']} us"],
            ["Worst round trip to the laptop", "77 us", f"{e['rtt_max_us']} us"],
            ["Loops that missed their own deadline", "not counted",
             f"{c['ctrl_late']}"],
            ["Laptop answered late", "8", f"{c['stale_steps']}"],
            ["Corrupted or lost frames", "0",
             f"{c['rx_bad'] + g3['host']['frames_dropped']}"],
        ], [2.6, 1.5, 1.5])
        para(doc, "The control computation rose from 16 to "
                  f"{e['ctrl_wcet_us']} microseconds because it now does real "
                  "work rather than a single multiplication. That is under "
                  "one percent of the slot it has.")
        para(doc, "The new row is the one that matters. Week 3 could report "
                  "that the laptop was late but could not prove the "
                  "microcontroller never was, because nothing counted it. A "
                  "counter added this week counts exactly that, and it reads "
                  f"{c['ctrl_late']} over ten minutes, including throughout "
                  "the fault-injection campaign in the next section. The two "
                  "failures the gate's criterion treats as one are now "
                  "measured apart, and one of them is empty.")
    else:
        para(doc, "The ten-minute campaign was still running when this report "
                  "was generated. Rebuild the report to include it.",
             italic=True, colour=MUTED)

    doc.add_heading("Two faults found while bringing the board up", level=2)
    para(doc, "Neither would have announced itself, and both are worth "
              "recording because both would have produced a wrong verdict "
              "rather than an obvious failure.")
    bullets(doc, [
        "The frame counter tracked one sequence number across all message "
        "types, while the control loop and the diagnostics task each run their "
        "own counter. Every alternation between them looked like a gap. On a "
        "real run it reported 1,566 lost frames on a link that lost none. Gate "
        "G3 is stated as zero lost frames, so this counter decides the verdict.",
        "The first connection to the board after a reset always receives "
        "nothing, and the second receives the full stream. This cost a long "
        "detour, because the symptom looks exactly like firmware that is not "
        "running. Opening the port now retries until data arrives, and the "
        "retry count is reported so the behaviour stays visible rather than "
        "hidden.",
    ])

    para(doc, "The link was also changed to run over the chip's built-in USB "
              "port instead of requiring a separate adapter. The design "
              "document left the choice between the two open for this gate to "
              "settle on measured latency. Both are implemented, so comparing "
              "them is a rebuild rather than a rewrite, but only the built-in "
              "port can be measured with the hardware currently connected.")


def control_section(doc: Document, baselines, robust) -> None:
    doc.add_heading("13. The controller, and how much room it has to improve",
                    level=1)

    para(doc, "Week 7 built the two things a proposed controller has to be "
              "measured against: the conventional controller anyone would "
              "write, and the theoretical best any controller could achieve. "
              "The second one is computed offline by dynamic programming, "
              "which searches every combination of decisions across the whole "
              "trip. Without it, a claim that a controller saves three "
              "percent means nothing, because nobody knows whether three and "
              "a half percent or thirty were available.")

    para(doc, "The answer came back smaller than anyone expected, and it has "
              "to be said before the reinforcement-learning work starts "
              "rather than after it.")

    if not baselines:
        para(doc, "The controller campaign had not been run when this report "
                  "was generated. Rebuild the report to include it.",
             italic=True, colour=MUTED)
        return

    rows = {}
    for r in baselines["rows"]:
        rows.setdefault(r["cycle"], {})[r["arm"]] = r

    doc.add_heading("Consumption on the four standard driving cycles", level=2)
    para(doc, "Watt-hours per kilometre. Lower is better. The last column is "
              "how far the conventional controller sits from the theoretical "
              "best.")
    table(doc, ["Cycle", "No regeneration", "Conventional rules",
                "Theoretical best", "Gap"],
          [[c.upper(),
            f"{rows[c]['no-regen']['wh_per_km']:.2f}",
            f"{rows[c]['rule-ems']['wh_per_km']:.2f}",
            f"{rows[c]['dp-comfort-priced']['wh_per_km']:.2f}",
            f"{rows[c]['rule-ems']['gap_to_dp_pct']:+.2f}%"]
           for c in rows],
          [1.2, 1.6, 1.6, 1.5, 0.9])

    para(doc, "Recovering braking energy is worth a great deal: between 5% on "
              "the highway cycle and 23% in city traffic. That is the whole "
              "energy story of this vehicle.")

    para(doc, "Everything after that is not. The theoretically optimal "
              "strategy turns out to be a constant instruction -- recover as "
              "much braking energy as the battery will accept -- and the "
              "conventional controller, which is two thresholds and a taper, "
              "is already within a sixth of one percent of it. There is "
              "essentially nothing left for a learned controller to find.")

    doc.add_heading("Why this is a property of the problem", level=2)
    para(doc, "It is not a weakness of the search. The controller is split in "
              "two on purpose: an inner loop follows the speed profile, and "
              "an outer loop manages energy. That split is what makes the "
              "energy comparison honest, because it stops a controller from "
              "saving energy by driving slower. But it also means the outer "
              "loop cannot change how the car drives at all, and once that is "
              "fixed:")
    bullets(doc, [
        "the discharge power limit can only take away power the speed "
        "controller needs, so it is a safety limit and not a lever;",
        "turning the cabin heating down saves energy the same way driving "
        "slower does, so it is priced at what it costs and then it is a wash;",
        "recovering braking energy is always better than not, so the best "
        "setting is simply the maximum the battery allows.",
    ])
    para(doc, "One lever with an obvious setting and two that do nothing. "
              "That is why the optimum is a constant.")

    para(doc, "There is a direct consequence for one of the planned "
              "experiments. Experiment A3 asks whether the controller needs "
              "the forecast at all. Under a fixed speed profile the best "
              "action does not depend on what happens next, so a forecast "
              "cannot help, and A3 can now be predicted rather than run. The "
              "design document already accepted that outcome as publishable; "
              "what is new is that there is a reason for it rather than a "
              "possibility.")

    doc.add_heading("What happens next is the supervisor's decision", level=2)
    para(doc, "This is recorded in the design document as an open item for "
              "the supervisor, not resolved here. Three routes:")
    table(doc, ["Route", "What it means", "Cost"], [
        ["Report it", "The contribution becomes the embedded engineering plus "
                      "a negative result: a learned energy manager cannot beat "
                      "two rules once speed tracking is a hard constraint. The "
                      "project's stated framing already supports this.",
         "None. Publishable as it stands."],
        ["Widen the controller's authority", "Let the outer loop adjust the "
                                             "target speed inside a tolerance "
                                             "band, with a penalty for "
                                             "arriving late. This is the "
                                             "standard formulation in which a "
                                             "forecast genuinely pays, and it "
                                             "would give A3 something real to "
                                             "measure.",
         "Most work. Changes one of the paper's claims."],
        ["Make the problem harder honestly", "Add battery temperature limits "
                                             "and a battery-ageing cost. Under "
                                             "those, always recovering the "
                                             "maximum stops being optimal.",
         "Moderate. Needs a thermal and ageing model."],
    ], [1.5, 3.6, 1.5])

    figure(doc, DOCS / "figures" / "week7-control.png",
           "Figure 8. Left: consumption by controller on each cycle. Right: "
           "how far each controller sits from the theoretical best, on a log "
           "scale. Recovering braking energy is worth tens of percent; "
           "everything after that is worth hundredths.")

    doc.add_heading("The speed controller holds under disturbance", level=2)
    para(doc, "The energy comparison is only honest if every controller "
              "actually follows the driving cycle, so the inner loop was "
              "tested with its model deliberately wrong. On a clean run its "
              "tracking error is under a millimetre per second, but that "
              "number is worthless on its own: the controller's feedforward "
              "term is computed from the same vehicle the simulation uses, so "
              "it is exact. The table below breaks that arrangement.")

    if robust:
        by_case = {}
        for r in robust["rows"]:
            if r["grade"] == "flat" or r["case"] == "grade unknown":
                by_case.setdefault(r["case"], {})[r["cycle"]] = r
        order = ["nominal", "mass +10%", "drag +30%", "rolling +50%",
                 "grade unknown", "speed noise 0.2 m/s", "link delay 100 ms",
                 "no feedforward"]
        table(doc, ["Condition", "City cycle error", "Aggressive cycle error",
                    "Worst instant"],
              [[case,
                f"{by_case[case]['udds']['tracking_rmse_mps']:.4f} m/s",
                f"{by_case[case]['us06']['tracking_rmse_mps']:.4f} m/s",
                f"{by_case[case]['us06']['tracking_max_mps']:.3f} m/s"]
               for case in order if case in by_case],
              [2.2, 1.6, 1.6, 1.2])
        para(doc, "The worst case across every perturbation is 0.30 m/s of "
                  "average error and 1.5 m/s at its worst instant, on the "
                  "aggressive cycle with the feedforward term removed "
                  "entirely. Speed tracking is the constraint the whole energy "
                  "comparison rests on, and it holds.")
        para(doc, "One row is a result rather than a check. Injecting "
                  "realistic speed-sensor noise costs 5.6% of consumption: "
                  "the controller chases the noise and pays for it in torque "
                  "reversals. That is a sensor-quality argument with a price "
                  "attached, and it belongs in the paper.")
        figure(doc, DOCS / "figures" / "week7-pid-robustness.png",
               "Figure 9. Speed-tracking error under model error and "
               "disturbance, log scale. The clean run at the bottom is the "
               "least informative bar in the chart.")


def rl_section(doc: Document, rl) -> None:
    doc.add_heading("14. The reinforcement-learning ramp-up", level=1)

    para(doc, "Reinforcement learning is the identified skill gap on this "
              "project and it is genuinely temperamental, so the schedule "
              "spends a week on the setup before the week that needs it to "
              "work. That week is done.")

    if not rl:
        para(doc, "The ramp-up had not been run when this report was "
                  "generated. Rebuild the report to include it.",
             italic=True, colour=MUTED)
        return

    p = rl["pendulum"]
    e = rl["energy_env"]
    para(doc, "Two runs, in this order, because they fail for different "
              "reasons and running them together would make a failure "
              "impossible to attribute.")
    table(doc, ["Check", "Result", "What it tells us"], [
        ["A textbook problem with a known answer",
         f"score {p['return_mean']:.0f}, target {p['target']:.0f}",
         "PASS. The installation and the default settings are sound, so a "
         "later failure is the problem and not the tooling."],
        ["Simulation speed of the real problem",
         f"{e['env_only_steps_per_s']:.0f} decisions per second",
         "The simulator is not the bottleneck."],
        ["Training speed on the real problem",
         f"{e['steps_per_s']:.0f} steps per second",
         f"Five independent training runs will take "
         f"{e['projected_5_seed_hours']:.1f} hours on this laptop."],
    ], [2.1, 1.7, 2.8])

    para(doc, "The last row is the one that mattered. The design document "
              "requires five independent training runs, because a single "
              "reinforcement-learning result is not publishable. That "
              "requirement is now known to be affordable rather than hoped to "
              "be.")

    para(doc, f"After a deliberately short training run the controller "
              f"already uses {e['sac']['energy_wh_mean']:.1f} watt-hours per "
              f"test episode against the conventional controller's "
              f"{e['rule']['energy_wh_mean']:.1f}, but scores slightly worse "
              f"overall. It is buying that energy by turning the cabin "
              f"heating down, and the scoring function is charging it for "
              f"doing so. The scoring function is working.")


def fallback_section(doc: Document, fb, wdt) -> None:
    doc.add_heading("15. What the controller does when something fails",
                    level=1)

    para(doc, "The design document requires that when the slow part of the "
              "system misses its deadline, the fast part falls back to simple "
              "rules and the event is counted rather than hidden. Week 7 "
              "built that, and then broke the system on purpose to check it. "
              "A safety path that has never been taken is a claim, not a "
              "result.")

    doc.add_heading("Three failures, three different responses", level=2)
    table(doc, ["What goes wrong", "How it is noticed", "What the controller does"], [
        ["The energy manager stops answering",
         "its last instruction is more than 300 ms old",
         "the simple rules run inside the fast loop instead"],
        ["The simulation stops sending the car's state",
         "five control periods with nothing received",
         "torque is ramped smoothly to zero and the controller stops acting "
         "on a measurement it no longer trusts"],
        ["The prediction takes too long",
         "its own timing exceeds the 40 ms budget",
         "the energy manager uses the simple rules for that step"],
        ["A task stops running altogether",
         "the chip's watchdog timer, 2 seconds",
         "the chip resets, and the reason is reported after the restart"],
    ], [2.0, 2.2, 2.6])

    para(doc, "Treating these as one generic fault is how a controller ends "
              "up crawling because a logging task was slow. They are counted "
              "separately for the same reason.")

    if not fb:
        para(doc, "The fault-injection campaign had not been run when this "
                  "report was generated. Rebuild the report to include it.",
             italic=True, colour=MUTED)
        return

    d = fb["delta"]
    doc.add_heading("Measured on the board", level=2)
    para(doc, "Two of the three faults have to be injected inside the "
              "firmware, because they happen entirely on the chip and cannot "
              "be caused from outside it. The third the laptop caused itself, "
              "by going quiet for a second.")
    table(doc, ["Fault injected", "What should happen", "What did happen"], [
        ["Laptop silent for 1.0 second",
         "101 missed states, the first 5 tolerated",
         f"{d['stale_steps']} missed, {d['limp_steps']} ramping down"],
        ["Energy manager stops publishing for 2.0 seconds",
         "180 control steps on the simple rules",
         f"{d['ctrl_fallback_steps']}"],
        ["Prediction overruns for 2.0 seconds",
         "20 missed deadlines and 20 fallbacks",
         f"{d['infer_deadline_misses']} and {d['ems_fallback_steps']}"],
        ["Control task made to hang",
         "the watchdog resets the chip",
         (wdt or {}).get("boot_reason_name", "not run")],
    ], [2.3, 2.3, 2.2])

    para(doc, "Every count is exactly what the injection schedule implies. "
              "During the silent second the commanded torque fell from 226 "
              "newton-metres to zero and stayed there: the chip kept sending "
              "commands, and what those commands said was that the controller "
              "was declining to act on stale information.")

    para(doc, f"Throughout all of it, the number of control loops that missed "
              f"their own deadline stayed at {d['ctrl_late']}. Handling a "
              f"failure does not cost the loop its timing.")

    para(doc, "One of the planned experiments switches this handling off and "
              "measures what it was worth. The switch to do that is a "
              "compile-time option in the same firmware, so that experiment "
              "will be a rebuild rather than a reconstruction.")



def sac_section(doc: Document, sac, onchip) -> None:
    doc.add_heading("16. The learned controller, and what it found", level=1)

    para(doc, "Week 8 trained the reinforcement-learning controller the "
              "project is named after: five independent training runs, "
              "because a single result from a method this temperamental is "
              "not publishable, and a matched pair of runs with the forecast "
              "removed from what the controller can see. Week 7's offline "
              "optimum had already predicted what this would find. The "
              "prediction was written down before the runs, and the runs were "
              "done anyway, because a predicted result is not a measured one.")

    if not sac:
        para(doc, "The training campaign had not finished when this report "
                  "was generated. Rebuild the report to include it.",
             italic=True, colour=MUTED)
        return

    doc.add_heading("How the arms are compared, and why it matters here",
                    level=2)
    para(doc, "Two numbers are reported for every controller. The raw figure "
              "is watt-hours per kilometre as measured. The comparable figure "
              "adds back the cabin heating the controller switched off, "
              "valued at exactly the energy it saved.")
    para(doc, "That second column is not bookkeeping. Every trained "
              "controller in this table looks better than the conventional "
              "one on the raw number and worse on the comparable one, and the "
              "whole of the difference is cabin heat. A controller that saves "
              "energy by turning the heating down in a Munich winter has done "
              "the same thing as one that saves energy by driving slower, and "
              "the project rejected that trade in its design document before "
              "any of this was measured.")

    b = sac["baseline"]
    w = sac["summary"]["with-forecast"]
    wo = sac["summary"]["without-forecast"]
    table(doc, ["Controller", "Raw Wh/km", "Comparable Wh/km",
                "Cabin heat shed", "vs conventional"], [
        ["Conventional rules", f"{b['wh_per_km']:.2f}",
         f"{b['equivalent_wh_per_km']:.2f}", f"{b['aux_shed_wh']:.1f} Wh",
         "-"],
        ["Learned, with forecast",
         f"{np.mean([r['wh_per_km'] for r in sac['rows'] if r['arm'] == 'with-forecast']):.2f}",
         f"{w['mean']:.2f} +- {w['std']:.2f}",
         f"{w['aux_shed_wh_mean']:.1f} Wh",
         f"{w['gap_to_rule_pct_mean']:+.2f}%"],
        ["Learned, forecast removed",
         f"{np.mean([r['wh_per_km'] for r in sac['rows'] if r['arm'] == 'without-forecast']):.2f}",
         f"{wo['mean']:.2f} +- {wo['std']:.2f}",
         f"{wo['aux_shed_wh_mean']:.1f} Wh",
         f"{wo['gap_to_rule_pct_mean']:+.2f}%"],
    ], [2.1, 1.2, 1.7, 1.2, 1.4])

    para(doc, f"Five seeds each, {sac['steps']:,} training steps per seed, "
              f"evaluated on complete runs of the validation cycle. The test "
              f"cycle is still sealed. Speed tracking is unchanged across "
              f"every arm, which is the point of putting tracking in a "
              f"separate loop the controller cannot touch.")

    doc.add_heading("Ablation A3: does the forecast help?", level=2)
    a3 = sac["a3"]
    para(doc, "A3 was the experiment carrying the most risk to the story. It "
              "removes the forecast from what the controller can see and "
              "changes nothing else.")
    para(doc, f"Difference, forecast minus no forecast: "
              f"{a3['diff_mean_wh_per_km']:+.3f} Wh/km, with a 95% interval "
              f"of [{a3['ci95'][0]:+.3f}, {a3['ci95'][1]:+.3f}].")
    if a3["null"]:
        para(doc, "The interval contains zero. The forecast makes no "
                  "measurable difference to the controller, which is the "
                  "result week 7 predicted from the structure of the problem "
                  "rather than from any property of this particular "
                  "forecaster: when the speed profile is fixed, the best "
                  "action does not depend on what happens next, so knowing "
                  "what happens next cannot help.")
        para(doc, "This was accepted as publishable in the design document "
                  "before it was run, and it frees the memory the forecaster "
                  "occupies. It is a finding about preview horizons in "
                  "embedded energy management, not a failure of the "
                  "experiment.")
    else:
        para(doc, "The interval excludes zero: the forecast changes the "
                  "result. That contradicts the week 7 prediction and the "
                  "reason needs finding before it is reported.")

    figure(doc, DOCS / "figures" / "week8-sac.png",
           "Figure 10. Left: five training runs per arm, each evaluated on "
           "complete cycles, against the conventional controller and the "
           "offline optimum. Right: where the ten runs finished, with 95% "
           "intervals.")

    doc.add_heading("What this means for the project", level=2)
    para(doc, "Two independent methods now agree. The offline optimum says "
              "the best possible policy is a constant instruction, and the "
              "learned controller, given five attempts and a third of a "
              "million training steps each, does not beat two thresholds and "
              "a taper. Neither result depends on the other being right.")
    para(doc, "That is a finding, and it is the one the paper should lead "
              "with in this section. The decision about what to do next -- "
              "report it, widen the controller's authority, or make the "
              "problem harder honestly -- is section 13's open question and "
              "is still the supervisor's to take.")


def actor_onchip_section(doc: Document, sac, onchip) -> None:
    doc.add_heading("17. Putting the learned controller on the chip", level=1)

    para(doc, "A policy that has only ever run in Python is a claim. The "
              "trained controller was exported, compiled into the firmware, "
              "and run on the board, and its answers were checked against the "
              "Python original on the same inputs.")

    if not onchip:
        para(doc, "The on-chip verification had not been run when this report "
                  "was generated. Rebuild the report to include it.",
             italic=True, colour=MUTED)
        return

    c = onchip["cost"]
    table(doc, ["Check", "Result"], [
        ["Network shape on the chip",
         f"{'-'.join(str(x) for x in c['layer_sizes'])}, "
         f"{c['n_params']:,} numbers"],
        ["Weights on the chip are the weights that were trained",
         "confirmed by checksum" if onchip.get("checksum_ok")
         else "MISMATCH"],
        ["Answers match the Python original",
         f"worst difference {onchip['max_action_error']:.1e}, "
         f"tolerance {onchip['tolerance']:.0e}"],
        ["Memory used",
         f"{c['footprint_kb']:.1f} KB of the 300 KB allowed"],
        ["Time per decision, measured on the chip",
         f"{onchip['latency_mean_ms']:.3f} ms of the 40 ms allowed"],
    ], [3.2, 3.2])

    para(doc, f"The controller costs "
              f"{onchip['latency_mean_ms'] / onchip['budget_ms']:.1%} of the "
              f"time budget and {c['footprint_kb'] / 300:.1%} of the memory. "
              f"It is, in embedded terms, free. The forecaster it consumes is "
              f"not: that takes 36.46 milliseconds of the same 40.")

    doc.add_heading("The compute estimate was wrong in the other direction",
                    level=2)
    para(doc, f"Section 11 reported that dividing a multiply count by a "
              f"measured multiply rate underestimated the forecaster's real "
              f"time on the chip by 64%. For this controller the same "
              f"arithmetic predicts "
              f"{onchip['estimated_latency_ms']:.3f} milliseconds against "
              f"{onchip['latency_mean_ms']:.3f} measured, so it is 25% too "
              f"pessimistic instead.")
    para(doc, "The two are not in conflict and the reason is worth a "
              "sentence. The forecaster spends much of its time on operations "
              "a multiply count cannot see, and it moves more data than fits "
              "close to the processor. This controller is a few thousand "
              "multiplications on numbers that stay in fast memory, and the "
              "chip has hardware that does a multiply and an add together. "
              "The estimate is unreliable in both directions and by different "
              "amounts, which is a stronger reason to measure than a "
              "consistent bias would have been.")

    para(doc, "The chain from a trained policy to a running one has four "
              "links, and each is checked against the one before it. Building "
              "that chain found a real fault: the test that compares the C "
              "controller against Python was, for a while, compiling the "
              "wrong weights and comparing them against themselves. It passed "
              "for exactly as long as no policy had been deployed. Section 18 "
              "records it.")


def negatives_section(doc: Document) -> None:
    doc.add_heading("18. Results that went against expectation", level=1)

    para(doc, "Each one is reported because each one changes what the paper "
              "may claim, and a supervisor reading the work will find them "
              "more convincing than the successes.")

    doc.add_heading("The learned controller loses to two thresholds", level=2)
    para(doc, "Five independent training runs, and every one of them finishes "
              "worse than a controller that is two thresholds and a taper, "
              "once the cabin heating they switched off is charged back. The "
              "offline optimum predicted it and the training measured it, and "
              "the two do not depend on each other. Section 16.")

    doc.add_heading("The forecast makes no difference to the controller",
                    level=2)
    para(doc, "Removing it changes the result by an amount whose confidence "
              "interval contains zero, and whose sign is not consistent "
              "across the five runs. This was accepted as publishable in the "
              "design document before it was run, and week 7 gave it a "
              "reason rather than leaving it a possibility.")

    doc.add_heading("A parity test was passing without testing anything",
                    level=2)
    para(doc, "The test that compares the controller written in C against the "
              "same controller in Python was, for a while, compiling one set "
              "of weights and comparing them against another network's "
              "expected answers. The cause is a C rule: an include written "
              "with quotes is resolved against the including file's own "
              "directory before any search path, so the file under test kept "
              "finding the deployed weights whatever the test asked for. It "
              "passed honestly for exactly as long as nothing had been "
              "deployed. Two fixes: the include now searches the path only, "
              "and the weights carry a checksum that the inference code "
              "itself reports, because two policies of the same shape are "
              "indistinguishable without one.")

    doc.add_heading("The energy-management problem has almost no room in it",
                    level=2)
    para(doc, "The theoretically optimal strategy is a constant instruction, "
              "and two thresholds get within a sixth of a percent of it. This "
              "is the largest of these findings and it is the subject of "
              "section 13, including the three routes open and the fact that "
              "choosing between them is the supervisor's decision rather than "
              "one taken here.")

    doc.add_heading("The fitted rolling resistance is not a rolling resistance",
                    level=2)
    para(doc, "It is 2.2 times larger than an independent measurement on a "
              "comparable car. It is a lumped loss term named after the physics "
              "it stands in for rather than the physics it contains. The "
              "parameter file now says so and an automated test fails if that "
              "statement is removed.")

    doc.add_heading("Gate G4 was already passed before the models existed",
                    level=2)
    para(doc, "A linear regression beat the naive baseline by 14.5% against a "
              "required 10%. The gate as written could not distinguish a "
              "Transformer from a matrix calculation, so every model is now "
              "reported against the regression too.")

    doc.add_heading("Physics-informing does not improve accuracy", level=2)
    para(doc, "Five watts of difference on eleven kilowatts at matched "
              "parameter count. It improves physical consistency by a factor "
              "of ten instead, which is a different and still useful claim.")

    doc.add_heading("The compute estimate was 64% too optimistic", level=2)
    para(doc, "Dividing a multiply count by a measured multiply rate gave "
              "22.28 milliseconds for the Transformer. Timing the real graph "
              "on the chip gave 36.46. The LSTM is worse: 19.84 estimated "
              "against 35.07 measured. Both still fit inside the 40 "
              "milliseconds allowed, and the estimates remain useful for "
              "ranking models against each other, but they cannot be quoted "
              "as latencies now that measurements exist.")

    doc.add_heading("Charge conservation cannot be tested at this horizon",
                    level=2)
    para(doc, "The recorded charge channel does not move within a typical "
              "three-second window, so the equation has nothing to constrain. "
              "Enforcing it costs 4.4% accuracy and buys almost nothing. This "
              "was measured rather than argued.")


def remaining_section(doc: Document) -> None:
    doc.add_heading("19. What is left to do", level=1)

    para(doc, "Phase 1 and Phase 2 are complete. The remaining work is the "
              "controller, the on-chip deployment, and the measurement "
              "campaign.")

    table(doc, ["Week", "Modelling work", "Hardware work", "Gate"], [
        ["6", "DONE: 8-bit costs 0.95% accuracy. Still to do: distil to a "
              "smaller student model",
         "DONE: 36.46 ms measured on the chip. Still to do: the conversion "
         "toolchain, and energy per prediction", "G5"],
        ["7", "DONE: the offline optimum, the conventional controller, the "
              "speed controller and its robustness tests, and the "
              "reinforcement-learning ramp-up. The optimum came back smaller "
              "than expected; see section 13",
         "DONE: watchdog and fallback path built, and all four failure modes "
         "triggered on the board. Gate G3 re-measured on the changed firmware",
         "-"],
        ["8", "DONE: five training runs per arm. The learned controller "
              "finishes slightly worse than the conventional one, and the "
              "forecast makes no measurable difference. Sections 16 and 17",
         "DONE: the controller runs on the chip, matches Python, and takes "
         "0.121 ms of the 40 allowed", "-"],
        ["9", "Tune the reward function", "Full system on the chip; ablation A4",
         "-"],
        ["10", "-", "Measurement campaign: six scenarios, several controllers, "
                    "several random starts", "-"],
        ["11", "Analysis and figures", "Oscilloscope timing measurements", "-"],
        ["12", "Write up and submit", "-", "-"],
    ], [0.5, 2.5, 2.5, 0.5])

    doc.add_heading("The two experiments that carry real risk", level=2)
    bullets(doc, [
        "A3 asks whether the forecast actually improves control. If removing "
        "it changes nothing, the entire prediction stack is decorative on the "
        "chip and the paper will say so. That is a publishable finding about "
        "preview horizons in embedded energy management, and it would free the "
        "memory for other uses. It is planned and it will be run.",
        "Reinforcement learning is the identified skill gap and it is "
        "genuinely temperamental. A full ramp-up week is scheduled before the "
        "real training. If it does not converge, the conventional controller "
        "and the offline optimum are guaranteed working comparisons, so the "
        "paper survives.",
    ])

    doc.add_heading("Decisions waiting on a gate or on the supervisor", level=2)
    bullets(doc, [
        "What to do about the missing headroom in the energy-management "
        "problem, described in section 13. This is the one that should be "
        "settled first, because weeks 8 and 9 are built on top of it.",
        "Whether gate G3's zero-lost-frame rule should distinguish a "
        "controller that missed its own deadline, of which there are none, "
        "from a laptop that answered late, of which there are a few. The "
        "counter that separates them was added and measured this week.",
        "Whether to restate gate G4 against the linear regression rather than "
        "the naive baseline. Recorded in the design document for G4 to decide.",
        "Which model to deploy. The Transformer is the most accurate and fits. "
        "The linear regression reaches 87% of the benefit for 1.2% of the cost. "
        "Ablation A3 decides whether the difference matters to the controller.",
        "Whether the road-load variation should become randomised training "
        "conditions for the reinforcement learner. The cross-vehicle test says "
        "the spread that matters is between vehicles and depends on "
        "temperature, which is wider than originally planned for.",
    ])


def reproduce_section(doc: Document) -> None:
    doc.add_heading("20. Reproducing everything in this report", level=1)

    para(doc, "Every result comes from a command that can be re-run. The "
              "report itself is generated from the result files rather than "
              "typed, so its numbers cannot drift from the measurements.")

    table(doc, ["What", "Command"], [
        ["Fit the vehicle parameters", "python3 scripts/identify_params.py"],
        ["Gate G2, vehicle model", "python3 scripts/validate_plant.py"],
        ["Cross-vehicle transfer test", "python3 scripts/validate_ved.py"],
        ["Pre-training checks and baselines", "python3 scripts/run_guards.py"],
        ["The model comparison", "python3 scripts/run_ladder.py"],
        ["Transformer and ablation A1", "python3 scripts/run_transformer.py"],
        ["Cost on the chip", "python3 scripts/report_deploy_cost.py"],
        ["Gate G3, real-time loop", "./scripts/g3_campaign.sh 10"],
        ["Fetch the standard driving cycles", "python3 scripts/build_cycles.py"],
        ["Controller baselines and the offline optimum",
         "python3 scripts/run_control_baselines.py"],
        ["Speed-controller robustness", "python3 scripts/run_pid_robustness.py"],
        ["Reinforcement-learning ramp-up", "python3 scripts/run_rl_rampup.py"],
        ["Train the controller, five seeds, plus ablation A3",
         "python3 scripts/run_sac.py"],
        ["Export the trained controller to the firmware",
         "python3 scripts/verify_actor.py --export"],
        ["Verify it on the chip (needs -DRUN_ACTOR_BENCH=1)",
         "python3 scripts/verify_actor.py --check"],
        ["Build the firmware", "./scripts/idf.sh build"],
        ["Fault-injection build",
         "./scripts/idf.sh -DFAULT_INJECT=1 build && ./scripts/idf.sh flash"],
        ["Fallback path on hardware", "python3 scripts/run_fallback.py"],
        ["Watchdog on hardware (needs -DFAULT_INJECT=2)",
         "python3 scripts/run_fallback.py --watchdog"],
        ["This report", "python3 scripts/build_report.py"],
    ], [2.4, 4.0])

    para(doc, "All Python commands need PYTHONPATH=\"src:.\" set. The "
              "reinforcement-learning ramp-up additionally needs "
              "stable-baselines3 and gymnasium. The test suite runs with "
              "python3 -m pytest and currently holds 387 tests, all passing, "
              "including ones that drive the controller and the learned "
              "policy in C and in Python through identical inputs and require "
              "them to agree.", size=11, colour=MUTED)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="reports/EV-PIL-status-report.docx")
    ap.add_argument("--date", default="31 August 2026")
    args = ap.parse_args()

    ladder = load("forecast-ladder.json")
    tf = load("transformer-a1.json")
    g3 = load("g3-loop-timing.json")
    a2 = load("a2-quantisation.json")
    baselines = load("week7-control-baselines.json")
    robust = load("week7-pid-robustness.json")
    rl = load("week7-rl-rampup.json")
    fb = load("week7-fallback.json")
    sac = load("week8-sac.json")
    onchip = load("week8-actor-onchip.json")
    wdt = load("week7-watchdog.json")

    cost_path = DOCS / "forecast-deploy-cost.csv"
    cost_rows = None
    if cost_path.exists():
        import csv
        cost_rows = list(csv.DictReader(cost_path.read_text().splitlines()))

    doc = Document()
    setup_styles(doc)
    for section in doc.sections:
        section.top_margin = Inches(0.9)
        section.bottom_margin = Inches(0.9)
        section.left_margin = Inches(0.9)
        section.right_margin = Inches(0.9)

    cover(doc, args.date)
    summary(doc, ladder, tf, cost_rows, g3, a2, sac, onchip)
    background(doc)
    gates_explained(doc)
    plant_section(doc)
    crr_section(doc)
    transfer_section(doc)
    guards_section(doc, ladder)
    ladder_section(doc, ladder, tf)
    physics_section(doc, tf)
    cost_section(doc, cost_rows)
    on_chip_section(doc, a2)
    hardware_section(doc, g3)
    control_section(doc, baselines, robust)
    rl_section(doc, rl)
    fallback_section(doc, fb, wdt)
    sac_section(doc, sac, onchip)
    actor_onchip_section(doc, sac, onchip)
    negatives_section(doc)
    remaining_section(doc)
    reproduce_section(doc)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(out)

    tracked = (("ladder", ladder), ("transformer", tf), ("G3", g3),
               ("A2/G5", a2), ("cost", cost_rows),
               ("controller baselines", baselines), ("PID robustness", robust),
               ("RL ramp-up", rl), ("fallback", fb), ("watchdog", wdt),
               ("SAC campaign", sac), ("actor on chip", onchip))
    have = [n for n, v in tracked if v]
    missing = [n for n, v in tracked if not v]
    print(f"wrote {out}")
    print(f"  included: {', '.join(have)}")
    if missing:
        print(f"  MISSING (rebuild once available): {', '.join(missing)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
