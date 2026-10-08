"""Print the architecture study as Markdown tables, from its JSON.

    PYTHONPATH="src:." python3 scripts/report_arch_study.py --split val
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="val")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()
    doc = json.loads(Path(
        args.json or f"docs/week13-arch-{args.split}.json").read_text())
    print("| Row | Caught in 0.5 s | Early releases | Flags stuck at 8 s | "
          "Worst peak error, m/s | Median peak error, worst case, m/s | "
          "Clean false alarms (floor + 10x) | Cases passed |")
    print("|---|---|---|---|---|---|---|---|")
    for name, r in doc["rows"].items():
        s = r["summary"]
        clean = (f"{s['false_alarms_floor']} + {s['false_alarms_10x']}"
                 if "false_alarms_floor" in s else "not run")
        passed = (f"{s['cases_passed']} of {s['cases_judged']}"
                  if "cases_passed" in s else "")
        print(f"| {name} | {s['detected_in_time']} of {s['named_faults']} | "
              f"{s['false_clears']} | {s['lingering_flags']} | "
              f"{s['worst_peak_err_mps']:.2f} | "
              f"{s['median_peak_err_mps_worst_case']:.2f} | {clean} | "
              f"{passed} |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
