"""Week 14 in the status report and the supervisor note, in plain language.

Three subjects: the board fault runs repeated with other draws of noise, a
backup speed that does not drift while an alarm is raised, and speed
planning with traffic. Every number is read from the week-14 result files.

The plain names of scripts/report_week13.py are kept: the new checker is B7,
the rule helper is the rule monitor, the fused backup speed is B8.
"""

from __future__ import annotations

import json
from pathlib import Path

DOCS = Path("docs")
FILES = {"rep": "week14-b7-pil-repeats.json", "tune": "week14-b8-tuning.json",
         "b8val": "week14-b8-val.json", "b8test": "week14-b8-test.json",
         "cor": "week14-corridor-planner.json"}
B8_ROWS = (("A0 b7", "New checker alone"),
           ("A2 monitor", "New checker with the rule helper"),
           ("B8 fused backup", "With the fused backup speed"),
           ("B8 + monitor", "Fused backup speed and rule helper"))


def load_week14(docs: Path = DOCS) -> dict | None:
    out = {}
    for key, name in FILES.items():
        path = docs / name
        if not path.exists():
            return None
        out[key] = json.loads(path.read_text())
    return out


def repeat_rows(w: dict) -> list[list[str]]:
    a = w["rep"]["arms"]
    cols = [a["B7"]["pooled"], a["B7 + rule monitor"]["pooled"]]

    def line(label, fmt):
        return [label] + [fmt(c) for c in cols]

    return [
        line("Faults caught within half a second",
             lambda c: f"{c['detected_in_time']} of {c['fault_runs']}"),
        line("Slowest catch, seconds", lambda c: f"{c['worst_delay_s']:.2f}"),
        line("False alarms in one clean hour",
             lambda c: str(c["clean_false_alarms"])),
        line("Alarm dropped while the fault was still there",
             lambda c: str(c["released_early"])),
        line("Still raising the alarm when the run ended",
             lambda c: str(c["still_flagged_in_last_second"])),
        line("Largest speed error during a fault, m/s",
             lambda c: f"{c['worst_peak_err_mps']:.2f}"),
        line("Typical speed error during a fault, m/s",
             lambda c: f"{c['median_peak_err_mps']:.2f}"),
        line("Control steps finished late",
             lambda c: str(c["late_control_steps"])),
    ]


def _b8_table(w: dict, key: str) -> list[list[str]]:
    rows = []
    for name, label in B8_ROWS:
        s = w[key]["rows"][name]["summary"]
        rows.append([label, f"{s['worst_peak_err_mps']:.2f}",
                     f"{s['median_peak_err_mps_worst_case']:.2f}",
                     str(s["lingering_flags"]),
                     str(s["false_alarms_floor"] + s["false_alarms_10x"])])
    return rows


def _b8_conditions(w: dict):
    """B8's largest error on the aggressive cycle, with the car as the
    model expects and with the car heavier."""
    by = w["b8test"]["rows"]["B8 fused backup"]["verdict"]["by_accel"]
    nominal = [g["worst_peak_err_mps"] for k, g in by.items()
               if "x1.1" not in k]
    heavy = [g["worst_peak_err_mps"] for k, g in by.items() if "x1.1" in k]
    return min(nominal), max(nominal), max(heavy), len(nominal), len(by)


def week14_section(doc, w, *, h1, para, table, bullets, note, ref) -> None:
    h1(doc, "Week 14: board repeats, a steadier backup speed, and traffic",
       "week14")
    if not w:
        para(doc, "The week-14 result files were not all present when this "
                  "report was generated.", italic=True)
        return
    a = w["rep"]["arms"]
    new, helped = a["B7"]["pooled"], a["B7 + rule monitor"]["pooled"]
    first = a["B7 + rule monitor"]["per_draw"]["first"]
    para(doc, "Week 14 followed up three things that sections "
              + ref("week13checker") + " to " + ref("week13planning")
              + " left open: each board case had been run only once; the "
              "backup speed used while an alarm is raised drifts; and the "
              "speed planner had an empty road.")

    doc.add_heading("The board runs, repeated", level=2)
    para(doc, f"The same 42 cases per version were run twice more on the "
              f"board, each time with a different draw of sensor noise and "
              f"of acceleration drift. With the first run that makes "
              f"{new['fault_runs']} injected faults and "
              f"{new['clean_hours']:.0f} hour of clean driving for each "
              f"version.")
    table(doc, ["", "New checker", "New checker with rule helper"],
          repeat_rows(w))
    note(doc, "Table. Injected speed-sensor faults on the board, three "
              "draws of noise pooled. Cases that lost more than 16 frames "
              "were set aside and run again. MEASURED on the board.")
    para(doc, f"The new checker's result holds. All {new['fault_runs']} "
              f"faults were caught, the slowest in "
              f"{new['worst_delay_s']:.2f} seconds, with no false alarm "
              f"and no late control step.")
    para(doc, f"The rule helper's advantage on the board does not hold. In "
              f"the first run its largest speed error was "
              f"{first['worst_peak_err_mps']:.2f} metres per second, a "
              f"little under the checker alone. Over three draws it is "
              f"{helped['worst_peak_err_mps']:.2f} against "
              f"{new['worst_peak_err_mps']:.2f}, and it left "
              f"{helped['still_flagged_in_last_second']} alarms raised at "
              f"the end of a run where the checker alone left none. It does "
              f"drop the alarm early less often "
              f"({helped['released_early']} against "
              f"{new['released_early']}). The rule helper helps in "
              f"simulation. On the chip it has not been shown to.")

    doc.add_heading("A backup speed that does not drift", level=2)
    t = w["tune"]
    lo, hi, heavy, n_nom, n_all = _b8_conditions(w)
    v = {k: w["b8val"]["rows"][k]["summary"] for k, _ in B8_ROWS}
    para(doc, "Section " + ref("week13helpers") + " found what limits every "
              "helper: while the sensor is distrusted the controller works "
              "from a backup speed, and both backups drift. One comes from "
              "the acceleration reading and drifts with that reading's "
              "error. The other is the vehicle model's prediction and "
              "drifts with whatever the model has wrong.")
    para(doc, "The fused backup speed is one calculation that keeps track "
              "of three things: the speed, the model's error and the "
              "acceleration reading's error. While the sensor is trusted "
              "it learns both errors. While the sensor is distrusted it "
              "carries on with what it learned. The checker itself is "
              "unchanged. Its three settings were chosen on the urban "
              "training cycle only.")
    table(doc, ["Highway cycle", "Largest speed error, m/s",
                "Typical speed error, m/s", "Alarms stuck",
                "Clean false alarms"], _b8_table(w, "b8val"))
    table(doc, ["Aggressive cycle", "Largest speed error, m/s",
                "Typical speed error, m/s", "Alarms stuck",
                "Clean false alarms"], _b8_table(w, "b8test"))
    note(doc, "Tables. Largest speed error through any of 560 faults, and "
              "the typical error in the hardest condition. SIMULATED on "
              "the laptop.")
    para(doc, f"On the highway cycle the fused backup speed is the best "
              f"result so far: largest error "
              f"{v['B8 fused backup']['worst_peak_err_mps']:.2f} metres per "
              f"second against {v['A0 b7']['worst_peak_err_mps']:.2f} for "
              f"the checker alone and "
              f"{v['A2 monitor']['worst_peak_err_mps']:.2f} with the rule "
              f"helper, and no alarm left stuck.")
    para(doc, f"On the aggressive cycle it is the best in {n_nom} of the "
              f"{n_all} conditions, with a largest error of {lo:.2f} to "
              f"{hi:.2f}. It is the worst in the remaining one: a car 10% "
              f"heavier than the model, {heavy:.2f}. That is where the "
              f"model is most wrong and changes fastest. The settings were "
              f"chosen on gentle urban driving, which is the likely cause; "
              f"it was not tested.")

    doc.add_heading("Speed planning with traffic", level=2)
    us, hw = (w["cor"]["routes"]["us06"]["rows"],
              w["cor"]["routes"]["hwfet"]["rows"])
    para(doc, "Section " + ref("week13planning") + " let the planner drive "
              "an empty road. A real car is in traffic. Here the planner "
              "must stay within a set distance of the recorded drive at "
              "every second, ahead or behind. Distance covered and arrival "
              "time are the recorded drive's exactly.")
    rows = [["The recorded drive", f"{us['recorded']['equivalent_wh_per_km']:.1f}",
             "", f"{hw['recorded']['equivalent_wh_per_km']:.1f}", ""]]
    for k in us:
        if k == "recorded":
            continue
        rows.append([f"Within {k}", f"{us[k]['equivalent_wh_per_km']:.1f}",
                     f"{100 * us[k]['saving_vs_recorded_frac']:.1f}%",
                     f"{hw[k]['equivalent_wh_per_km']:.1f}",
                     f"{100 * hw[k]['saving_vs_recorded_frac']:.1f}%"])
    table(doc, ["The car stays", "Aggressive route, Wh/km", "Saving",
                "Highway route, Wh/km", "Saving"], rows)
    note(doc, "Table. Energy on the comparable scale, each plan driven "
              "through the full vehicle model. One run per distance. "
              "SIMULATED on the laptop.")
    para(doc, f"About half of the empty-road saving survives a tight "
              f"limit. Held within 25 metres of the recorded drive the "
              f"planner still saves "
              f"{100 * us['25 m']['saving_vs_recorded_frac']:.1f}% on the "
              f"aggressive route, and within 100 metres "
              f"{100 * us['100 m']['saving_vs_recorded_frac']:.1f}%. On the "
              f"steady highway route there is little to save at any "
              f"distance.")

    doc.add_heading("What this does not cover", level=2)
    bullets(doc, [
        "A real acceleration sensor. The drift on the board is still "
        "simulated.",
        "The fused backup speed on the board. It exists on the laptop "
        "only.",
        "A traffic model. The traffic here is one recorded drive.",
        "Jev. It was not purchased and is not tested.",
    ])


def summary_bullets(w: dict, ref) -> list[str]:
    a = w["rep"]["arms"]
    new = a["B7"]["pooled"]
    v = w["b8val"]["rows"]
    us = w["cor"]["routes"]["us06"]["rows"]
    return [
        f"Week 14, measured on the board: repeated with two more draws of "
        f"noise, the new fault checker caught {new['detected_in_time']} of "
        f"{new['fault_runs']} injected faults with no false alarm in "
        f"{new['clean_hours']:.0f} clean hour. The rule helper's small "
        f"advantage from the first run did not repeat. Section "
        + ref("week14") + ".",
        f"Week 14, simulated: a backup speed that does not drift cut the "
        f"largest speed error during a fault from "
        f"{v['A0 b7']['summary']['worst_peak_err_mps']:.2f} to "
        f"{v['B8 fused backup']['summary']['worst_peak_err_mps']:.2f} "
        f"metres per second on the highway cycle. It fails for a car "
        f"heavier than its model in aggressive driving.",
        f"Week 14, simulated: with traffic, held within 25 metres of the "
        f"recorded drive, speed planning still saves "
        f"{100 * us['25 m']['saving_vs_recorded_frac']:.1f}% on the "
        f"aggressive route.",
    ]


def note_block(doc, w: dict) -> None:
    a = w["rep"]["arms"]
    new, helped = a["B7"]["pooled"], a["B7 + rule monitor"]["pooled"]
    v, t = w["b8val"]["rows"], w["b8test"]["rows"]
    us, hw = (w["cor"]["routes"]["us06"]["rows"],
              w["cor"]["routes"]["hwfet"]["rows"])
    lo, hi, heavy, n_nom, n_all = _b8_conditions(w)
    doc.add_heading("Week 14: repeats, a steadier backup speed, traffic",
                    level=1)
    doc.add_paragraph(
        "Board repeats. MEASURED on the board: the week-13 fault cases "
        "were run twice more with other draws of noise. Over three draws "
        f"the new checker caught {new['detected_in_time']} of "
        f"{new['fault_runs']} injected faults, the slowest in "
        f"{new['worst_delay_s']:.2f} s, with no false alarm in "
        f"{new['clean_hours']:.0f} clean hour and no late control step. "
        "This corrects the week-13 table above on one point: the rule "
        "helper's lower speed error in the first run did not repeat. Over "
        f"three draws its largest speed error is "
        f"{helped['worst_peak_err_mps']:.2f} m/s against "
        f"{new['worst_peak_err_mps']:.2f} for the checker alone, and it "
        f"left {helped['still_flagged_in_last_second']} alarms raised at "
        "the end of a run. The rule helper is not recommended for the "
        "board on this evidence.")
    doc.add_paragraph(
        "Backup speed. SIMULATED: one calculation that tracks the speed, "
        "the model's error and the acceleration reading's error replaces "
        "the two drifting backups. On the highway cycle the largest speed "
        f"error during a fault falls from "
        f"{v['A0 b7']['summary']['worst_peak_err_mps']:.2f} to "
        f"{v['B8 fused backup']['summary']['worst_peak_err_mps']:.2f} m/s. "
        f"On the aggressive cycle it is {lo:.2f} to {hi:.2f} m/s in "
        f"{n_nom} of {n_all} conditions and {heavy:.2f} in the remaining "
        "one, a car 10% heavier than the model. It has not been written "
        "for the chip.")
    doc.add_paragraph(
        "Planning with traffic. SIMULATED: the planner held within 25 m "
        "of the recorded drive saves "
        f"{100 * us['25 m']['saving_vs_recorded_frac']:.1f}% on the "
        f"aggressive route and "
        f"{100 * hw['25 m']['saving_vs_recorded_frac']:.1f}% on the "
        f"highway route; within 100 m, "
        f"{100 * us['100 m']['saving_vs_recorded_frac']:.1f}% and "
        f"{100 * hw['100 m']['saving_vs_recorded_frac']:.1f}%. The traffic "
        "is one recorded drive, not a traffic model.")
