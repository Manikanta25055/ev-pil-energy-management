"""Generate a supervisor correction note from saved measurements."""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path

from docx import Document
from docx.shared import Inches, Pt, RGBColor

from scripts.corrected_campaign import load_corrected_a4, validate_campaign


def build_note(sac, campaign=None, a4=None, robustness=None):
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)
    style.paragraph_format.space_after = Pt(8)
    for name in ("Title", "Heading 1", "Heading 2"):
        doc.styles[name].font.color.rgb = RGBColor(0, 0, 0)
    for section in doc.sections:
        section.top_margin = section.bottom_margin = Inches(0.75)
    doc.add_paragraph("Correction to the EV energy management results", "Title")
    doc.add_paragraph(date.today().strftime("%d %B %Y").lstrip("0"))
    doc.add_paragraph(
        "The earlier claim of an 8.28% mean energy saving is withdrawn. "
        "The host vehicle model capped the energy billed at the commanded "
        "power ceiling while delivering unrestricted torque. The corrected "
        "model reduces torque when the power ceiling binds. Regression tests "
        "cover this correction.")
    doc.add_heading("Retraining on the corrected model", level=1)
    table = doc.add_table(rows=1, cols=3)
    table.style = "Light Shading Accent 1"
    for c, text in zip(table.rows[0].cells,
                       ("Controller", "Validation energy Wh/km", "Against rules")):
        c.text = text
    rows = [("Rule manager", f"{sac['baseline']['equivalent_wh_per_km']:.2f}", "")]
    for arm in ("without-forecast", "with-forecast"):
        s = sac["summary"][arm]
        rows.append((arm.replace("-", " "), f"{s['mean']:.2f} ± {s['std']:.2f}",
                     f"{s['gap_to_rule_pct_mean']:+.2f}%"))
    for row in rows:
        for c, text in zip(table.add_row().cells, row):
            c.text = text
    doc.add_paragraph(
        f"SIMULATED on {sac['cycle'].upper()}, {sac['seeds']} seeds per "
        "learned arm; spread is the seed standard deviation. Shed cabin heat "
        "is charged back. The no-forecast policy was selected on validation "
        "and exported. The paired forecast interval "
        + ("includes zero." if sac["a3"]["null"] else "excludes zero."))
    doc.add_heading("Board measurements", level=1)
    if campaign is None:
        doc.add_paragraph(
            "The corrected board campaign and link-outage sweep are pending. "
            "The simulation results above are not board measurements. This "
            "note will be regenerated when the saved measurements are complete.")
    else:
        summary = validate_campaign(campaign)
        doc.add_paragraph(
            f"MEASURED: {summary['runs']} runs, {summary['steps']:,} control "
            f"steps, {summary['ctrl_late']} late steps. The learned controller "
            f"uses less energy in {summary['actor_less']} of "
            f"{summary['valid_settings']} valid settings, more in "
            f"{summary['actor_more']}, with {summary['ties']} ties. The mean "
            f"paired difference is {summary['mean_gap_pct']:+.3f}%. Each cell "
            "has one run per controller, so these settings are not repeats.")
        doc.add_paragraph(
            f"{summary['excluded_settings']} settings are excluded from energy "
            "aggregates because tracking RMSE reaches 1 m/s; their rows remain "
            "visible. The serialized delay axis measures host throughput, "
            "not independent link latency.")
        if a4 is None:
            doc.add_paragraph("The corrected link-outage sweep remains pending.")
        else:
            late = sum(d["delta"].get("ctrl_late", 0)
                       for pair in a4.values() for d in pair)
            failed = sum(d.get("verdict") is not True
                         for pair in a4.values() for d in pair)
            doc.add_paragraph(
                f"Corrected A4: {len(a4)} outage lengths from 0.2 to 10 s, "
                f"eight paired onsets each, {late} late steps and {failed} "
                "files with counter checks not passed. The report presents "
                "the new sweep separately from historical measurements.")
    doc.add_heading("Robustness work and remaining decision", level=1)
    text = ("The proposed speed-loop decision transformer was dropped. The "
            "classical filter and sensor-fault detector are merged into the "
            "code base and switched off by default. ")
    if robustness:
        v = robustness["verdict"]
        text += (f"SIMULATED B6: {v['named faults run']} named faults, "
                 f"{v['named faults missed']} missed, worst delay "
                 f"{v['worst delay, s']:.2f} s; "
                 f"{v['false alarms in them']} false alarms in "
                 f"{v['clean hours at the noise floor']:.2f} h at the noise floor. ")
    text += ("Acceleration is idealised; sensor bias and slope gravity remain "
             "unchecked. The detector has lingering flags and weak small-offset "
             "recovery. Only the earlier one-state Kalman filter has a C port. "
             "B5 and B6 need firmware implementation and parity checks before "
             "board testing. No board result is claimed. Measuring this arm "
             "on the board remains a separate decision.")
    doc.add_paragraph(text)
    doc.add_paragraph("Draft for review; this script does not send the note.")
    return doc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="reports/supervisor-correction-note.docx")
    ap.add_argument("--robustness-docs", type=Path)
    args = ap.parse_args()
    docs = Path("docs")
    sac = json.loads((docs / "week11-sac-corrected.json").read_text())
    campaign_path = docs / "week11-pil-corrected.json"
    campaign = json.loads(campaign_path.read_text()) if campaign_path.exists() else None
    robustness = None
    if args.robustness_docs:
        robustness = json.loads((args.robustness_docs / "week11-fault-arms-b6.json").read_text())
    doc = build_note(sac, campaign, load_corrected_a4(docs), robustness)
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(path)
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
