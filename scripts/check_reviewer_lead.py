"""Is a learned reviewer reading the fault, or the clock?

Every registered fault run starts 30 s before its fault, so in the recorded
blocks the fault is always on from block 300 to block 350. A recurrent model
could score well by counting. This re-records the validation fault runs with
the fault 12 s and 47 s into the run instead and scores the reviewers again.
A model that reads the fault scores the same; a model that counts does not.

    PYTHONPATH="src:." python3 scripts/check_reviewer_lead.py
"""

from __future__ import annotations

import argparse
import json
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from evpil.control import sensor_eval as se
from scripts import build_reviewer_data as brd
from scripts.score_reviewers_shadow import probs_for, score
from scripts.sensor_arms import reviewer


def _set_lead(lead_s: float) -> None:
    se.LEAD_S = lead_s


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reviewers", default="monitor,gru16v3,fastgrnn16v3,gru64v3")
    ap.add_argument("--out-json", default="docs/week13-reviewer-lead-check.json")
    args = ap.parse_args()
    cases = se.fault_cases("val")[::3]
    doc = {"provenance": "SIMULATED on the laptop; validation fault runs, "
                         "every third, re-recorded with a different lead",
           "runs": len(cases), "leads": {}}
    for lead in (30.0, 12.0, 47.0):
        with Pool(4, initializer=_set_lead, initargs=(lead,)) as pool:
            rows = pool.map(brd._one, cases, chunksize=8)
        d = {"x": np.concatenate([x for x, _ in rows]),
             "y": np.concatenate([y for _, y in rows]),
             "lens": np.array([len(x) for x, _ in rows]),
             "fault": np.array([c.fault for c in cases])}
        doc["leads"][str(lead)] = {}
        for name in args.reviewers.split(","):
            s = score(probs_for(reviewer(name), d), d)["sensor_fault"]
            doc["leads"][str(lead)][name] = s
            print(f"lead {lead:4.0f} s  {name:13s} recall {s['recall']:.3f} "
                  f"(flagged {s['recall_while_flagged']:.3f}, not flagged "
                  f"{s['recall_while_not_flagged']:.3f})  false positives "
                  f"{s['false_positive_rate']:.4f}", flush=True)
    Path(args.out_json).write_text(json.dumps(doc, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
