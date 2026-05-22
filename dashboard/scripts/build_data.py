"""Build dashboard/public/data.json for the agent-eval-harness Phase 2 dashboard.

Joins three sources into one static JSON file:
  1. corpus/swe_bench_verified_subset.jsonl  -- the 25 SWE-bench tasks
  2. runs/run-20260522-172308.json           -- the 25-task agent run
  3. corpus/audit.json                       -- benchmark-quality audit flags

Run this from the repository root:

    python dashboard/scripts/build_data.py

It writes dashboard/public/data.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# --- locate the repo root (this file lives at dashboard/scripts/build_data.py)
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DASHBOARD_DIR = SCRIPT_DIR.parent

# Make `harness` importable so we can ask it for the real system prompt.
sys.path.insert(0, str(REPO_ROOT))
from harness.agent import build_system_prompt  # noqa: E402

CORPUS_JSONL = REPO_ROOT / "corpus" / "swe_bench_verified_subset.jsonl"
RUN_JSON = REPO_ROOT / "runs" / "run-20260522-172308.json"
AUDIT_JSON = REPO_ROOT / "corpus" / "audit.json"
OUT_PATH = DASHBOARD_DIR / "public" / "data.json"

# Trace event content longer than this is truncated so data.json stays small.
MAX_CONTENT = 4000


def truncate(text: str, limit: int = MAX_CONTENT) -> str:
    """Truncate long strings, appending a short note about how much was cut."""
    if not isinstance(text, str):
        return text
    if len(text) <= limit:
        return text
    cut = len(text) - limit
    return text[:limit] + f"\n\n... [truncated {cut:,} characters]"


def load_corpus() -> dict[str, dict]:
    """Load the SWE-bench subset, keyed by instance_id."""
    tasks: dict[str, dict] = {}
    with CORPUS_JSONL.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            tasks[obj["instance_id"]] = obj
    return tasks


def load_audits() -> dict[str, list]:
    """Load the audit file, returning flags keyed by task_id."""
    audit = json.loads(AUDIT_JSON.read_text())
    flags = {a["task_id"]: a.get("flags", []) for a in audit.get("audits", [])}
    return audit, flags


def parse_id_list(raw) -> list[str]:
    """FAIL_TO_PASS / PASS_TO_PASS are JSON-encoded string lists."""
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return []
    return []


def main() -> None:
    corpus = load_corpus()
    audit, audit_flags = load_audits()
    run = json.loads(RUN_JSON.read_text())

    system_prompt = build_system_prompt("/testbed")

    tasks_out: list[dict] = []
    score_sum = 0.0

    for result in run["results"]:
        task_id = result["task_id"]
        task = corpus.get(task_id, {})

        fail_to_pass_ids = parse_id_list(task.get("FAIL_TO_PASS"))
        pass_to_pass_ids = parse_id_list(task.get("PASS_TO_PASS"))

        # fail_to_pass on the result is a dict id -> bool
        ftp_result = result.get("fail_to_pass", {}) or {}
        ftp_passed = sum(1 for v in ftp_result.values() if v)
        ftp_total = len(ftp_result) if ftp_result else len(fail_to_pass_ids)

        trace = []
        for event in result.get("trace", []):
            trace.append(
                {
                    "step": event.get("step"),
                    "kind": event.get("kind"),
                    "name": event.get("name", ""),
                    "content": truncate(event.get("content", "")),
                    "timestamp": event.get("timestamp"),
                }
            )

        score = result.get("score", 0.0) or 0.0
        score_sum += score

        tasks_out.append(
            {
                "instance_id": task_id,
                "repo": task.get("repo", ""),
                "version": task.get("version", ""),
                "difficulty": task.get("difficulty", ""),
                "resolved": bool(result.get("resolved")),
                "score": score,
                "fail_to_pass_passed": ftp_passed,
                "fail_to_pass_total": ftp_total,
                "pass_to_pass_passed": result.get("pass_to_pass_passed", 0),
                "pass_to_pass_total": result.get("pass_to_pass_total", 0),
                "problem_statement": task.get("problem_statement", ""),
                "gold_patch": task.get("patch", ""),
                "test_patch": task.get("test_patch", ""),
                "agent_diff": result.get("diff", ""),
                "patch_applied": bool(result.get("patch_applied")),
                "patch_error": result.get("patch_error", ""),
                "malformed_ids": result.get("malformed_ids", []),
                "test_runner": result.get("test_runner", ""),
                "steps": result.get("steps", 0),
                "completed": bool(result.get("completed")),
                "prompt_tokens": result.get("prompt_tokens", 0),
                "completion_tokens": result.get("completion_tokens", 0),
                "duration_s": result.get("duration_s", 0),
                "trace": trace,
                "audit_flags": audit_flags.get(task_id, []),
            }
        )

    n = len(tasks_out)
    mean_score = round(score_sum / n, 4) if n else 0.0
    flagged = sum(1 for t in tasks_out if t["audit_flags"])

    data = {
        "run": {
            "run_id": run.get("run_id", ""),
            "model": run.get("model", ""),
            "created_at": run.get("created_at", ""),
            "tasks_total": run.get("tasks_total", n),
            "tasks_passed": run.get("tasks_passed", 0),
            "tasks_flagged": flagged,
            "mean_score": mean_score,
            "system_prompt": system_prompt,
        },
        "audit_profile": audit.get("profile", {}),
        "tasks": tasks_out,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(data, indent=2))
    print(f"Wrote {OUT_PATH} ({OUT_PATH.stat().st_size:,} bytes)")
    print(f"  tasks: {n}  resolved: {data['run']['tasks_passed']}  "
          f"flagged: {flagged}  mean score: {mean_score}")


if __name__ == "__main__":
    main()
