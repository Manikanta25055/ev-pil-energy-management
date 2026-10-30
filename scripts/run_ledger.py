"""Review R2/R9 (2026-10-30): one ledger of every energy-comparison run on the board.

Reads the campaign records as committed and lists each run with its status:

  accepted            in the analysed set
  excluded_delay      a nonzero communication-delay setting, dropped by the
                      tracking rule (RMSE of 1 m/s or more) fixed on 2026-09-21
                      after those runs were seen
  set_aside_frames    over 16 dropped frames, moved to a *-disturbed.json file
                      and taken again under the rule recorded on 2026-10-07
  accepted_over_limit a retake that again exceeded 16 frames and stands, as the
                      rule allows one retake

Earlier-campaign runs (faulty plant) predate the 16-frame rule, so none of them
was set aside; their energy result is withdrawn. Nothing is recomputed here
beyond counting. MEASURED records, host bookkeeping.

    python3 scripts/run_ledger.py
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

DOCS = Path("docs")
OUT_CSV = DOCS / "2026-10-30-run-ledger.csv"
OUT_JSON = DOCS / "2026-10-30-run-ledger.json"
LIMIT = 16

# campaign id, plant, accepted file(s), disturbed file(s), apply frame rule
CAMPAIGNS = [
    ("earlier", "faulty (withdrawn)", ["week10-pil-campaign.json"], [], False),
    ("earlier-repeat", "faulty (withdrawn)", ["week10-pil-campaign-repeat.json"], [], False),
    ("corrected-s0", "corrected", ["week11-pil-corrected.json"],
     ["week11-pil-corrected-rule-disturbed.json"], True),
    ("b2-s100", "corrected",
     ["2026-10-14-pil-repeats-rule-s100.json", "2026-10-14-pil-repeats-actor-s100.json"],
     ["2026-10-14-pil-repeats-rule-s100-disturbed.json",
      "2026-10-14-pil-repeats-actor-s100-disturbed.json"], True),
    ("b2-s200", "corrected",
     ["2026-10-14-pil-repeats-rule-s200.json", "2026-10-14-pil-repeats-actor-s200.json"],
     ["2026-10-14-pil-repeats-rule-s200-disturbed.json",
      "2026-10-14-pil-repeats-actor-s200-disturbed.json"], True),
    ("b1-estimators", "corrected",
     [f"2026-10-14-lowpass-pil-{a}-s{s}.json" for a in ("b0", "lowpass", "kalman")
      for s in (100, 200)],
     ["2026-10-14-lowpass-pil-b0-s200-disturbed.json"], True),
]


def runs(name):
    return json.loads((DOCS / name).read_text())["runs"]


def arm_of(name, run):
    if "lowpass-pil-" in name:
        return name.split("lowpass-pil-")[1].split("-s")[0]
    return run["controller"]


def row(campaign, plant, name, run, status):
    return {
        "campaign": campaign, "plant": plant, "source": f"docs/{name}",
        "cell": f"{run['scenario']}/{run['level']}", "arm": arm_of(name, run),
        "seed": run["seed"], "comm_delay_s": run.get("comm_delay_s", 0.0),
        "dropped_frames": run.get("dropped_frames"),
        "ctrl_late": run.get("ctrl_late"),
        "tracking_rmse_mps": round(run["tracking_rmse_mps"], 4),
        "equivalent_wh_per_km": round(run["equivalent_wh_per_km"], 3),
        "status": status,
    }


def main() -> int:
    rows = []
    for campaign, plant, acc, dist, frame_rule in CAMPAIGNS:
        for name in acc:
            for r in runs(name):
                if r.get("comm_delay_s", 0.0) > 0:
                    status = "excluded_delay"
                elif frame_rule and r.get("dropped_frames", 0) > LIMIT:
                    status = "accepted_over_limit"
                else:
                    status = "accepted"
                rows.append(row(campaign, plant, name, r, status))
        for name in dist:
            for r in runs(name):
                rows.append(row(campaign, plant, name, r, "set_aside_frames"))

    summary = {}
    for campaign, *_ in CAMPAIGNS:
        c = Counter(r["status"] for r in rows if r["campaign"] == campaign)
        summary[campaign] = {"attempted": sum(c.values()), **dict(sorted(c.items()))}

    with OUT_CSV.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    OUT_JSON.write_text(json.dumps({
        "provenance": "bookkeeping over committed MEASURED records; review items R2 and R9",
        "frame_limit": LIMIT,
        "rules": {
            "excluded_delay": "tracking RMSE >= 1 m/s, fixed 2026-09-21 after the delay runs were seen",
            "set_aside_frames": "dropped frames > 16, recorded 2026-10-07; one retake, which stands",
            "earlier campaigns": "predate the frame rule; energy result withdrawn (faulty plant)",
        },
        "summary": summary,
    }, indent=1) + "\n")
    for k, v in summary.items():
        print(f"{k:15} {v}")
    print(f"wrote {OUT_CSV} and {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
