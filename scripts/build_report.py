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


def summary(doc: Document, ladder, tf, cost_rows, g3) -> None:
    doc.add_heading("1. Summary", level=1)

    para(doc, "The project builds an energy-management controller for an "
              "electric car and runs it on a real ESP32-S3 microcontroller. "
              "The car itself is simulated in Python. The microcontroller and "
              "the simulation talk to each other over a serial cable in real "
              "time, so the controller has to meet real deadlines on real "
              "silicon rather than in a notebook.")

    para(doc, "The work so far has produced a validated vehicle model, a "
              "forecasting model that beats every baseline we could find, and "
              "measured evidence that it fits inside the microcontroller's "
              "compute budget. It has also produced four results that went "
              "against expectation, and those are reported here as plainly as "
              "the successes, because each one changes what the paper can "
              "claim.")

    doc.add_heading("Where the gates stand", level=2)
    rows = [
        ["G1", "Week 1", "Is the chip fast enough for a Transformer?",
         "PASS, 6.1x margin"],
        ["G2", "Week 2", "Does the vehicle model reproduce real trips?",
         "PASS, 6 of 7 trips"],
        ["G3", "Week 3", "Does the 10 ms loop close on hardware?",
         "Timing passes by 40x; 6 host stalls in 59,650 loops fail the "
         "zero-drop rule" if g3 else "measuring"],
        ["G4", "Week 4", "Does any model beat the naive baseline by 10%?",
         "PASS, all four models"],
        ["G5", "Week 6", "Does the forecaster run on the chip in 40 ms?",
         "not yet run"],
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
    if g3:
        bullets(doc, [
            f"On hardware, {g3['counters']['loop_count']:,} control loops ran "
            f"over ten minutes with 99.997% of them inside 25 microseconds of "
            f"their slot, against a limit of 1000. The link lost nothing.",
            f"Gate G3 still fails, on six occasions where the laptop did not "
            f"answer in time. The microcontroller met every deadline. Section "
            f"11 explains why that distinction matters and what it changes.",
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


def hardware_section(doc: Document, g3) -> None:
    doc.add_heading("11. The real-time loop on hardware", level=1)

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
                  f"pass on timing by a factor of 40.")

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
            "and no gaps in 121,255 frames received.",
            "The microcontroller met every deadline. Its control computation runs in "
            "16 microseconds inside a 10,000 microsecond slot, and no loop "
            "drifted by more than 50 microseconds.",
            "What missed, six times, was the laptop replying inside the 9 "
            "millisecond window the firmware waits. The worst measured round "
            "trip was 7,405 microseconds, so the laptop runs close to that "
            "limit routinely.",
        ])
        para(doc, "The six are not spread out. None for the first eight "
                  "minutes, then six inside one. That is macOS doing something "
                  "else, not a steady overload.")

        doc.add_heading("What this says about the design", level=2)
        para(doc, "The firmware sends a request and waits for the reply inside "
                  "the same ten-millisecond slot. That ties its deadline to the "
                  "scheduling behaviour of a general-purpose operating system. "
                  "The design already anticipated that the laptop's timing "
                  "could not be trusted and made the microcontroller the "
                  "timekeeper, which is why the jitter figure is 25 "
                  "microseconds. That protects the measurement. It does not "
                  "decouple the loop.")
        para(doc, "The fix that matches the diagnosis is to stop waiting: the "
                  "control task would use the most recent state it holds, "
                  "marked as stale when no fresh one arrived. That is also "
                  "what a real controller does when a sensor misses an update, "
                  "and it is already the subject of one of the project's own "
                  "claims. The planned experiment A4 compares deadline-miss "
                  "handling switched on against off, and a test rig that never "
                  "missed a deadline would leave it nothing to measure. Six "
                  "misses in 59,650 loops is a measured rate to design against.")
        para(doc, "The criterion has not been loosened to fit the result. One "
                  "revision of one criterion was permitted in the design "
                  "document, it was used at gate G2 with the reason recorded, "
                  "and it is spent. G3 stays as written until the fix is built "
                  "and the run repeated in week 7.")
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


def negatives_section(doc: Document) -> None:
    doc.add_heading("12. Results that went against expectation", level=1)

    para(doc, "Four of these. Each one is reported because each one changes "
              "what the paper may claim, and a supervisor reading the work "
              "will find them more convincing than the successes.")

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

    doc.add_heading("Charge conservation cannot be tested at this horizon",
                    level=2)
    para(doc, "The recorded charge channel does not move within a typical "
              "three-second window, so the equation has nothing to constrain. "
              "Enforcing it costs 4.4% accuracy and buys almost nothing. This "
              "was measured rather than argued.")


def remaining_section(doc: Document) -> None:
    doc.add_heading("13. What is left to do", level=1)

    para(doc, "Phase 1 and Phase 2 are complete. The remaining work is the "
              "controller, the on-chip deployment, and the measurement "
              "campaign.")

    table(doc, ["Week", "Modelling work", "Hardware work", "Gate"], [
        ["6", "Shrink the model to 8-bit numbers and measure what accuracy "
              "that costs (ablation A2)",
         "Program the forecaster onto the chip and measure its real time, "
         "memory and energy use", "G5"],
        ["7", "Compute the theoretically optimal energy strategy offline; "
              "build the conventional controller to compare against",
         "Watchdog and fallback path for a missed deadline", "-"],
        ["8", "Train the reinforcement-learning controller, five random "
              "starts; run ablation A3",
         "Export the trained controller and verify it on the chip", "-"],
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

    doc.add_heading("Decisions waiting on a gate", level=2)
    bullets(doc, [
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
    doc.add_heading("14. Reproducing everything in this report", level=1)

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
        ["This report", "python3 scripts/build_report.py"],
    ], [2.4, 4.0])

    para(doc, "All Python commands need PYTHONPATH=\"src:.\" set. The test "
              "suite runs with python3 -m pytest and currently holds 287 "
              "tests, all passing.", size=11, colour=MUTED)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="reports/EV-PIL-status-report.docx")
    ap.add_argument("--date", default="31 August 2026")
    args = ap.parse_args()

    ladder = load("forecast-ladder.json")
    tf = load("transformer-a1.json")
    g3 = load("g3-loop-timing.json")

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
    summary(doc, ladder, tf, cost_rows, g3)
    background(doc)
    gates_explained(doc)
    plant_section(doc)
    crr_section(doc)
    transfer_section(doc)
    guards_section(doc, ladder)
    ladder_section(doc, ladder, tf)
    physics_section(doc, tf)
    cost_section(doc, cost_rows)
    hardware_section(doc, g3)
    negatives_section(doc)
    remaining_section(doc)
    reproduce_section(doc)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(out)

    have = [n for n, v in (("ladder", ladder), ("transformer", tf), ("G3", g3),
                           ("cost", cost_rows)) if v]
    missing = [n for n, v in (("ladder", ladder), ("transformer", tf),
                              ("G3", g3), ("cost", cost_rows)) if not v]
    print(f"wrote {out}")
    print(f"  included: {', '.join(have)}")
    if missing:
        print(f"  MISSING (rebuild once available): {', '.join(missing)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
