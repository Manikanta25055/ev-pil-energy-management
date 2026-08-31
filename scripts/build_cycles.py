"""Download the standard driving-cycle speed traces and cache them.

Spec 5.2 fixes the controller split: train on WLTP and UDDS, validate on
HWFET, test on US06. Those four traces are regulatory tables, not measurements,
so they are fetched once from their publishers and cached rather than typed in.

  python3 scripts/build_cycles.py

The EPA files are the dynamometer drive schedules distributed with the Federal
Test Procedure. They are published in miles per hour at one-second intervals.
The WLTC class 3b trace is the table in UN GTR No. 15, mirrored here from the
JRC's open-source WLTP implementation because UNECE publishes it inside a PDF
annex that would have to be scraped. It is published in kilometres per hour at
one-second intervals.

Provenance for every one of them is written into docs/dataset-provenance.md.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

import numpy as np

MPH_MPS = 0.44704
KPH_MPS = 1.0 / 3.6

SOURCES: dict[str, dict] = {
    "udds": {
        "url": "https://www.epa.gov/sites/default/files/2015-10/uddscol.txt",
        "unit": "mph", "layout": "t_v",
        "title": "Urban Dynamometer Driving Schedule (EPA city cycle)",
        "publisher": "US EPA, Dynamometer Drive Schedules",
    },
    "hwfet": {
        "url": "https://www.epa.gov/sites/default/files/2015-10/hwycol.txt",
        "unit": "mph", "layout": "t_v",
        "title": "Highway Fuel Economy Driving Schedule",
        "publisher": "US EPA, Dynamometer Drive Schedules",
    },
    "us06": {
        "url": "https://www.epa.gov/sites/default/files/2015-10/us06col.txt",
        "unit": "mph", "layout": "t_v",
        "title": "US06 Supplemental Federal Test Procedure (aggressive)",
        "publisher": "US EPA, Dynamometer Drive Schedules",
    },
    "ftp75": {
        "url": "https://www.epa.gov/sites/default/files/2015-10/ftpcol.txt",
        "unit": "mph", "layout": "t_v",
        "title": "Federal Test Procedure (FTP-75)",
        "publisher": "US EPA, Dynamometer Drive Schedules",
    },
    "wltc3b": {
        "url": "https://raw.githubusercontent.com/JRCSTU/wltp/master/"
               "wltp/cycles/V_class3b.txt",
        "unit": "kph", "layout": "flat",
        "title": "WLTC class 3b, UN GTR No. 15 Annex 1",
        "publisher": "UNECE GTR 15, via JRCSTU/wltp (EUPL-1.2)",
    },
}


def parse_trace(text: str, unit: str, layout: str) -> tuple[np.ndarray, np.ndarray]:
    """Return (t_s, v_mps) from a published trace file.

    Layout is declared per source rather than inferred. The two files differ in
    a way that no heuristic reads safely: EPA ships `time speed` pairs one per
    line, and the JRC file ships speeds alone, wrapped across lines at whatever
    width the file was written at. A guess that reads a wrapped stream as
    columns produces a plausible-looking cycle of the wrong length, which is
    the kind of error that survives to a results table.
    """
    values: list[float] = []
    rows: list[list[float]] = []
    for line in text.splitlines():
        fields = line.replace(",", " ").split()
        try:
            nums = [float(f) for f in fields]
        except ValueError:
            continue                      # header or comment line
        rows.append(nums)
        values.extend(nums)

    if layout == "t_v":
        pairs = [r for r in rows if len(r) == 2]
        if len(pairs) < 2:
            raise ValueError("declared two-column layout, found no pairs")
        arr = np.array(pairs, dtype=float)
        t_s, v_raw = arr[:, 0], arr[:, 1]
    elif layout == "flat":
        v_raw = np.array(values, dtype=float)
        t_s = np.arange(len(v_raw), dtype=float)     # published at 1 Hz
    else:
        raise ValueError(f"unknown layout {layout!r}")

    scale = MPH_MPS if unit == "mph" else KPH_MPS
    return t_s, v_raw * scale


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="data/raw/cycles")
    ap.add_argument("--timeout", type=float, default=60.0)
    args = ap.parse_args()

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    manifest = {}

    for name, meta in SOURCES.items():
        print(f"{name:8} <- {meta['url']}")
        try:
            with urllib.request.urlopen(meta["url"], timeout=args.timeout) as fh:
                text = fh.read().decode("utf-8", errors="replace")
        except OSError as exc:
            print(f"  FAILED: {exc}", file=sys.stderr)
            return 1

        (out / f"{name}.txt").write_text(text)
        t_s, v_mps = parse_trace(text, meta["unit"], meta["layout"])
        np.savez(out / f"{name}.npz", t_s=t_s, v_mps=v_mps)

        dist_km = float(np.trapezoid(v_mps, t_s) / 1000.0)
        manifest[name] = {
            **{k: v for k, v in meta.items() if k not in ("unit", "layout")},
            "source_unit": meta["unit"],
            "n_samples": int(len(v_mps)),
            "duration_s": float(t_s[-1]),
            "distance_km": dist_km,
            "v_max_mps": float(v_mps.max()),
            "v_mean_mps": float(v_mps.mean()),
        }
        print(f"  {len(v_mps):5d} samples, {t_s[-1]:6.0f} s, "
              f"{dist_km:6.2f} km, v_max {v_mps.max() * 3.6:5.1f} km/h")

    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"\nwrote {out}/manifest.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
