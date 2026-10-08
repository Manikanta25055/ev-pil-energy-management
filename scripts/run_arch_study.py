"""Every architecture, with every reviewer that exists, on the same cases.

`docs/2026-10-07-model-advancement-research.md`, section 12, names the
architectures. They were written with a hosted model (Jev) in the reviewer's
seat. Here the seat is filled in turn by the rule monitor, the tiny GRU and
the FastGRNN cell, so that each architecture has a result whatever sits in
it, and a hosted model can be added later as one more row.

  A0   B7 alone: no reviewer
  A2   the reviewer on the chip, no delay
  A1   post-action review behind a link: 70, 150, 500, 1000 ms, 20% jitter
  A1e  A1 at 150 ms, asked only when something is up (event-triggered)
  A1c  A1 at 150 ms, an answer reused for 5 s while the flag has not changed
  A1x  A1 at 150 ms with a fifth of the answers lost and a link that is
       down from 20 s to 40 s into every run
  A6   a larger model on a nearby host, 5 ms away
  A5   a fast reviewer on the chip and a slow larger one at 150 ms
  ctl  a reviewer that always answers "healthy"

The delays are test fixtures, not measurements of any service.

Each row is the registered evaluation (`evpil.control.sensor_eval`). Fault
cases are run for every row; the clean cycles, which take most of the time,
for the rows marked so. Rows already in the output file are not run again.
SIMULATED on the laptop.

    PYTHONPATH="src:." python3 scripts/run_arch_study.py --split val
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

from scripts.run_sensor_eval import evaluate

SMALL = ("monitor", "gru16", "fastgrnn16")
HOST = "gru64"
OUTAGE = ((20.0, 40.0),)


def rows(reviewers=SMALL, host=HOST,
         ablations=False) -> list[tuple[str, str, dict | None, bool]]:
    """(name, arm, settings, also run the clean cycles)."""
    out = [("A0 b7", "b7", None, True),
           ("ctl healthy", "sup", {"fast": "healthy"}, True)]
    for r in reviewers if not ablations else ():
        out.append((f"A2 {r}", "sup", {"fast": r}, True))
        for ms in (70, 150, 500, 1000):
            out.append((f"A1 {r} {ms}ms", "sup", {
                "slow": r, "delay_s": ms / 1000.0,
                "jitter_s": 0.2 * ms / 1000.0}, ms == 150))
        base = {"slow": r, "delay_s": 0.15, "jitter_s": 0.03}
        out.append((f"A1e {r} 150ms", "sup",
                    {**base, "policy": {"trigger": "event"}}, False))
        out.append((f"A1c {r} 150ms", "sup",
                    {**base, "policy": {"expiry_s": 5.0}}, False))
        out.append((f"A1x {r} 150ms", "sup",
                    {**base, "loss": 0.2, "outages": OUTAGE}, False))
    if ablations:
        # One bounded setting at a time, reviewer on the chip: which of the
        # four things a diagnosis may change is doing the good or the harm.
        only = {"hold": "use_hold", "release": "use_release",
                "fallback": "use_fallback", "vigilance": "use_vigilance"}
        for r in reviewers:
            for label, keep in only.items():
                pol = {k: k == keep for k in only.values()}
                out.append((f"A2 {r} {label} only", "sup",
                            {"fast": r, "policy": pol}, False))
            # The default lets a hold run for ten seconds. While it runs the
            # loop is on dead reckoning or the model, and both drift.
            out.append((f"A2 {r} hold 2 s", "sup",
                        {"fast": r, "policy": {"max_hold_s": 2.0}}, True))
        return out
    if host:
        out.append((f"A6 {host}", "sup",
                    {"slow": host, "delay_s": 0.005}, True))
        for r in reviewers:
            if not r.startswith("fastgrnn"):
                out.append((f"A5 {r}+{host} 150ms", "sup", {
                    "fast": r, "slow": host, "delay_s": 0.15,
                    "jitter_s": 0.03}, False))
    return out


def summarise(v: dict) -> dict:
    """One line per row: the registered counts, pooled over the
    acceleration cases, and the worst case beside them."""
    g = list(v["by_accel"].values())
    s = lambda k: sum(x.get(k, 0) for x in g)
    out = {"named_faults": s("named_faults"),
           "detected_in_time": s("detected_in_time"),
           "false_clears": s("false_clears"),
           "lingering_flags": s("lingering_flags"),
           "false_alarms_before_onset": s("false_alarms_before_onset"),
           "worst_peak_err_mps": max(x["worst_peak_err_mps"] for x in g),
           "median_peak_err_mps_worst_case": max(
               x["median_peak_err_mps"] for x in g),
           "cleared_within_2s_frac_worst_case": min(
               x["cleared_within_2s_frac"] for x in g)}
    if "clean_hours_floor" in g[0]:
        out.update({
            "clean_hours_floor": s("clean_hours_floor"),
            "false_alarms_floor": s("false_alarms_floor"),
            "false_alarms_10x": s("false_alarms_10x"),
            "worst_clean_rmse_mps": max(x["worst_clean_rmse_mps"] for x in g),
            "worst_energy_gap_frac": max(x["worst_energy_gap_frac"] for x in g),
            "cases_passed": v["cases_passed"],
            "cases_judged": v["cases_judged"]})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="val", choices=("val", "test"))
    ap.add_argument("--only", default=None,
                    help="comma-separated row names; default all")
    ap.add_argument("--reviewers", default=",".join(SMALL))
    ap.add_argument("--host", default=HOST)
    ap.add_argument("--ablations", action="store_true",
                    help="run the one-setting-at-a-time rows instead")
    ap.add_argument("--procs", type=int, default=4)
    ap.add_argument("--out-json", default=None)
    args = ap.parse_args()

    path = Path(args.out_json or f"docs/week13-arch-{args.split}.json")
    doc = (json.loads(path.read_text()) if path.exists() else {
        "provenance": "SIMULATED on the laptop; no board involved; link "
                      "delays are fixtures, not measurements of a service",
        "split": args.split, "rows": {}})
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                            capture_output=True, text=True).stdout.strip()
    want = args.only.split(",") if args.only else None
    t0 = time.time()
    for name, arm, settings, clean in rows(
            tuple(r for r in args.reviewers.split(",") if r), args.host,
            args.ablations):
        if (want and name not in want) or name in doc["rows"]:
            continue
        out = evaluate(arm, args.split, settings=settings, clean=clean,
                       procs=args.procs)
        applied: dict = {}
        for r in out["faults"] + out["clean"]:
            for k, n in r.get("supervisor", {}).items():
                applied[k] = applied.get(k, 0) + n
        doc["rows"][name] = {
            "arm": arm, "settings": settings, "clean_run": clean,
            "commit": commit, "seconds": out["seconds"],
            "summary": summarise(out["verdict"]),
            "verdict": out["verdict"], "supervisor_actions": applied}
        path.write_text(json.dumps(doc, indent=1) + "\n")
        s = doc["rows"][name]["summary"]
        print(f"{name:28s} caught {s['detected_in_time']}/{s['named_faults']}"
              f"  false clears {s['false_clears']:3d}  lingering "
              f"{s['lingering_flags']:3d}  worst peak "
              f"{s['worst_peak_err_mps']:.2f}  median(worst case) "
              f"{s['median_peak_err_mps_worst_case']:.2f}"
              + (f"  clean alarms {s['false_alarms_floor']}"
                 f"+{s['false_alarms_10x']}  passed {s['cases_passed']}"
                 f"/{s['cases_judged']}" if clean else "")
              + f"  [{time.time() - t0:.0f} s]", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
