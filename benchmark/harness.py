#!/usr/bin/env python3
"""Benchmark harness: drives two models through the 12-phase tinylang build.

Both models go through the local LiteLLM proxy on port 4000, using the
OpenAI-compatible chat-completions API with tool use.

Subcommands:
    python harness.py models                                # smoke-test both models
    python harness.py phase --num 1 --model A               # implement + self-eval one phase, one model
    python harness.py phase --num 1 --model both            # implement + self-eval both models
    python harness.py cross-eval --phase 1                  # both directions of cross-eval
    python harness.py final-eval                            # final whole-repo cross-eval
    python harness.py run-all                               # phases 1..12 + final cross-eval

Results land under benchmark/results/. See benchmark/README.md.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

try:
    from openai import OpenAI
except ImportError:
    print("error: install the openai package: pip install 'openai>=1.40'", file=sys.stderr)
    raise


# ----------------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent
SPEC = ROOT / "spec"
RESULTS = ROOT / "results"
TRANSCRIPTS = RESULTS / "transcripts"
TIMINGS_CSV = RESULTS / "timings.csv"

LITELLM_URL = os.environ.get("LITELLM_URL", "http://localhost:4000/v1")
LITELLM_KEY = os.environ.get("LITELLM_MASTER_KEY", "sk-gateway-master-change-me")

MODELS = {
    "A": {"display": "Sonnet 4", "litellm_id": "claude-sonnet"},
    "B": {"display": "local-coding", "litellm_id": "local-coding"},
}

STEP_CAP_IMPLEMENT = 80
STEP_CAP_SELFEVAL = 40
STEP_CAP_CROSSEVAL = 40
BASH_TIMEOUT = 60
RESULT_TRUNCATE = 4000  # characters per tool result fed back to the model

TEMPERATURE = 0.2
MAX_TOKENS = 4096

# CLI-settable overrides (mutated by main()).
WORKDIR_SUFFIX = ""    # appended to ModelX directory name
LABEL = ""             # appended to model_key in timing/result rows (e.g. "B_thinkoff")
EXTRA_BODY: dict = {}  # merged into every chat.completions.create call


PHASE_FILES = {
    1: "phase_01_lexer.md",
    2: "phase_02_parser.md",
    3: "phase_03_evaluator.md",
    4: "phase_04_scope.md",
    5: "phase_05_control_flow.md",
    6: "phase_06_functions.md",
    7: "phase_07_closures.md",
    8: "phase_08_lists.md",
    9: "phase_09_dicts.md",
    10: "phase_10_errors.md",
    11: "phase_11_stdlib.md",
    12: "phase_12_repl.md",
}


# ----------------------------------------------------------------------------
# Tool schemas (OpenAI function-calling format)
# ----------------------------------------------------------------------------

def _tool(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
        },
    }


TOOLS_FULL = [
    _tool(
        "read_file",
        "Read a UTF-8 text file relative to the workdir.",
        {"path": {"type": "string", "description": "Relative path inside workdir."}},
        ["path"],
    ),
    _tool(
        "write_file",
        "Write (or overwrite) a UTF-8 text file relative to the workdir. Parents created.",
        {
            "path": {"type": "string"},
            "content": {"type": "string"},
        },
        ["path", "content"],
    ),
    _tool(
        "edit_file",
        "Replace `old_string` with `new_string` in `path`. Fails if `old_string` is absent or non-unique.",
        {
            "path": {"type": "string"},
            "old_string": {"type": "string"},
            "new_string": {"type": "string"},
        },
        ["path", "old_string", "new_string"],
    ),
    _tool(
        "list_dir",
        "List files/dirs under `path` (default '.') one level deep.",
        {"path": {"type": "string"}},
        [],
    ),
    _tool(
        "run_bash",
        f"Run a bash command in the workdir. {BASH_TIMEOUT}s timeout. stdout/stderr/exit code returned.",
        {"command": {"type": "string"}},
        ["command"],
    ),
    _tool(
        "done",
        "Call when you have finished this phase and want to stop the loop.",
        {"summary": {"type": "string", "description": "One-paragraph summary of what you did."}},
        ["summary"],
    ),
]

TOOLS_READONLY = [
    _tool(
        "read_file",
        "Read a UTF-8 text file relative to the workdir.",
        {"path": {"type": "string"}},
        ["path"],
    ),
    _tool(
        "list_dir",
        "List files/dirs under `path` (default '.') one level deep.",
        {"path": {"type": "string"}},
        [],
    ),
    _tool(
        "score",
        "Submit your final review. Call this exactly once when you have finished evaluating.",
        {
            "accuracy": {
                "type": "integer",
                "description": "0-100. Would this implementation pass the acceptance tests? How correct/bug-free is it?",
            },
            "completeness": {
                "type": "integer",
                "description": "0-100. Coverage of the brief: edge cases, error messages, code organization, all required features.",
            },
            "rationale": {
                "type": "string",
                "description": "3-5 sentences. Specific strengths and weaknesses. Cite file paths.",
            },
        },
        ["accuracy", "completeness", "rationale"],
    ),
]


# ----------------------------------------------------------------------------
# Sandboxed filesystem dispatcher
# ----------------------------------------------------------------------------

class SandboxError(Exception):
    pass


def _resolve(workdir: Path, rel: str) -> Path:
    if rel is None:
        rel = "."
    p = (workdir / rel).resolve()
    wd = workdir.resolve()
    if not (p == wd or wd in p.parents):
        raise SandboxError(f"path escapes workdir: {rel}")
    return p


def make_dispatcher(workdir: Path, readonly: bool) -> dict[str, Callable]:
    workdir.mkdir(parents=True, exist_ok=True)

    def read_file(path: str) -> str:
        p = _resolve(workdir, path)
        if not p.exists():
            return f"ERROR: file not found: {path}"
        if not p.is_file():
            return f"ERROR: not a file: {path}"
        try:
            data = p.read_text()
        except UnicodeDecodeError:
            return f"ERROR: binary or non-UTF-8 file: {path}"
        return data

    def write_file(path: str, content: str) -> str:
        if readonly:
            return "ERROR: read-only sandbox"
        p = _resolve(workdir, path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return f"wrote {len(content)} bytes to {path}"

    def edit_file(path: str, old_string: str, new_string: str) -> str:
        if readonly:
            return "ERROR: read-only sandbox"
        p = _resolve(workdir, path)
        if not p.exists():
            return f"ERROR: file not found: {path}"
        text = p.read_text()
        count = text.count(old_string)
        if count == 0:
            return f"ERROR: old_string not found in {path}"
        if count > 1:
            return f"ERROR: old_string is not unique in {path} (found {count} times). Provide more context."
        p.write_text(text.replace(old_string, new_string, 1))
        return f"edited {path}"

    def list_dir(path: str = ".") -> str:
        p = _resolve(workdir, path)
        if not p.exists():
            return f"ERROR: not found: {path}"
        if p.is_file():
            return f"FILE: {path}"
        entries = []
        for child in sorted(p.iterdir()):
            kind = "DIR" if child.is_dir() else "FILE"
            size = "" if child.is_dir() else f" ({child.stat().st_size}b)"
            entries.append(f"{kind} {child.name}{size}")
        return "\n".join(entries) if entries else "(empty)"

    def run_bash(command: str) -> str:
        if readonly:
            return "ERROR: read-only sandbox"
        env = os.environ.copy()
        venv_bin = str(Path(sys.executable).parent)
        env["PATH"] = f"{venv_bin}:{env.get('PATH', '')}"
        env["PYTHONIOENCODING"] = "utf-8"
        try:
            r = subprocess.run(
                ["bash", "-c", command],
                cwd=str(workdir),
                capture_output=True,
                text=True,
                timeout=BASH_TIMEOUT,
                env=env,
            )
        except subprocess.TimeoutExpired:
            return f"ERROR: command timed out after {BASH_TIMEOUT}s"
        out = r.stdout
        err = r.stderr
        return f"exit={r.returncode}\n--stdout--\n{out}\n--stderr--\n{err}"

    d: dict[str, Callable] = {
        "read_file": read_file,
        "list_dir": list_dir,
    }
    if not readonly:
        d["write_file"] = write_file
        d["edit_file"] = edit_file
        d["run_bash"] = run_bash
    return d


# ----------------------------------------------------------------------------
# OpenAI / LiteLLM client
# ----------------------------------------------------------------------------

def make_client() -> OpenAI:
    return OpenAI(api_key=LITELLM_KEY, base_url=LITELLM_URL)


def _serialize_assistant_message(msg) -> dict:
    """OpenAI SDK ChatCompletionMessage → wire-format dict for re-sending."""
    out: dict[str, Any] = {"role": "assistant", "content": msg.content or ""}
    if getattr(msg, "tool_calls", None):
        out["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments or "{}",
                },
            }
            for tc in msg.tool_calls
        ]
    return out


@dataclass
class LoopResult:
    elapsed_s: float
    steps: int
    done_payload: dict | None
    score_payload: dict | None
    transcript_path: Path
    finish_reason: str  # "done" | "score" | "step_cap" | "stop_no_done" | "api_error"
    error: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0


def run_tool_loop(
    *,
    model_id: str,
    system_prompt: str,
    user_prompt: str,
    workdir: Path,
    cap: int,
    readonly: bool,
    transcript_path: Path,
    allow_done: bool = True,
    allow_score: bool = False,
) -> LoopResult:
    """Run a tool-using chat loop until the model calls done()/score() or hits cap."""
    client = make_client()
    tools = TOOLS_READONLY if readonly else TOOLS_FULL
    # Filter tools by which terminators we allow
    tools = [
        t for t in tools
        if not (t["function"]["name"] == "done" and not allow_done)
        and not (t["function"]["name"] == "score" and not allow_score)
    ]
    dispatcher = make_dispatcher(workdir, readonly=readonly)

    messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    transcript: list[dict] = []
    start = time.time()
    steps = 0
    done_payload = None
    score_payload = None
    finish = "step_cap"
    error_msg = None
    in_tokens = 0
    out_tokens = 0

    transcript_path.parent.mkdir(parents=True, exist_ok=True)

    while steps < cap:
        try:
            kwargs = dict(
                model=model_id,
                messages=messages,
                tools=tools,
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS,
            )
            if EXTRA_BODY:
                kwargs["extra_body"] = EXTRA_BODY
            resp = client.chat.completions.create(**kwargs)
        except Exception as e:
            finish = "api_error"
            error_msg = f"{type(e).__name__}: {e}"
            transcript.append({"step": steps, "api_error": error_msg})
            break

        if resp.usage:
            in_tokens += resp.usage.prompt_tokens or 0
            out_tokens += resp.usage.completion_tokens or 0

        choice = resp.choices[0]
        msg = choice.message
        assistant_dict = _serialize_assistant_message(msg)
        messages.append(assistant_dict)
        transcript.append({"step": steps, "assistant": assistant_dict})

        tcs = getattr(msg, "tool_calls", None) or []
        if not tcs:
            # Model emitted plain text and stopped. Push back once asking for an explicit terminator.
            if (allow_done and not done_payload) or (allow_score and not score_payload):
                nudge = (
                    "You stopped without calling the required terminating tool. "
                    "Please call `done(summary=...)` when finished."
                    if allow_done else
                    "You stopped without calling `score(accuracy=..., completeness=..., rationale=...)`. "
                    "Please submit your score now."
                )
                messages.append({"role": "user", "content": nudge})
                transcript.append({"step": steps, "nudge": nudge})
                steps += 1
                continue
            finish = "stop_no_done"
            break

        terminated = False
        for tc in tcs:
            name = tc.function.name
            raw_args = tc.function.arguments or "{}"
            try:
                args = json.loads(raw_args)
            except json.JSONDecodeError as e:
                result_str = f"ERROR: tool arguments not valid JSON: {e}\nReceived: {raw_args[:500]}"
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": result_str})
                transcript.append({"step": steps, "tool": name, "args_raw": raw_args[:500], "result": result_str[:500]})
                continue

            if name == "done" and allow_done:
                done_payload = args
                result_str = "done acknowledged"
                terminated = True
            elif name == "score" and allow_score:
                score_payload = args
                result_str = "score recorded"
                terminated = True
            elif name in dispatcher:
                try:
                    result_str = dispatcher[name](**args)
                except SandboxError as e:
                    result_str = f"ERROR: {e}"
                except TypeError as e:
                    result_str = f"ERROR: bad arguments to {name}: {e}"
                except Exception as e:
                    result_str = f"ERROR running {name}: {type(e).__name__}: {e}"
            else:
                result_str = f"ERROR: unknown tool {name}"

            if not isinstance(result_str, str):
                result_str = str(result_str)
            if len(result_str) > RESULT_TRUNCATE:
                result_str = result_str[:RESULT_TRUNCATE] + f"\n... [truncated, total {len(result_str)} chars]"

            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result_str})
            transcript.append({
                "step": steps,
                "tool": name,
                "args": args,
                "result_preview": result_str[:500],
                "result_len": len(result_str),
            })

        steps += 1
        if terminated:
            if done_payload is not None:
                finish = "done"
            elif score_payload is not None:
                finish = "score"
            break

    elapsed = time.time() - start
    transcript_path.write_text(json.dumps(transcript, indent=2, default=str))

    return LoopResult(
        elapsed_s=elapsed,
        steps=steps,
        done_payload=done_payload,
        score_payload=score_payload,
        transcript_path=transcript_path,
        finish_reason=finish,
        error=error_msg,
        input_tokens=in_tokens,
        output_tokens=out_tokens,
    )


# ----------------------------------------------------------------------------
# Workdir management
# ----------------------------------------------------------------------------

def model_root(model_key: str) -> Path:
    return ROOT / f"Model{model_key}{WORKDIR_SUFFIX}"


def label_for(model_key: str) -> str:
    """Tag used in result filenames and timing rows. Defaults to model_key."""
    return LABEL if LABEL else model_key


def phase_workdir(model_key: str, phase: int) -> Path:
    return model_root(model_key) / f"phase_{phase:02d}"


SCRATCH_PATTERNS = (
    "debug_*.py", "simple_*.py", "minimal_*.py", "detailed_*.py",
    "very_*.py", "final_*.py", "test_*.py",
    "*.tl", "*.py.backup",
)
# Root-level deliverables that match scratch patterns but must be preserved.
SCRATCH_PRESERVE = {"tinylang_cli.py", "stdlib.tl"}


def sweep_scratch(workdir: Path) -> list[str]:
    """Delete scratch/debug files at the workdir root (non-recursive).

    Returns the names that were removed (for logging). Pattern matches only
    the top level of workdir — anything under tinylang/, tests/, scratch/ is
    left alone.
    """
    removed: list[str] = []
    for pat in SCRATCH_PATTERNS:
        for p in workdir.glob(pat):
            if not p.is_file() or p.name in SCRATCH_PRESERVE:
                continue
            try:
                p.unlink()
                removed.append(p.name)
            except OSError:
                pass
    return removed


def prepare_phase_workdir(model_key: str, phase: int) -> Path:
    """Create the phase workdir, seeded from the prior phase if any."""
    wd = phase_workdir(model_key, phase)
    if wd.exists():
        return wd
    if phase == 1:
        wd.mkdir(parents=True, exist_ok=True)
        return wd
    prior = phase_workdir(model_key, phase - 1)
    if prior.exists():
        shutil.copytree(prior, wd)
        removed = sweep_scratch(wd)
        if removed:
            print(f"  swept {len(removed)} scratch files from new phase {phase:02d} workdir: "
                  f"{', '.join(removed[:8])}{'...' if len(removed) > 8 else ''}", flush=True)
        return wd
    wd.mkdir(parents=True, exist_ok=True)
    return wd


def drop_tests_for_phase(workdir: Path, phase: int) -> None:
    src = SPEC / "tests" / f"phase_{phase:02d}"
    dst = workdir / "tests"
    dst.mkdir(exist_ok=True)
    # Ensure pytest can find tests/__init__.py-free dir.
    for f in src.glob("*.py"):
        shutil.copy(f, dst / f.name)


def read_brief(phase: int) -> str:
    return (SPEC / PHASE_FILES[phase]).read_text()


def read_overall_brief() -> str:
    return (SPEC / "overall_brief.md").read_text()


# ----------------------------------------------------------------------------
# Prompts
# ----------------------------------------------------------------------------

IMPL_SYSTEM = """You are an autonomous coding agent implementing one phase of the
tinylang interpreter benchmark. You have file-system tools (read_file, write_file,
edit_file, list_dir) and a bash tool. Your workdir is a fresh sandbox per phase.

Work efficiently. Read the overall brief and the phase brief once, then implement.
Test your implementation as you go using run_bash (e.g. `python -c "from tinylang.lexer
import tokenize; print(tokenize('let x=1;'))"`). You do not have access to the
acceptance tests during implementation — you must reason about correctness from the
brief alone. When finished, call done(summary).

Output rules:
- Do NOT write planning files, design docs, or commentary files.
- Do NOT write scratch test or debug scripts at the workdir root (e.g.
  debug_*.py, simple_test.py, minimal_test.py, test_*.py at root). They will
  be deleted before the next phase. Experiment via `python -c '...'` in
  run_bash, or write under a `scratch/` subdir. Only files under `tinylang/`
  and (later) `tests/` are graded.
- Do NOT remove, rename, or break functions/classes that prior phases
  exposed via tinylang/__init__.py or that prior-phase tests imported.
  The codebase is cumulative — earlier deliverables must keep working.
- Do NOT print large status messages. Tool calls are sufficient.
- Code only. Stay focused on the current phase's scope.
"""

SELFEVAL_SYSTEM = """You are an autonomous coding agent self-evaluating one phase
of the tinylang interpreter benchmark. The acceptance tests are now in tests/.
Run them with `pytest -q tests/` via run_bash (scope is `tests/` — not the
whole workdir). Fix any failures. Re-run.

If you see "errors during collection" or every test failing with the same
ImportError, fix the import root cause FIRST before touching anything else —
usually a function/class that prior phases exported has been removed or
renamed. Restoring the public surface is higher priority than new features.

Stop when either (a) all tests pass, or (b) you have made your best attempt and
no further progress is possible. Call done(summary) with a short status report
including whether tests pass.

Do not introduce new features outside the phase's scope while fixing failures.
Do not write debug scripts at the workdir root — only `tests/` is graded.
"""

CROSSEVAL_SYSTEM = """You are an autonomous code-reviewer evaluating ANOTHER
model's implementation of one phase of the tinylang interpreter benchmark. You
have read-only access: read_file and list_dir only. You may NOT modify files
or run commands.

Read the phase brief, then explore the implementation. Look at:
- Does the public surface (function names, AST node names, etc.) match the brief?
- Are the edge cases the brief calls out actually handled?
- Code quality, structure, error handling.

When done, call score(accuracy=0-100, completeness=0-100, rationale="3-5 sentences").
Accuracy = how correct/bug-free; would tests pass. Completeness = brief coverage.
"""


def implement_user_prompt(phase: int) -> str:
    return (
        "## Overall brief\n\n"
        f"{read_overall_brief()}\n\n"
        f"## Phase {phase} brief\n\n"
        f"{read_brief(phase)}\n\n"
        f"## Your task\n\nImplement Phase {phase}. Your workdir is the sandbox root. "
        "All paths in tools are relative to it. When complete, call done(summary).\n"
    )


def selfeval_user_prompt(phase: int, label: str = "") -> str:
    base = (
        f"## Phase {phase} brief (for reference)\n\n{read_brief(phase)}\n\n"
        "## Your task\n\n"
        "Run `pytest -q tests/` via run_bash. ONLY `tests/` is graded — do not "
        "write debug scripts at the workdir root (they break collection and "
        "are deleted between phases). Examine failures. Fix what you can "
        "without expanding scope beyond this phase. Re-run until passing or "
        "no further progress.\n"
        "Then call done(summary='X of Y tests pass, ...').\n"
    )
    if label:
        prior = load_prior_baseline(label, phase)
        if prior:
            shown = prior[:200]
            base += (
                f"\n## Regression baseline — {len(prior)} tests passed at end of phase {phase-1}\n\n"
                "These tests must still pass. If any of them now fail, you have "
                "regressed prior-phase code; fixing that takes priority over "
                "new phase-" + str(phase) + " failures. The codebase is cumulative.\n\n"
            )
            for tid in shown:
                base += f"- {tid}\n"
            if len(prior) > len(shown):
                base += f"- ... and {len(prior) - len(shown)} more\n"
    return base


FIX_SYSTEM = """You are an autonomous coding agent FIXING one phase of the tinylang
interpreter benchmark. The acceptance tests are already in tests/ and a prior pass
left some failing. Your sole job is to make more of them pass without expanding scope
beyond this phase.

Run `pytest -q tests/` via run_bash to see the current state. Investigate failures,
fix root causes (prefer minimal targeted edits over rewrites), re-run. Prior-phase
regressions take priority over new failures.

Stop when either (a) all tests pass, or (b) you've made your best attempt this
iteration. Call done(summary) including the final pass/fail counts you observed.

Do not write debug scripts at the workdir root — only `tests/` is graded.
"""


def fix_user_prompt(phase: int, label: str, prior_pytest: dict | None = None,
                   attempt: int = 1) -> str:
    base = (
        f"## Phase {phase} brief (for reference)\n\n{read_brief(phase)}\n\n"
        f"## Iteration {attempt}\n\n"
        "A prior pass already attempted this phase and left tests failing. "
        "Your task is to fix what you can in this iteration. Run pytest, "
        "investigate, edit, re-run.\n"
    )
    if prior_pytest:
        p = prior_pytest.get("passed", 0)
        f_ = prior_pytest.get("failed", 0)
        base += (
            f"\n## Pytest before this iteration: {p} passed, {f_} failed.\n"
        )
    if label:
        prior = load_prior_baseline(label, phase)
        if prior:
            shown = prior[:200]
            base += (
                f"\n## Regression baseline — {len(prior)} tests passed at end of "
                f"phase {phase-1}\n\nThese must still pass. Regressions take "
                "priority over new-phase failures.\n\n"
            )
            for tid in shown:
                base += f"- {tid}\n"
            if len(prior) > len(shown):
                base += f"- ... and {len(prior) - len(shown)} more\n"
    return base


def crosseval_user_prompt(phase: int) -> str:
    return (
        "## Overall brief\n\n"
        f"{read_overall_brief()}\n\n"
        f"## Phase {phase} brief\n\n{read_brief(phase)}\n\n"
        "## Your task\n\n"
        "Review the implementation in your workdir (read-only). Explore via list_dir "
        "and read_file. Then call score(accuracy, completeness, rationale).\n"
    )


def final_eval_user_prompt() -> str:
    parts = ["## Overall brief\n\n", read_overall_brief(), "\n\n## All phase briefs\n\n"]
    for n in range(1, 13):
        parts.append(f"### Phase {n}\n\n{read_brief(n)}\n\n")
    parts.append(
        "## Your task\n\n"
        "Review the full implementation in your workdir (read-only). This is the "
        "state after all 12 phases. Then call score(accuracy, completeness, rationale) "
        "scoring the whole project.\n"
    )
    return "".join(parts)


# ----------------------------------------------------------------------------
# Recording
# ----------------------------------------------------------------------------

def init_timings_csv():
    RESULTS.mkdir(parents=True, exist_ok=True)
    if not TIMINGS_CSV.exists():
        with TIMINGS_CSV.open("w", newline="") as f:
            csv.writer(f).writerow([
                "phase", "model", "stage", "elapsed_s", "steps",
                "input_tokens", "output_tokens", "finish_reason", "test_pass_count", "test_fail_count",
            ])


def append_timing(*, phase, model, stage, elapsed, steps, in_tok, out_tok, finish, passed=None, failed=None):
    init_timings_csv()
    with TIMINGS_CSV.open("a", newline="") as f:
        csv.writer(f).writerow([
            phase, model, stage, f"{elapsed:.2f}", steps, in_tok, out_tok, finish,
            "" if passed is None else passed, "" if failed is None else failed,
        ])


def parse_pytest_output(text: str) -> tuple[int, int]:
    """Best-effort parse of pytest -q summary like '7 passed, 2 failed in 0.3s'."""
    passed = failed = 0
    for line in text.splitlines()[-10:]:
        line_l = line.lower()
        for word, target in (("passed", "p"), ("failed", "f"), ("errors", "f"), ("error", "f")):
            if word in line_l:
                tokens = line_l.replace(",", " ").split()
                for i, t in enumerate(tokens):
                    if t.startswith(word):
                        try:
                            n = int(tokens[i - 1])
                            if target == "p":
                                passed = max(passed, n)
                            else:
                                failed = max(failed, n)
                        except (ValueError, IndexError):
                            pass
    return passed, failed


def _parse_junit_passed(junit_xml: Path) -> list[str]:
    """Return sorted list of test ids ('classname::name' or 'name') that passed."""
    try:
        import xml.etree.ElementTree as ET
        tree = ET.parse(junit_xml)
    except Exception:
        return []
    ids: list[str] = []
    for tc in tree.iter("testcase"):
        if any(tc.find(t) is not None for t in ("failure", "error", "skipped")):
            continue
        cls = tc.attrib.get("classname", "") or ""
        name = tc.attrib.get("name", "") or ""
        ids.append(f"{cls}::{name}" if cls else name)
    return sorted(ids)


def baseline_path(label: str, phase: int) -> Path:
    return RESULTS / "baselines" / label / f"phase_{phase:02d}_passed.json"


def junit_path_for(label: str, phase: int) -> Path:
    return RESULTS / "baselines" / label / f"phase_{phase:02d}_junit.xml"


def load_prior_baseline(label: str, phase: int) -> list[str]:
    """Return the list of test ids that passed at the end of phase-1, or []."""
    if phase <= 1 or not label:
        return []
    p = baseline_path(label, phase - 1)
    if not p.exists():
        return []
    try:
        return list(json.loads(p.read_text()).get("passed_ids") or [])
    except Exception:
        return []


def save_baseline(label: str, phase: int, passed_ids: list[str]) -> None:
    p = baseline_path(label, phase)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"phase": phase, "passed_ids": sorted(passed_ids)}, indent=2))


def run_final_pytest(workdir: Path, junit_path: Path | None = None) -> dict:
    tests_dir = workdir / "tests"
    if not tests_dir.exists():
        return {"returncode": -1, "passed": 0, "failed": 0, "passed_ids": [],
                "error": "no tests/ directory"}
    cmd = [sys.executable, "-m", "pytest", "-q", "tests/", "--tb=short", "--no-header"]
    if junit_path is not None:
        junit_path.parent.mkdir(parents=True, exist_ok=True)
        cmd.append(f"--junitxml={junit_path}")
    try:
        r = subprocess.run(
            cmd,
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=180,
        )
        out = r.stdout
        err = r.stderr
        passed, failed = parse_pytest_output(out + "\n" + err)
        passed_ids = _parse_junit_passed(junit_path) if junit_path else []
        return {"returncode": r.returncode, "passed": passed, "failed": failed,
                "passed_ids": passed_ids,
                "stdout_tail": out[-3000:], "stderr_tail": err[-1000:]}
    except FileNotFoundError:
        return {"returncode": -1, "passed": 0, "failed": 0, "passed_ids": [],
                "error": "pytest not installed"}
    except subprocess.TimeoutExpired:
        return {"returncode": -1, "passed": 0, "failed": 0, "passed_ids": [],
                "error": "pytest timed out"}


# ----------------------------------------------------------------------------
# Orchestration
# ----------------------------------------------------------------------------

def run_phase_for_model(phase: int, model_key: str) -> dict:
    model = MODELS[model_key]
    print(f"\n=== phase {phase}  model {model_key} ({model['display']}) — implement ===", flush=True)
    workdir = prepare_phase_workdir(model_key, phase)

    impl_transcript = TRANSCRIPTS / f"phase_{phase:02d}_{model_key}_implement.json"
    impl = run_tool_loop(
        model_id=model["litellm_id"],
        system_prompt=IMPL_SYSTEM,
        user_prompt=implement_user_prompt(phase),
        workdir=workdir,
        cap=STEP_CAP_IMPLEMENT,
        readonly=False,
        transcript_path=impl_transcript,
        allow_done=True,
    )
    print(f"  implement: {impl.steps} steps, {impl.elapsed_s:.1f}s, finish={impl.finish_reason}")
    append_timing(phase=phase, model=label_for(model_key), stage="implement",
                  elapsed=impl.elapsed_s, steps=impl.steps,
                  in_tok=impl.input_tokens, out_tok=impl.output_tokens,
                  finish=impl.finish_reason)

    # Drop tests for self-eval
    drop_tests_for_phase(workdir, phase)
    print(f"  tests dropped into {workdir}/tests/", flush=True)

    print(f"=== phase {phase}  model {model_key} — self-eval ===", flush=True)
    seval_transcript = TRANSCRIPTS / f"phase_{phase:02d}_{model_key}_selfeval.json"
    label = label_for(model_key)
    seval = run_tool_loop(
        model_id=model["litellm_id"],
        system_prompt=SELFEVAL_SYSTEM,
        user_prompt=selfeval_user_prompt(phase, label=label),
        workdir=workdir,
        cap=STEP_CAP_SELFEVAL,
        readonly=False,
        transcript_path=seval_transcript,
        allow_done=True,
    )
    print(f"  self-eval: {seval.steps} steps, {seval.elapsed_s:.1f}s, finish={seval.finish_reason}")

    final = run_final_pytest(workdir, junit_path=junit_path_for(label, phase))
    print(f"  pytest: {final['passed']} passed, {final['failed']} failed")
    # Persist the set of passing test ids as next-phase's regression baseline.
    save_baseline(label, phase, final.get("passed_ids") or [])
    # Surface regression delta against prior phase, if available.
    prior_passed = set(load_prior_baseline(label, phase))
    now_passed = set(final.get("passed_ids") or [])
    regressed = sorted(prior_passed - now_passed)
    if regressed:
        print(f"  ⚠ regressed {len(regressed)} prior-phase test(s): "
              f"{', '.join(regressed[:5])}{'...' if len(regressed) > 5 else ''}", flush=True)
    append_timing(phase=phase, model=label, stage="self_eval",
                  elapsed=seval.elapsed_s, steps=seval.steps,
                  in_tok=seval.input_tokens, out_tok=seval.output_tokens,
                  finish=seval.finish_reason,
                  passed=final["passed"], failed=final["failed"])

    record = {
        "phase": phase,
        "model": label_for(model_key),
        "workdir": str(workdir),
        "implement": {
            "elapsed_s": impl.elapsed_s, "steps": impl.steps,
            "input_tokens": impl.input_tokens, "output_tokens": impl.output_tokens,
            "finish_reason": impl.finish_reason, "done_payload": impl.done_payload,
            "transcript": str(impl.transcript_path),
        },
        "self_eval": {
            "elapsed_s": seval.elapsed_s, "steps": seval.steps,
            "input_tokens": seval.input_tokens, "output_tokens": seval.output_tokens,
            "finish_reason": seval.finish_reason, "done_payload": seval.done_payload,
            "transcript": str(seval.transcript_path),
        },
        "final_tests": final,
    }
    out = RESULTS / "self_eval" / label_for(model_key) / f"phase_{phase:02d}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=2, default=str))
    return record


def run_fix_for_model(phase: int, model_key: str, attempt: int) -> dict:
    """Re-run a selfeval-style loop on an EXISTING phase workdir.

    Does NOT re-prepare the workdir, does NOT re-drop the tests/. Runs another
    tool loop with a prompt that tells the model the prior pass left tests
    failing and asks it to fix more this iteration. Records timings with stage
    "fix_K" where K is `attempt`. Updates the regression baseline AND the
    self_eval JSON in place.

    Caller (the driver) is responsible for the iterate-while-progress loop
    and for stopping when pass count plateaus.
    """
    model = MODELS[model_key]
    label = label_for(model_key)
    wd = phase_workdir(model_key, phase)
    if not wd.exists():
        raise SystemExit(f"fix: workdir does not exist (run `phase` first): {wd}")

    # Read prior pytest from the most recent self_eval record for this phase.
    prior_pytest = None
    rec_path = RESULTS / "self_eval" / label / f"phase_{phase:02d}.json"
    if rec_path.exists():
        try:
            prior_record = json.loads(rec_path.read_text())
            prior_pytest = prior_record.get("final_tests")
        except Exception:
            prior_record = {}
    else:
        prior_record = {}

    print(f"\n=== phase {phase}  model {model_key} ({model['display']}) — fix attempt {attempt} ===", flush=True)
    transcript = TRANSCRIPTS / f"phase_{phase:02d}_{model_key}_fix_{attempt:02d}.json"
    res = run_tool_loop(
        model_id=model["litellm_id"],
        system_prompt=FIX_SYSTEM,
        user_prompt=fix_user_prompt(phase, label=label, prior_pytest=prior_pytest, attempt=attempt),
        workdir=wd,
        cap=STEP_CAP_SELFEVAL,
        readonly=False,
        transcript_path=transcript,
        allow_done=True,
    )
    print(f"  fix#{attempt}: {res.steps} steps, {res.elapsed_s:.1f}s, finish={res.finish_reason}")

    final = run_final_pytest(wd, junit_path=junit_path_for(label, phase))
    print(f"  pytest after fix#{attempt}: {final['passed']} passed, {final['failed']} failed")
    save_baseline(label, phase, final.get("passed_ids") or [])

    prior_passed = set(load_prior_baseline(label, phase))
    now_passed = set(final.get("passed_ids") or [])
    regressed = sorted(prior_passed - now_passed)
    if regressed:
        print(f"  ⚠ regressed {len(regressed)} prior-phase test(s): "
              f"{', '.join(regressed[:5])}{'...' if len(regressed) > 5 else ''}", flush=True)

    append_timing(phase=phase, model=label, stage=f"fix_{attempt:02d}",
                  elapsed=res.elapsed_s, steps=res.steps,
                  in_tok=res.input_tokens, out_tok=res.output_tokens,
                  finish=res.finish_reason,
                  passed=final["passed"], failed=final["failed"])

    fixes = prior_record.get("fixes") or []
    fixes.append({
        "attempt": attempt,
        "elapsed_s": res.elapsed_s, "steps": res.steps,
        "input_tokens": res.input_tokens, "output_tokens": res.output_tokens,
        "finish_reason": res.finish_reason, "done_payload": res.done_payload,
        "transcript": str(res.transcript_path),
        "pytest": final,
    })
    prior_record["fixes"] = fixes
    prior_record["final_tests"] = final
    rec_path.parent.mkdir(parents=True, exist_ok=True)
    rec_path.write_text(json.dumps(prior_record, indent=2, default=str))
    return {
        "phase": phase, "attempt": attempt,
        "elapsed_s": res.elapsed_s, "steps": res.steps,
        "finish_reason": res.finish_reason, "pytest": final,
    }


def cross_eval_one_direction(reviewer_key: str, target_key: str, phase: int) -> dict:
    reviewer = MODELS[reviewer_key]
    target_wd = phase_workdir(target_key, phase)
    if not target_wd.exists():
        raise SystemExit(f"target workdir does not exist: {target_wd}")
    print(f"\n=== phase {phase}  cross-eval: {reviewer_key} reviewing {target_key} ===", flush=True)
    transcript = TRANSCRIPTS / f"phase_{phase:02d}_{reviewer_key}_on_{target_key}.json"
    res = run_tool_loop(
        model_id=reviewer["litellm_id"],
        system_prompt=CROSSEVAL_SYSTEM,
        user_prompt=crosseval_user_prompt(phase),
        workdir=target_wd,
        cap=STEP_CAP_CROSSEVAL,
        readonly=True,
        transcript_path=transcript,
        allow_done=False,
        allow_score=True,
    )
    print(f"  {res.steps} steps, {res.elapsed_s:.1f}s, finish={res.finish_reason}, score={res.score_payload}")
    append_timing(phase=phase, model=f"{reviewer_key}->{target_key}", stage="cross_eval",
                  elapsed=res.elapsed_s, steps=res.steps,
                  in_tok=res.input_tokens, out_tok=res.output_tokens,
                  finish=res.finish_reason)

    record = {
        "phase": phase,
        "reviewer": reviewer_key,
        "target": target_key,
        "elapsed_s": res.elapsed_s, "steps": res.steps,
        "input_tokens": res.input_tokens, "output_tokens": res.output_tokens,
        "finish_reason": res.finish_reason,
        "score": res.score_payload,
        "transcript": str(res.transcript_path),
    }
    out = RESULTS / "cross_eval" / f"{reviewer_key}_on_{target_key}" / f"phase_{phase:02d}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=2, default=str))
    return record


def cross_eval_phase(phase: int) -> list[dict]:
    return [
        cross_eval_one_direction("A", "B", phase),
        cross_eval_one_direction("B", "A", phase),
    ]


def final_eval_one_direction(reviewer_key: str, target_key: str) -> dict:
    reviewer = MODELS[reviewer_key]
    # Use the final phase's workdir as the snapshot of the whole project.
    target_wd = phase_workdir(target_key, 12)
    if not target_wd.exists():
        # Fall back to highest completed phase
        for p in range(12, 0, -1):
            if phase_workdir(target_key, p).exists():
                target_wd = phase_workdir(target_key, p)
                break
    print(f"\n=== final eval: {reviewer_key} reviewing {target_key} ({target_wd.name}) ===", flush=True)
    transcript = TRANSCRIPTS / f"final_{reviewer_key}_on_{target_key}.json"
    res = run_tool_loop(
        model_id=reviewer["litellm_id"],
        system_prompt=CROSSEVAL_SYSTEM,
        user_prompt=final_eval_user_prompt(),
        workdir=target_wd,
        cap=STEP_CAP_CROSSEVAL * 2,
        readonly=True,
        transcript_path=transcript,
        allow_done=False,
        allow_score=True,
    )
    print(f"  {res.steps} steps, {res.elapsed_s:.1f}s, finish={res.finish_reason}, score={res.score_payload}")
    append_timing(phase=0, model=f"{reviewer_key}->{target_key}", stage="final_eval",
                  elapsed=res.elapsed_s, steps=res.steps,
                  in_tok=res.input_tokens, out_tok=res.output_tokens,
                  finish=res.finish_reason)
    record = {
        "reviewer": reviewer_key,
        "target": target_key,
        "target_workdir": str(target_wd),
        "elapsed_s": res.elapsed_s,
        "steps": res.steps,
        "input_tokens": res.input_tokens,
        "output_tokens": res.output_tokens,
        "finish_reason": res.finish_reason,
        "score": res.score_payload,
        "transcript": str(res.transcript_path),
    }
    out = RESULTS / "cross_eval_final" / f"{reviewer_key}_on_{target_key}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=2, default=str))
    return record


def final_eval_both() -> list[dict]:
    return [
        final_eval_one_direction("A", "B"),
        final_eval_one_direction("B", "A"),
    ]


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------

def smoke_test_models():
    client = make_client()
    for key, m in MODELS.items():
        try:
            resp = client.chat.completions.create(
                model=m["litellm_id"],
                messages=[{"role": "user", "content": 'Reply with the word OK.'}],
                max_tokens=10,
                temperature=0,
            )
            print(f"{key}  {m['litellm_id']:20s}  reply: {resp.choices[0].message.content!r}")
        except Exception as e:
            print(f"{key}  {m['litellm_id']:20s}  ERROR: {type(e).__name__}: {e}")


def main():
    parser = argparse.ArgumentParser()
    # Global overrides applicable to most subcommands.
    parser.add_argument("--litellm-id", help="override MODELS[--model]['litellm_id']")
    parser.add_argument("--max-tokens", type=int, help="override MAX_TOKENS for this run")
    parser.add_argument("--workdir-suffix", default="",
                        help="append to ModelX directory name, e.g. _thinkoff")
    parser.add_argument("--label", default="",
                        help="tag used in timing rows + self_eval result dir, e.g. B_thinkoff")
    parser.add_argument("--extra-body-json", default="",
                        help="JSON merged into every chat completions request, e.g. "
                             "'{\"chat_template_kwargs\":{\"enable_thinking\":false}}'")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("models", help="smoke test both models")

    p_phase = sub.add_parser("phase", help="implement + self-eval one phase")
    p_phase.add_argument("--num", type=int, required=True)
    p_phase.add_argument("--model", choices=["A", "B", "both"], default="both")

    p_fix = sub.add_parser("fix",
        help="re-run selfeval-style on EXISTING phase workdir (no re-implement)")
    p_fix.add_argument("--num", type=int, required=True)
    p_fix.add_argument("--model", choices=["A", "B"], default="B")
    p_fix.add_argument("--attempt", type=int, required=True,
                       help="iteration number K — used in transcript filename + timing stage fix_KK")

    p_cross = sub.add_parser("cross-eval", help="cross-evaluate one phase")
    p_cross.add_argument("--phase", type=int, required=True)

    sub.add_parser("final-eval", help="run final whole-repo cross-eval (both directions)")

    p_runall = sub.add_parser("run-all", help="run phases 1..12 + final")
    p_runall.add_argument("--start", type=int, default=1)
    p_runall.add_argument("--end", type=int, default=12)

    args = parser.parse_args()
    init_timings_csv()

    # Apply CLI overrides
    global MAX_TOKENS, WORKDIR_SUFFIX, LABEL, EXTRA_BODY
    if args.max_tokens:
        MAX_TOKENS = args.max_tokens
    if args.workdir_suffix:
        WORKDIR_SUFFIX = args.workdir_suffix
    if args.label:
        LABEL = args.label
    if args.extra_body_json:
        try:
            EXTRA_BODY = json.loads(args.extra_body_json)
        except json.JSONDecodeError as e:
            sys.exit(f"--extra-body-json: not valid JSON: {e}")
    if args.litellm_id:
        # When provided, applies to the model chosen in `phase --model`.
        # Also update `display` so logs name the model actually being hit (not the
        # static default), since the printed label reads from `display`.
        target = getattr(args, "model", None)
        if target in ("A", "B"):
            MODELS[target] = {**MODELS[target], "litellm_id": args.litellm_id, "display": args.litellm_id}
        else:
            # Without a specific --model, override both (useful in run-all single-model)
            for k in MODELS:
                MODELS[k] = {**MODELS[k], "litellm_id": args.litellm_id, "display": args.litellm_id}

    if args.cmd == "models":
        smoke_test_models()
        return

    if args.cmd == "phase":
        keys = ["A", "B"] if args.model == "both" else [args.model]
        for k in keys:
            run_phase_for_model(args.num, k)
        return

    if args.cmd == "fix":
        run_fix_for_model(args.num, args.model, args.attempt)
        return

    if args.cmd == "cross-eval":
        cross_eval_phase(args.phase)
        return

    if args.cmd == "final-eval":
        final_eval_both()
        return

    if args.cmd == "run-all":
        for n in range(args.start, args.end + 1):
            for k in ["A", "B"]:
                run_phase_for_model(n, k)
            cross_eval_phase(n)
        final_eval_both()
        print("\n--- run-all complete. See benchmark/results/. ---")
        return


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        sys.exit(130)
