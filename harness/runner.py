"""The runner: turn a task directory into a scored result.

Pipeline, per task:
  1. copy the task into an isolated temp workdir (agent cannot corrupt the original)
  2. run the agent in that workdir
  3. score it by running the task's test command
  4. capture the agent's diff against the original buggy code

Returns a plain dict — the per-task record that goes into runs/*.json.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from .agent import run_agent
from .scorer import score_task


def load_task(task_dir: Path) -> dict:
    """Read a task's manifest. Each task dir holds a task.json plus its files."""
    task = json.loads((task_dir / "task.json").read_text())
    task["_dir"] = task_dir
    return task


def run_task(client, model: str, task: dict) -> dict:
    """Run one task end to end and return its result record."""
    task_dir: Path = task["_dir"]
    started = time.time()

    with tempfile.TemporaryDirectory(prefix="evalrun-") as tmp:
        workdir = Path(tmp) / task["id"]
        shutil.copytree(
            task_dir,
            workdir,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "task.json"),
        )

        agent = run_agent(client, model, workdir, task["prompt"])

        # {python} lets a task pin scoring to the harness's interpreter.
        test_command = task["test_command"].format(python=sys.executable)
        score = score_task(workdir, test_command)
        diff = _diff(task_dir, workdir, task.get("editable_files", []))

    return {
        "task_id": task["id"],
        "passed": score.passed,
        "score": score.score,
        "tests_passed": score.tests_passed,
        "tests_failed": score.tests_failed,
        "steps": agent.steps,
        "completed": agent.completed,
        "prompt_tokens": agent.prompt_tokens,
        "completion_tokens": agent.completion_tokens,
        "duration_s": round(time.time() - started, 1),
        "diff": diff,
        "score_detail": score.detail,
        "trace": agent.trace.to_list(),
    }


def _diff(original: Path, workdir: Path, files: list[str]) -> str:
    """Unified diff of each editable file: buggy original vs the agent's version."""
    chunks = []
    for name in files:
        before, after = original / name, workdir / name
        if not after.exists():
            continue
        result = subprocess.run(
            ["diff", "-u", "-L", f"a/{name}", "-L", f"b/{name}",
             str(before), str(after)],
            capture_output=True,
            text=True,
        )
        if result.stdout:
            chunks.append(result.stdout)
    return "\n".join(chunks)
