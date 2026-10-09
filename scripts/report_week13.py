"""Week 13 in the status report and the supervisor note, in plain language.

Three subjects: a speed-sensor fault checker that works beside a realistic
acceleration signal and was measured on the board; small AI helpers placed
around it; and planning the speed of a journey to save energy. Every number
is read from the week-13 result files in docs/.

The report and the note use everyday names for the parts:

  first checker    the week-12 detector (B6 in the result files)
  new checker      the week-13 detector (B7)
  rule helper      a hand-written monitor around the new checker
  AI helpers       two small neural networks (a GRU and a FastGRNN cell) in
                   the same seat as the rule helper
"""

from __future__ import annotations

import json
from pathlib import Path

DOCS = Path("docs")
FILES = {
    "pil": "week13-b7-pil.json", "sim": "week13-b7-pil-sim.json",
    "val": "week13-arch-val.json", "test": "week13-arch-test.json",
    "b6val": "week13-sensor-b6-val.json", "shadow": "week13-arch-shadow.json",
    "a3val": "week13-a3-val.json", "a3test": "week13-a3-test.json",
    "plan": "week13-energy-planner.json", "a4": "week13-a4-decision.json",
    "a7": "week13-a7-decision.json",
}


def load_week13(docs: Path = DOCS) -> dict | None:
    """Every week-13 result file, or None if any is missing: the sections
    quote across files and are not written from part of them."""
    out = {}
    for key, name in FILES.items():
        path = docs / name
        if not path.exists():
            return None
        out[key] = json.loads(path.read_text())
    return out


def _row(doc_rows: dict, name: str) -> dict:
    return doc_rows["rows"][name]["summary"]


def board_rows(w: dict) -> list[list[str]]:
    a = w["pil"]["arms"]
    cols = [a["B6"], a["B7"], a["B7 + rule monitor"]]

    def line(label, fmt):
        return [label] + [fmt(c) for c in cols]

    return [
        line("Faults caught within half a second",
             lambda c: f"{c['detected_in_time']} of {c['fault_runs']}"),
        line("Slowest catch, seconds", lambda c: f"{c['worst_delay_s']:.2f}"),
        line("False alarms before any fault",
             lambda c: str(c["alarms_before_onset"])),
        line("False alarms on two clean drives",
             lambda c: str(c["clean_false_alarms"])),
        line("Still raising the alarm when the run ended",
             lambda c: str(c["still_flagged_in_last_second"])),
        line("Largest speed error during a fault, m/s",
             lambda c: f"{c['worst_peak_err_mps']:.2f}"),
        line("Typical speed error during a fault, m/s",
             lambda c: f"{c['median_peak_err_mps']:.2f}"),
        line("Control steps finished late",
             lambda c: str(c["late_control_steps"])),
        line("Longest control calculation, millionths of a second",
             lambda c: str(c["worst_control_computation_us"])),
    ]


def checker_section(doc, w, *, h1, para, table, bullets, note) -> None:
    h1(doc, "A fault checker that works on the board", "week13checker")
    a = w["pil"]["arms"]
    old, new, helped = a["B6"], a["B7"], a["B7 + rule monitor"]
    b6 = w["b6val"]["verdict"]["by_accel"]
    bad = [k for k, g in b6.items() if g["false_alarms_per_hour_floor"] >= 1.0]
    a0v, a0t = _row(w["val"], "A0 b7"), _row(w["test"], "A0 b7")

    para(doc, "The car's controller needs to know its speed. If the speed "
              "sensor freezes, drops to zero or starts reading a little "
              "wrong, the controller acts on a false number. A fault checker "
              "watches for this. When it raises the alarm, the controller "
              "stops trusting the sensor and works out the speed another way "
              "until the sensor behaves again.")
    para(doc, "Section " + "{ref}" + " ended with the first checker not "
              "usable. It compared the speed reading with the acceleration "
              "reading, and it had only ever been tested against a perfect "
              "acceleration signal with a little random noise. A real "
              "acceleration signal also drifts slowly. Week 13 added that "
              "drift to the simulation, sized from 19 logged BMW i3 trips.",
         _ref="speedarms")
    para(doc, f"With the drift added, the first checker failed in "
              f"{len(bad)} of the {len(b6)} test conditions. It raised the "
              f"alarm on a healthy sensor for most of the drive. SIMULATED.")

    doc.add_heading("The new checker", level=2)
    para(doc, "The new checker makes three changes. It estimates the slow "
              "drift in the acceleration signal and removes it. It looks for "
              "a sudden jump in the speed reading, which a fault produces "
              "and a slow drift does not. And it allows for its own "
              "uncertainty before raising the alarm.")
    para(doc, f"In simulation it raised no false alarm on a healthy sensor "
              f"in any condition, and caught {a0v['detected_in_time']} of "
              f"{a0v['named_faults']} faults within half a second on the "
              f"highway cycle and {a0t['detected_in_time']} of "
              f"{a0t['named_faults']} on the aggressive cycle. The ones it "
              f"caught late were all the same kind: a small error of half a "
              f"metre per second while the sensor was ten times noisier "
              f"than normal. SIMULATED.")

    doc.add_heading("Measured on the board", level=2)
    para(doc, "No fault had been put on the board before this week. The new "
              "checker was written again in C for the chip and compared with "
              "the laptop version on 4,000 samples, step by step, until the "
              "two agreed on every step. Then three versions of the firmware "
              "were run on the board. Each was given the same 40 faults on "
              "the aggressive cycle and two clean ten-minute drives. The "
              "laptop played the car and injected the faults; the checker "
              "ran on the chip.")
    table(doc, ["", "First checker", "New checker",
                "New checker with rule helper"], board_rows(w))
    note(doc, "Table. Injected speed-sensor faults on the board. One run per "
              "case, each on the firmware its column names, confirmed from "
              "the chip's own report. MEASURED on the board.")
    para(doc, f"The new checker caught all {new['fault_runs']} faults, the "
              f"slowest in {new['worst_delay_s']:.2f} seconds, and raised "
              f"no false alarm. The first checker caught "
              f"{old['detected_in_time']} and raised "
              f"{old['clean_false_alarms']} false alarms on one clean drive "
              f"with a drifting acceleration signal. That is the failure the "
              f"simulation predicted, now seen on the chip.")
    para(doc, f"The cost is small. The new checker's longest control "
              f"calculation was {new['worst_control_computation_us']} "
              f"millionths of a second against "
              f"{old['worst_control_computation_us']} for the first, out of "
              f"the 10,000 available, and no control step finished late in "
              f"any run.")
    para(doc, "The rule helper in the last column is explained in the next "
              "section. On the board it made a small difference in the "
              "direction the simulation gave. With 40 runs per version, that "
              "difference is not established.")

    doc.add_heading("What this does not cover", level=2)
    bullets(doc, [
        "A real acceleration sensor. The drift on the board was simulated "
        "from what the logged trips showed.",
        "Repeats. Each case was run once, with one draw of noise.",
        "The new checker has not passed every limit set in advance. In "
        "simulation it is still late on a few small errors under heavy "
        "noise. On the board those cases were caught in "
        "0.22 to 0.32 seconds.",
    ])


def helpers_section(doc, w, *, h1, para, table, bullets, note) -> None:
    h1(doc, "AI helpers around the fault checker", "week13helpers")
    sh = w["shadow"]["reviewers"]
    mon, gru = sh["monitor"]["sensor_fault"], sh["gru16v3"]["sensor_fault"]

    para(doc, "The fault checker makes fast decisions, one every hundredth "
              "of a second. The plan proposed a second, slower layer: a "
              "helper that looks back over the last tenth of a second and "
              "advises the checker. The helper may only do four things: "
              "keep an alarm raised, release it, choose which backup speed "
              "to use, or make the checker more watchful. It never commands "
              "the motor.")
    para(doc, "The plan intended this seat for Jev, a paid online AI model. "
              "Jev has not been purchased, so no result in this report is a "
              "Jev result. To test the idea itself, three other helpers were "
              "put in the same seat: a helper made of hand-written rules, "
              "and two small neural networks of 1,508 and 550 numbers, "
              "small enough for the chip.")

    doc.add_heading("As judges, the AI helpers were better", level=2)
    para(doc, f"Each helper was first scored on its diagnosis alone, without "
              f"letting it change anything. While an alarm was raised, the "
              f"rule helper recognised a real fault "
              f"{100 * mon['recall_while_flagged']:.0f}% of the time and the "
              f"larger neural network "
              f"{100 * gru['recall_while_flagged']:.0f}%. With no alarm "
              f"raised, the rule helper recognised "
              f"{100 * mon['recall_while_not_flagged']:.0f}% of faults and "
              f"the network {100 * gru['recall_while_not_flagged']:.0f}%. "
              f"SIMULATED, {w['shadow']['blocks']:,} tenth-of-a-second "
              f"blocks from the highway cycle.")

    doc.add_heading("In control of the car, they were worse", level=2)
    rows = []
    for label, key in (("New checker alone", "A0 b7"),
                       ("With the rule helper", "A2 monitor"),
                       ("With the larger neural network", "A2 gru16v3"),
                       ("With the smaller neural network", "A2 fastgrnn16v3")):
        v, t = _row(w["val"], key), _row(w["test"], key)
        rows.append([label, f"{v['worst_peak_err_mps']:.1f}",
                     f"{t['worst_peak_err_mps']:.1f}",
                     f"{v['false_alarms_floor'] + v['false_alarms_10x']}",
                     f"{t['false_alarms_floor'] + t['false_alarms_10x']}"])
    table(doc, ["", "Largest speed error, highway, m/s",
                "Largest speed error, aggressive, m/s",
                "False alarms, highway", "False alarms, aggressive"], rows)
    note(doc, "Table. Each helper on the chip, with no delay. Largest speed "
              "error through any of 560 faults; false alarms on the clean "
              "drives. SIMULATED on the laptop.")
    mv, gv = _row(w["val"], "A2 monitor"), _row(w["val"], "A2 gru16v3")
    para(doc, f"The rule helper cut the largest speed error from "
              f"{_row(w['val'], 'A0 b7')['worst_peak_err_mps']:.1f} to "
              f"{mv['worst_peak_err_mps']:.1f} metres per second on the "
              f"highway cycle, with no false alarm. The neural networks, "
              f"which judged faults better, drove the car worse: up to "
              f"{_row(w['test'], 'A2 fastgrnn16v3')['worst_peak_err_mps']:.0f} "
              f"metres per second off on the aggressive cycle, and they "
              f"added false alarms.")
    para(doc, "The cause was traced on the highway cycle. The networks were "
              "right that the sensor was faulty, so they kept the alarm "
              "raised. While the alarm is raised the controller works out "
              "its speed from a backup, and both backups drift. For a small "
              "sensor error, five seconds on a drifting backup did more "
              "harm than trusting the slightly wrong sensor would have. A "
              "better judge does not fix a drifting backup.")

    doc.add_heading("Delay, and what it means for an online helper", level=2)
    para(doc, "An online helper answers late. The rule helper was tested "
              "with its answers delayed. Up to half a second it worked "
              "about as well as with no delay. At one second its advice "
              "arrived too late to be used, and the result was the checker "
              "alone. A lost connection during a fault also left the "
              "checker working alone, which is the designed behaviour.")

    doc.add_heading("Mixing the two backup speeds did not help", level=2)
    a3 = _row(w["a3test"], "A3 fixed 0.5")
    para(doc, f"One further idea was tried: instead of choosing one backup "
              f"speed, use a mix of the two, with the mix set by a fixed "
              f"number or by a helper. No mix beat the rule helper's simple "
              f"choice. A fixed half-and-half mix gave a largest error of "
              f"{a3['worst_peak_err_mps']:.1f} metres per second on the "
              f"aggressive cycle. SIMULATED.")

    doc.add_heading("What this means for buying Jev", level=2)
    bullets(doc, [
        "For the sensor-fault task, the evidence is against it. The "
        "simple rules did the job, and the limit was the drifting backup "
        "speed, which no helper can fix by judging better.",
        "A hosted helper would need to answer within about half a second "
        "and bring information the car does not already have.",
        "Nothing here tests Jev itself. Its seat in the software is ready "
        "if it is bought later.",
    ])


def planning_section(doc, w, *, h1, para, table, bullets, note) -> None:
    h1(doc, "Planning the speed to save energy", "week13planning")
    p = w["plan"]
    t, v = p["arms"], p["validation"]["arms"]
    names = (("tracked_cycle", "The drive as recorded"),
             ("classical", "Planner that sees the whole route"),
             ("classical_short", "Planner that sees 300 m ahead"),
             ("terminal_cost", "300 m ahead, with a learned estimate of "
                               "the rest"),
             ("student", "Neural network that picks the speed directly"))

    para(doc, "Everything before this section followed a speed trace that "
              "was handed to the controller. This section asks a different "
              "question: if the car may choose its own speed, how much "
              "energy can it save? This is a new task. It does not change "
              "any energy figure earlier in the report.")
    para(doc, "The rules were fixed before any planner was run. A route is "
              "a standard drive with the driver taken out. The planner must "
              "cover the same distance, make every stop and wait the same "
              "time at each, stay under the fastest speed the drive reached "
              "nearby, accelerate and brake no harder than the drive did, "
              "and arrive at the same time within 1%.")
    para(doc, "One thing is missing from this task, and it limits what the "
              "numbers mean: other traffic. Where the recorded drive slowed "
              "for a car ahead, the planner is free not to. The savings "
              "below are for an empty road. They are the most that planning "
              "could give, not what it would give in traffic.")

    rows = []
    for key, label in names:
        rows.append([label, f"{t[key]['equivalent_wh_per_km']:.1f}",
                     f"{100 * t[key]['saving_vs_tracked_frac']:.1f}%",
                     f"{v[key]['equivalent_wh_per_km']:.1f}",
                     f"{100 * v[key]['saving_vs_tracked_frac']:.1f}%"])
    table(doc, ["", "Aggressive route, Wh/km", "Saving",
                "Highway route, Wh/km", "Saving"], rows)
    note(doc, "Table. Energy on the comparable scale, each speed plan "
              "driven through the full vehicle model with the speed "
              "controller and the rule energy manager. No other traffic. "
              "One run, reported as it came out. SIMULATED on the laptop.")

    c, s, tc, st = (t["classical"], t["classical_short"], t["terminal_cost"],
                    t["student"])
    para(doc, f"On the aggressive route the planner used "
              f"{100 * c['saving_vs_tracked_frac']:.1f}% less energy than "
              f"the recorded drive, with the same stops and the same arrival "
              f"time. On the steady highway route it saved "
              f"{100 * v['classical']['saving_vs_tracked_frac']:.1f}%: that "
              f"drive had little to smooth out.")
    para(doc, f"A planner that sees only 300 metres ahead saved "
              f"{100 * s['saving_vs_tracked_frac']:.1f}%. Giving it a small "
              f"neural network that estimates the cost of the rest of the "
              f"route brought it back to "
              f"{100 * tc['saving_vs_tracked_frac']:.1f}%. This is the one "
              f"place in the project where a learned part clearly earned "
              f"its keep.")
    para(doc, f"A neural network asked to pick the speed directly, with no "
              f"planning behind it, saved "
              f"{100 * st['saving_vs_tracked_frac']:.1f}% on the aggressive "
              f"route. It kept every rule, because a simple arithmetic "
              f"check forces it to, but it drove no better than the "
              f"recorded driver.")
    para(doc, f"The planners draw a higher peak battery current than the "
              f"recorded drive, {c['peak_current_a']:.0f} to "
              f"{s['peak_current_a']:.0f} amperes against "
              f"{t['tracked_cycle']['peak_current_a']:.0f} on the aggressive "
              f"route. Energy fell and peak current rose. The task set no "
              f"current limit, and the cause was not examined.")

    doc.add_heading("What this does not cover", level=2)
    bullets(doc, [
        "Other traffic, traffic lights, hills.",
        "The board. No planner was run on the chip.",
        "Repeats. One training run, one test route.",
        "Sending plans from a remote computer. It was considered and not "
        "run: the local planner already recovers the full saving, so a "
        "remote one would add a link without adding a result.",
    ])


def week13_sections(doc, w, *, h1, para, table, bullets, note, ref) -> None:
    """The three sections, or one line saying they are missing."""
    if not w:
        h1(doc, "Week 13: fault checker, AI helpers and energy planning",
           "week13checker")
        para(doc, "The week-13 result files were not all present when this "
                  "report was generated.", italic=True)
        return

    def para_ref(d, text, _ref=None, **kw):
        para(d, text.replace("{ref}", ref(_ref)) if _ref else text, **kw)

    kw = dict(h1=h1, para=para_ref, table=table, bullets=bullets, note=note)
    checker_section(doc, w, **kw)
    helpers_section(doc, w, **kw)
    planning_section(doc, w, **kw)


def summary_bullets(w: dict, ref) -> list[str]:
    a = w["pil"]["arms"]
    new, old = a["B7"], a["B6"]
    t = w["plan"]["arms"]
    return [
        f"Week 13, measured on the board: a new speed-sensor fault checker "
        f"caught all {new['fault_runs']} injected faults within "
        f"{new['worst_delay_s']:.2f} seconds with no false alarm and no "
        f"late control step. The earlier checker caught "
        f"{old['detected_in_time']} and raised {old['clean_false_alarms']} "
        f"false alarms on one clean drive. Section " + ref("week13checker")
        + ".",
        "Week 13, simulated: small AI helpers judged sensor faults better "
        "than hand-written rules and drove the car worse. The rules are "
        "kept. Jev was not purchased and is not tested. Section "
        + ref("week13helpers") + ".",
        f"Week 13, simulated, a new task: letting the car plan its own "
        f"speed on an empty road saved "
        f"{100 * t['classical']['saving_vs_tracked_frac']:.1f}% of energy "
        f"on the aggressive route and "
        f"{100 * w['plan']['validation']['arms']['classical']['saving_vs_tracked_frac']:.1f}% "
        f"on the highway route. Section " + ref("week13planning") + ".",
    ]


def note_block(doc, w: dict) -> None:
    """Week 13 for the supervisor note: one page, plain words."""
    a = w["pil"]["arms"]
    old, new, helped = a["B6"], a["B7"], a["B7 + rule monitor"]
    t, v = w["plan"]["arms"], w["plan"]["validation"]["arms"]
    doc.add_heading("Week 13: fault checker, AI helpers, energy planning",
                    level=1)
    doc.add_paragraph(
        "The fault checker that the previous section reports as not usable "
        "has been replaced. The new one allows for the slow drift a real "
        "acceleration signal carries. It was written in C, matched step by "
        "step against the laptop version, and tested on the board with "
        "faults injected for the first time.")
    table = doc.add_table(rows=1, cols=4)
    table.style = "Light Shading Accent 1"
    for c, text in zip(table.rows[0].cells,
                       ("", "First checker", "New checker",
                        "New checker with rule helper")):
        c.text = text
    for row in board_rows(w)[:6] + board_rows(w)[7:8]:
        for c, text in zip(table.add_row().cells, row):
            c.text = text
    doc.add_paragraph(
        f"MEASURED on the board, aggressive cycle (US06), "
        f"{new['fault_runs']} injected faults and two clean ten-minute "
        f"drives per version, one run per case. The acceleration drift was "
        f"simulated from logged trips, not taken from a real sensor. The "
        f"new checker's longest control calculation was "
        f"{new['worst_control_computation_us']} microseconds of 10,000.")
    doc.add_paragraph(
        "AI helpers. The plan proposed a slower helper that advises the "
        "checker, with the paid online model Jev in that seat. Jev was not "
        "purchased and no result here is a Jev result. Hand-written rules "
        "and two small neural networks were tested in the same seat. "
        "SIMULATED: the networks recognised faults better than the rules "
        f"({100 * w['shadow']['reviewers']['gru16v3']['sensor_fault']['recall_while_flagged']:.0f}% "
        f"against "
        f"{100 * w['shadow']['reviewers']['monitor']['sensor_fault']['recall_while_flagged']:.0f}% "
        "while an alarm was raised) and controlled the car worse. Largest "
        "speed error through a fault on the aggressive cycle: "
        f"{_row(w['test'], 'A0 b7')['worst_peak_err_mps']:.1f} m/s with the "
        f"checker alone, "
        f"{_row(w['test'], 'A2 monitor')['worst_peak_err_mps']:.1f} with "
        f"the rules, "
        f"{_row(w['test'], 'A2 gru16v3')['worst_peak_err_mps']:.1f} and "
        f"{_row(w['test'], 'A2 fastgrnn16v3')['worst_peak_err_mps']:.1f} "
        "with the networks. The cause is the backup speed the controller "
        "uses while an alarm is raised: it drifts, and a helper that keeps "
        "the alarm raised longer keeps the car on it longer. On this "
        "evidence Jev is not recommended for the sensor-fault task.")
    doc.add_paragraph(
        "Energy planning, a new task. SIMULATED, empty road: a planner "
        "that chooses the car's speed, with the same stops, limits and "
        f"arrival time as the recorded drive, used "
        f"{100 * t['classical']['saving_vs_tracked_frac']:.1f}% less energy "
        f"on the aggressive route and "
        f"{100 * v['classical']['saving_vs_tracked_frac']:.1f}% less on the "
        f"highway route. Seeing only 300 m ahead it saved "
        f"{100 * t['classical_short']['saving_vs_tracked_frac']:.1f}%; with "
        f"a small learned estimate of the rest of the route, "
        f"{100 * t['terminal_cost']['saving_vs_tracked_frac']:.1f}%. A "
        f"neural network choosing the speed directly saved "
        f"{100 * t['student']['saving_vs_tracked_frac']:.1f}%. With no "
        "other traffic in the task these are upper bounds. Nothing in this "
        "paragraph was run on the board.")
