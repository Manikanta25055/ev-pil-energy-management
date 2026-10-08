"""The shadow rung: every reviewer's diagnoses against the truth, with no
advice applied.

The recorded validation blocks (`scripts/build_reviewer_data.py`) are what a
reviewer would have been shown with B7 alone in the loop. Each reviewer is
run over them from a fresh state per run and scored on the same blocks: the
rule monitor, and each trained model that is on disk.

This says how well a reviewer diagnoses. It does not say that acting on the
diagnosis helps: once advice is applied the drive is a different drive. That
is `scripts/run_arch_study.py`.

    PYTHONPATH="src:." python3 scripts/score_reviewers_shadow.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from evpil.control.supervisor import DIAGNOSES, Snapshot
from scripts.sensor_arms import reviewer


def probs_for(rev, d) -> np.ndarray:
    out = np.zeros((len(d["y"]), len(DIAGNOSES)))
    at = 0
    for n in d["lens"]:
        rev.reset()
        for i in range(at, at + int(n)):
            out[i] = rev.review(Snapshot(i - at, 0.0, 0, tuple(d["x"][i])))
        at += int(n)
    return out


def score(p: np.ndarray, d) -> dict:
    y = d["y"]
    run = np.repeat(np.arange(len(d["lens"])), d["lens"])
    fault_of = d["fault"][run]
    pred = p.argmax(axis=1)
    p_fault, is_fault = p[:, 1] + p[:, 3], y % 2 == 1
    p_acc, is_acc = p[:, 2] + p[:, 3], y >= 2
    flagged = d["x"][:, 8] > 0.5
    out = {
        "accuracy": float((pred == y).mean()),
        "brier": float(((p - np.eye(4)[y]) ** 2).sum(axis=1).mean()),
        "sensor_fault": {
            "brier": float(((p_fault - is_fault) ** 2).mean()),
            "recall": float((p_fault[is_fault] > 0.5).mean()),
            "false_positive_rate": float((p_fault[~is_fault] > 0.5).mean()),
            "recall_while_flagged": float(
                (p_fault[is_fault & flagged] > 0.5).mean()),
            "recall_while_not_flagged": float(
                (p_fault[is_fault & ~flagged] > 0.5).mean()),
            "false_positive_rate_while_flagged": float(
                (p_fault[~is_fault & flagged] > 0.5).mean()),
            "recall_by_fault": {
                str(f): float((p_fault[is_fault & (fault_of == f)] > 0.5).mean())
                for f in np.unique(fault_of) if f},
        },
        "accel_degraded": {
            "brier": float(((p_acc - is_acc) ** 2).mean()),
            "recall": float((p_acc[is_acc] > 0.5).mean()),
            "false_positive_rate": float((p_acc[~is_acc] > 0.5).mean()),
        },
    }
    conf = p.max(axis=1)
    rel = []
    for lo in np.arange(0.0, 1.0, 0.1):
        m = (conf > lo) & (conf <= lo + 0.1)
        if m.any():
            rel.append({"bin": f"{lo:.1f}-{lo + 0.1:.1f}", "n": int(m.sum()),
                        "confidence": float(conf[m].mean()),
                        "accuracy": float((pred[m] == y[m]).mean())})
    out["reliability"] = rel
    out["ece"] = float(sum(r["n"] * abs(r["accuracy"] - r["confidence"])
                           for r in rel) / len(y))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/reviewer/val.npz")
    ap.add_argument("--reviewers",
                    default="healthy,monitor,gru16,fastgrnn16,gru64")
    ap.add_argument("--out-json", default="docs/week13-arch-shadow.json")
    args = ap.parse_args()
    d = dict(np.load(args.data))
    doc = {"provenance": "SIMULATED on the laptop; validation split; advice "
                         "scored, never applied",
           "blocks": int(len(d["y"])), "runs": int(len(d["lens"])),
           "label_counts": dict(zip(DIAGNOSES, np.bincount(
               d["y"], minlength=4).tolist())),
           "data_config": str(d["config"]), "reviewers": {}}
    for name in args.reviewers.split(","):
        if name not in ("healthy", "monitor") and not Path(
                f"data/reviewer/{name}.npz").exists():
            print(f"{name}: not trained, skipped")
            continue
        rev = reviewer(name)
        s = score(probs_for(rev, d), d)
        if hasattr(rev, "n_params"):
            s["parameters"], s["weight_bytes"] = rev.n_params(), rev.weight_bytes()
        doc["reviewers"][name] = s
        f = s["sensor_fault"]
        print(f"{name:11s} accuracy {s['accuracy']:.3f}  Brier {s['brier']:.3f}"
              f"  ECE {s['ece']:.3f} | sensor fault: recall {f['recall']:.2f} "
              f"(flagged {f['recall_while_flagged']:.2f}, not flagged "
              f"{f['recall_while_not_flagged']:.2f}), false positives "
              f"{f['false_positive_rate']:.4f} | accel: recall "
              f"{s['accel_degraded']['recall']:.2f}, false positives "
              f"{s['accel_degraded']['false_positive_rate']:.3f}", flush=True)
    Path(args.out_json).write_text(json.dumps(doc, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
