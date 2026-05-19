#!/usr/bin/env python3
"""Bookkeeping helper for the subagent-driven Sonnet baseline run.

The subagent invocations are done from the parent conversation (one Agent tool
call per stage). This script handles the deterministic glue: workdir seeding,
test drop, pytest + junit, baseline persistence, timing CSV, and per-phase git
commit. Each step is its own subcommand so the parent can call them between
agent invocations.
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SPEC = ROOT / "spec"
RESULTS = ROOT / "results"
LABEL = "A_subagent"
WORKROOT = ROOT / f"Model{LABEL[0]}_subagent"
VENV_PY = ROOT / ".venv" / "bin" / "python"
TIMINGS = RESULTS / "timings.csv"

SCRATCH_PATTERNS = (
    "debug_*.py", "simple_*.py", "minimal_*.py", "detailed_*.py",
    "very_*.py", "final_*.py", "test_*.py",
    "*.tl", "*.py.backup",
)
SCRATCH_PRESERVE = {"tinylang_cli.py", "stdlib.tl"}


def phase_wd(phase: int) -> Path:
    return WORKROOT / f"phase_{phase:02d}"


def sweep_scratch(wd: Path) -> list[str]:
    removed = []
    for pat in SCRATCH_PATTERNS:
        for p in wd.glob(pat):
            if not p.is_file() or p.name in SCRATCH_PRESERVE:
                continue
            try:
                p.unlink()
                removed.append(p.name)
            except OSError:
                pass
    return removed


def clean_caches(wd: Path) -> None:
    for d in wd.rglob("__pycache__"):
        if d.is_dir():
            shutil.rmtree(d, ignore_errors=True)
    pc = wd / ".pytest_cache"
    if pc.exists():
        shutil.rmtree(pc, ignore_errors=True)


def seed(phase: int) -> None:
    """Seed workdir for phase N from phase N-1 (or empty for phase 1)."""
    wd = phase_wd(phase)
    if wd.exists():
        print(f"phase {phase:02d} workdir already exists, leaving alone")
        return
    if phase == 1:
        wd.mkdir(parents=True)
        print(f"created empty phase {phase:02d} workdir")
        return
    prior = phase_wd(phase - 1)
    if not prior.exists():
        sys.exit(f"prior phase {phase-1:02d} workdir missing: {prior}")
    shutil.copytree(prior, wd)
    clean_caches(wd)
    # tests/ from prior phase persists for cumulative regression checks
    removed = sweep_scratch(wd)
    if removed:
        print(f"swept {len(removed)} scratch files: {', '.join(removed[:6])}"
              f"{'...' if len(removed) > 6 else ''}")
    print(f"seeded phase {phase:02d} from phase {phase-1:02d}")


def drop_tests(phase: int) -> None:
    """Copy phase N tests into workdir/tests/ (cumulative — keeps prior tests)."""
    wd = phase_wd(phase)
    src = SPEC / "tests" / f"phase_{phase:02d}"
    if not src.exists():
        sys.exit(f"spec tests dir missing: {src}")
    dst = wd / "tests"
    dst.mkdir(exist_ok=True)
    n = 0
    for f in src.glob("*.py"):
        shutil.copy(f, dst / f.name)
        n += 1
    print(f"dropped {n} test file(s) into {dst}")


def _parse_passed_ids(junit_xml: Path) -> list[str]:
    if not junit_xml.exists():
        return []
    tree = ET.parse(junit_xml)
    ids = []
    for tc in tree.iter("testcase"):
        if any(tc.find(t) is not None for t in ("failure", "error", "skipped")):
            continue
        cls = tc.attrib.get("classname", "") or ""
        name = tc.attrib.get("name", "") or ""
        ids.append(f"{cls}::{name}" if cls else name)
    return sorted(ids)


def _parse_pytest_summary(text: str) -> tuple[int, int]:
    """Find 'N passed' / 'M failed' / 'K errors' in the summary line."""
    passed = failed = 0
    for line in text.splitlines()[-15:]:
        l = line.lower().replace(",", " ").replace("=", " ")
        parts = l.split()
        for word in ("passed", "failed", "error", "errors"):
            for i, t in enumerate(parts):
                if t == word and i > 0:
                    try:
                        n = int(parts[i - 1])
                    except ValueError:
                        continue
                    if word == "passed":
                        passed = max(passed, n)
                    else:
                        failed = max(failed, n)
    return passed, failed


def grade(phase: int) -> dict:
    """Run pytest tests/ and save junit + passed_ids baseline."""
    wd = phase_wd(phase)
    junit = RESULTS / "baselines" / LABEL / f"phase_{phase:02d}_junit.xml"
    junit.parent.mkdir(parents=True, exist_ok=True)
    cmd = [str(VENV_PY), "-m", "pytest", "-q", "tests/", "--tb=short",
           f"--junitxml={junit}"]
    r = subprocess.run(cmd, cwd=str(wd), capture_output=True, text=True, timeout=300)
    out = r.stdout + "\n" + r.stderr
    passed, failed = _parse_pytest_summary(out)
    ids = _parse_passed_ids(junit)
    baseline = RESULTS / "baselines" / LABEL / f"phase_{phase:02d}_passed.json"
    baseline.write_text(json.dumps({"phase": phase, "passed_ids": ids}, indent=2))
    print(f"phase {phase:02d}: {passed} passed, {failed} failed/error, {len(ids)} ids saved")
    tail = "\n".join(r.stdout.splitlines()[-5:])
    print(tail)
    return {"passed": passed, "failed": failed, "passed_ids": ids,
            "returncode": r.returncode, "tail": tail}


def log(phase: int, stage: str, elapsed_s: float, steps: int,
        in_tok: int = 0, out_tok: int = 0,
        passed: int | None = None, failed: int | None = None,
        finish: str = "done") -> None:
    """Append a row to results/timings.csv."""
    TIMINGS.parent.mkdir(parents=True, exist_ok=True)
    new = not TIMINGS.exists()
    with TIMINGS.open("a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["phase", "model", "stage", "elapsed_s", "steps",
                        "input_tokens", "output_tokens", "finish_reason",
                        "test_pass_count", "test_fail_count"])
        w.writerow([phase, LABEL, stage, f"{elapsed_s:.2f}", steps,
                    in_tok, out_tok, finish,
                    "" if passed is None else passed,
                    "" if failed is None else failed])
    print(f"logged {stage} phase {phase:02d}")


def commit(phase: int, passed: int, total: int) -> None:
    wd = phase_wd(phase)
    clean_caches(wd)
    baselines = RESULTS / "baselines" / LABEL
    files = [
        str(wd.relative_to(ROOT.parent)),
        str((baselines / f"phase_{phase:02d}_passed.json").relative_to(ROOT.parent)),
        str((baselines / f"phase_{phase:02d}_junit.xml").relative_to(ROOT.parent)),
        str((RESULTS / "timings.csv").relative_to(ROOT.parent)),
    ]
    msg = f"benchmark A_subagent phase {phase:02d} — Sonnet baseline ({passed}/{total})"
    r = subprocess.run(["git", "add"] + files, cwd=str(ROOT.parent), capture_output=True, text=True)
    if r.returncode != 0:
        print("git add failed:", r.stderr)
        return
    r = subprocess.run(["git", "commit", "--no-verify", "-m", msg], cwd=str(ROOT.parent),
                       capture_output=True, text=True)
    print(r.stdout.strip() or r.stderr.strip())


def show_passed_ids(phase: int, max_show: int = 200) -> None:
    """Print up to max_show test ids that passed at end of phase, for next-phase regression baseline."""
    p = RESULTS / "baselines" / LABEL / f"phase_{phase:02d}_passed.json"
    if not p.exists():
        print(f"no baseline for phase {phase:02d}")
        return
    data = json.loads(p.read_text())
    ids = data.get("passed_ids", [])
    print(f"# {len(ids)} tests passed at end of phase {phase:02d}")
    for tid in ids[:max_show]:
        print(f"- {tid}")
    if len(ids) > max_show:
        print(f"- ... and {len(ids) - max_show} more")


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    for cmd in ("seed", "drop-tests", "grade"):
        sp = sub.add_parser(cmd)
        sp.add_argument("phase", type=int)

    sp = sub.add_parser("log")
    sp.add_argument("phase", type=int)
    sp.add_argument("stage", choices=["implement", "self_eval"])
    sp.add_argument("--elapsed", type=float, required=True)
    sp.add_argument("--steps", type=int, required=True)
    sp.add_argument("--in-tok", type=int, default=0)
    sp.add_argument("--out-tok", type=int, default=0)
    sp.add_argument("--passed", type=int)
    sp.add_argument("--failed", type=int)
    sp.add_argument("--finish", default="done")

    sp = sub.add_parser("commit")
    sp.add_argument("phase", type=int)
    sp.add_argument("--passed", type=int, required=True)
    sp.add_argument("--total", type=int, required=True)

    sp = sub.add_parser("show-passed")
    sp.add_argument("phase", type=int)
    sp.add_argument("--max", type=int, default=200)

    args = p.parse_args()
    if args.cmd == "seed":
        seed(args.phase)
    elif args.cmd == "drop-tests":
        drop_tests(args.phase)
    elif args.cmd == "grade":
        grade(args.phase)
    elif args.cmd == "log":
        log(args.phase, args.stage, args.elapsed, args.steps,
            args.in_tok, args.out_tok, args.passed, args.failed, args.finish)
    elif args.cmd == "commit":
        commit(args.phase, args.passed, args.total)
    elif args.cmd == "show-passed":
        show_passed_ids(args.phase, args.max)


if __name__ == "__main__":
    main()
