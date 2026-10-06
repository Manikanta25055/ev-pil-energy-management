"""Finish the corrected campaign only after its existing board chain exits."""

from __future__ import annotations

import argparse
from datetime import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from scripts.corrected_campaign import DURATIONS, load_corrected_a4, validate_campaign

ROOT = Path(__file__).resolve().parents[1]
NIGHT = ROOT / ".claude/night"
LOG = NIGHT / "finalize-corrected.log"
STATUS = NIGHT / "finalize-corrected-status.json"
SOURCES = ("scripts/build_report.py", "scripts/plot_pil.py",
           "scripts/plot_a4_sweep.py", "scripts/build_supervisor_note.py",
           "scripts/corrected_campaign.py", "scripts/finalize_corrected_campaign.py",
           "scripts/arduino_build.sh",
           "tests/test_corrected_finalization.py", "AGENTS.md", "src/evpil/plant/plant.py",
           "firmware/main/sac_actor_weights.h")


def hashes(paths):
    return {str(p): hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths}


def board_progress():
    counts = []
    for arm in ("rule", "actor"):
        p = ROOT / f"docs/week11-pil-corrected-{arm}.json"
        try:
            counts.append(len(json.loads(p.read_text())["runs"]))
        except (FileNotFoundError, json.JSONDecodeError):
            counts.append(0)
    a4 = sum((ROOT / f"docs/week11-a4-{mode}-{s}s.json").exists()
             for s in DURATIONS for mode in ("on", "off"))
    return tuple(counts) + (a4,)


def record(phase, message, chain_pid=None):
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    progress = board_progress()
    print(f"{now} {phase}: {message}; rule {progress[0]}/18, "
          f"actor {progress[1]}/18, A4 {progress[2]}/16", flush=True)
    STATUS.write_text(json.dumps({"time": now, "phase": phase, "message": message,
                                 "pid": os.getpid(), "chain_pid": chain_pid,
                                 "progress": progress}, indent=2) + "\n")
    memory = ROOT / ".remember"
    memory.mkdir(exist_ok=True)
    with (memory / "now.md").open("a") as f:
        f.write(f"\n## {now} | corrected campaign finisher\nI recorded {phase}: "
                f"{message}. Saved cells: rules {progress[0]}/18, actor "
                f"{progress[1]}/18, A4 {progress[2]}/16. See {STATUS.relative_to(ROOT)} "
                f"and {LOG.relative_to(ROOT)}.\n")
    branch = subprocess.check_output(["git", "branch", "--show-current"], text=True).strip()
    commit = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    (memory / "remember.md").write_text(
        "# Handoff\n\n## State\n"
        f"I am on `{branch}` at `{commit}`. As of {now}, phase is `{phase}`: {message}.\n"
        f"Saved corrected cells: rules {progress[0]}/18, actor {progress[1]}/18, "
        f"A4 {progress[2]}/16. Finisher PID {os.getpid()}; existing chain PID {chain_pid}.\n"
        "The power-ceiling plant fault is fixed and the old 8.28% gain is withdrawn. "
        "Corrected SAC retraining is exported; no energy conclusion is assumed before measurement.\n"
        "\n## Next\n"
        "1. Read `.claude/night/finalize-corrected-status.json` and "
        "`finalize-corrected.log`; do not start duplicate board or finisher jobs.\n"
        "2. If blocked, fix only the reported failure and resume from saved data. "
        "Do not claim full tests, reports, commits or board validation unless the log confirms them.\n"
        "3. Review the report and supervisor note; sending the note or merging the "
        "classical branch needs a separate explicit request.\n"
        "\n## Context\n"
        "The rule re-run selector was fixed to drops >16 AND RMSE <1 m/s, keeping "
        "the two invalid delay cells visible without repeating them. Quiet host required.\n"
        "`feature/decision-model` stays unmerged at `5305706` in `.worktrees/decision-model`. "
        "B6 evidence is simulated with idealised acceleration; transformer dropped. "
        "Only the earlier one-state Kalman has a C port; B5/B6 need porting and parity first.\n"
        "Prose linter is `~/.claude/tools/prose_lint.py`; report findings remain "
        "0 HIGH, 3 MED, 2 LOW categories, note generator clean.\n")


def run(command, env):
    with LOG.open("a") as out:
        out.write("\n" + repr(command) + "\n")
        out.flush()
        subprocess.run(command, env=env, stdout=out, stderr=subprocess.STDOUT, check=True)


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chain-pid", type=int, required=True)
    ap.add_argument("--robustness-docs", type=Path)
    ap.add_argument("--commit", action="store_true")
    args = ap.parse_args()
    os.chdir(ROOT)
    NIGHT.mkdir(exist_ok=True)
    with (NIGHT / "finalize-corrected.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit("another corrected campaign finisher is active")
        initial = hashes(SOURCES)
        try:
            record("waiting", "No heavy work until the existing board chain exits", args.chain_pid)
            previous = board_progress()
            while alive(args.chain_pid):
                time.sleep(30)
                progress = board_progress()
                if progress != previous:
                    record("waiting", "Existing board chain is still running", args.chain_pid)
                    previous = progress
            if hashes(SOURCES) != initial:
                raise ValueError("a source or actor header changed while waiting; review before finalizing")
            campaign = json.loads(Path("docs/week11-pil-corrected.json").read_text())
            summary = validate_campaign(campaign)
            pairs = load_corrected_a4(Path("docs"))
            if pairs is None:
                raise ValueError("board chain ended without all sixteen corrected A4 files")
            env = {**os.environ, "PYTHONPATH": "src:.", "OPENBLAS_NUM_THREADS": "1",
                   "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
            record("restoring", "A4 is complete; restoring the normal actor image with handling enabled", args.chain_pid)
            flash_env = {**env, "EVPIL_PORT": campaign["port"],
                         "EVPIL_ARDUINO_DIR": str(Path.home() / ".cache/evpil-arduino-a4on")}
            run(["bash", "scripts/arduino_build.sh", "--flash",
                 "-DFAULT_INJECT=0", "-DFALLBACK_ENABLED=1"], flash_env)
            record("building", "Normal firmware restored; building figures and documents", args.chain_pid)
            commands = [
                [sys.executable, "-m", "scripts.plot_pil", "--campaign",
                 "docs/week11-pil-corrected.json", "--out", "docs/figures/pil-energy-corrected.png"],
                [sys.executable, "-m", "scripts.plot_a4_sweep", "--prefix", "week11-a4",
                 "--out", "docs/figures/week11-a4-corrected-sweep.png"],
                [sys.executable, "-m", "scripts.build_report"],
                [sys.executable, "-m", "scripts.build_supervisor_note"],
            ]
            if args.robustness_docs:
                commands[-1] += ["--robustness-docs", str(args.robustness_docs)]
            for command in commands:
                run(command, env)
            record("testing", "Documents built; full test suite is now running", args.chain_pid)
            run([sys.executable, "-m", "pytest", "tests", "-q"], env)
            renderer = Path.home() / ".codex/plugins/cache/openai-primary-runtime/documents/26.904.11930/skills/documents/render_docx.py"
            render_root = Path("/private/tmp/evpil-corrected-review")
            if not renderer.exists():
                raise FileNotFoundError(f"document renderer missing: {renderer}")
            record("rendering", "Full tests passed; rendering documents for visual review", args.chain_pid)
            for name in ("EV-PIL-status-report", "supervisor-correction-note"):
                run([sys.executable, str(renderer), f"reports/{name}.docx",
                     "--output_dir", str(render_root / name), "--emit_pdf"],
                    {**env, "PYTHONPATH": env["PYTHONPATH"] + ":/private/tmp/evpil-render-deps"})
            measurements = [Path("docs/week11-pil-corrected.json"),
                            Path("docs/week11-sac-corrected.json")]
            measurements += [Path(f"docs/week11-a4-{mode}-{s}s.json")
                             for s in DURATIONS for mode in ("on", "off")]
            outputs = [Path("reports/EV-PIL-status-report.docx"),
                       Path("reports/supervisor-correction-note.docx"),
                       Path("docs/figures/pil-energy-corrected.png"),
                       Path("docs/figures/week11-a4-corrected-sweep.png")]
            manifest = {"summary": summary, "source_sha256": initial,
                        "measurement_sha256": hashes(measurements),
                        "output_sha256": hashes(outputs), "full_tests_passed": True,
                        "normal_actor_firmware_restored": True,
                        "visual_review_pending": True, "render_directory": str(render_root)}
            if args.robustness_docs:
                p = args.robustness_docs / "week11-fault-arms-b6.json"
                manifest["simulation_only_robustness_sha256"] = hashes([p])
            evidence = Path("docs/week11-corrected-finalization.json")
            evidence.write_text(json.dumps(manifest, indent=2) + "\n")
            if args.commit:
                run(["git", "diff", "--check"], env)
                run(["git", "diff", "--cached", "--quiet"], env)
                run(["git", "add", "--", *map(str, measurements + outputs + [evidence]),
                     *SOURCES], env)
                run(["git", "commit", "-m",
                     "Report the corrected board campaign and outage sweep from measured data"], env)
            record("review_pending", "Reports rebuilt, full tests passed, documents rendered; "
                   + ("artifacts committed; " if args.commit else "")
                   + f"visual review remains at {render_root}",
                   args.chain_pid)
            return 0
        except Exception as exc:
            record("blocked", f"{type(exc).__name__}: {exc}", args.chain_pid)
            raise


if __name__ == "__main__":
    raise SystemExit(main())
