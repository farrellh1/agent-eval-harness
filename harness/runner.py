"""The runner: execute a task and return a scored result record.

Two task types, same shape of result:
  - local toy task -> run_task          (LocalExecutor, held-back tests/)
  - SWE-bench task -> run_swebench_task  (DockerExecutor, held-back test_patch)

Either way: the agent works in isolation, the grading tests are applied only
after it stops, and the result is a plain dict for runs/*.json.
"""

from __future__ import annotations

import json
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from .agent import run_agent
from .executor import DockerExecutor, LocalExecutor
from .scorer import score_swebench, score_task
from .swebench import DOCKER_PLATFORM, TESTBED_ENV_PATH, instance_image
from .testspec import (
    TestRun,
    split_malformed_ids,
    test_files_from_patch,
    test_spec_for,
)

TEST_TIMEOUT = 1800  # seconds; django's largest task runs thousands of tests


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

        # The agent gets workspace/ only. The grading tests live in tests/ and
        # are held back, so the agent cannot see or edit what will score it.
        shutil.copytree(
            task_dir / "workspace",
            workdir,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )

        agent = run_agent(client, model, LocalExecutor(workdir), task["prompt"])

        # The agent has stopped: only now do the grading tests touch the workdir.
        _apply_tests(task_dir / "tests", workdir)

        # {python} lets a task pin scoring to the harness's interpreter.
        test_command = task["test_command"].format(python=sys.executable)
        score = score_task(workdir, test_command)
        diff = _diff(task_dir / "workspace", workdir, task.get("editable_files", []))

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


def _apply_tests(tests_dir: Path, workdir: Path) -> None:
    """Copy the held-back grading tests into the workdir, after the agent stops."""
    for path in sorted(tests_dir.iterdir()):
        if path.is_file():
            shutil.copy2(path, workdir / path.name)


def _diff(original: Path, workdir: Path, files: list[str]) -> str:
    """Unified diff of each editable file: buggy original vs the agent's version."""
    chunks = []
    for name in files:
        before, after = original / name, workdir / name
        if not after.exists():
            continue
        result = subprocess.run(
            [
                "diff",
                "-u",
                "-L",
                f"a/{name}",
                "-L",
                f"b/{name}",
                str(before),
                str(after),
            ],
            capture_output=True,
            text=True,
        )
        if result.stdout:
            chunks.append(result.stdout)
    return "\n".join(chunks)


def run_swebench_task(
    client, model: str, task: dict, cleanup_image: bool = True
) -> dict:
    """Run one SWE-bench task in its Docker container, end to end.

    The agent works in /testbed (the repo at its base commit) with only the
    problem statement. After it stops, the held-back grading tests (test_patch)
    are applied and run - the agent never saw what scores it.

    `cleanup_image` removes the task's (large) Docker image afterwards, unless
    the machine already had it - see DockerExecutor.
    """
    instance_id = task["instance_id"]
    # SWE-bench's dataset truncates some parametrized test ids; quarantine the
    # malformed ones so they neither poison the test run nor skew the score.
    fail_to_pass, ftp_bad = split_malformed_ids(json.loads(task["FAIL_TO_PASS"]))
    pass_to_pass, ptp_bad = split_malformed_ids(json.loads(task["PASS_TO_PASS"]))
    malformed_ids = ftp_bad + ptp_bad
    # How this repo's tests run and get scored - pytest for most, but django
    # and sympy need their own runner (see harness.testspec).
    spec = test_spec_for(task["repo"])
    started = time.time()

    with DockerExecutor(
        instance_image(instance_id),
        workdir="/testbed",
        platform=DOCKER_PLATFORM,
        env_path=TESTBED_ENV_PATH,
        remove_image=cleanup_image,
    ) as ex:
        agent = run_agent(client, model, ex, task["problem_statement"])

        # Capture the agent's patch before the grading tests touch the repo.
        agent_diff = ex.run("git diff")[1]

        # Revert any agent edits to the test files, so the held-back grading
        # tests apply cleanly and the agent cannot influence its own score.
        test_files = test_files_from_patch(task["test_patch"])
        if test_files:
            ex.run("git checkout -- " + " ".join(shlex.quote(f) for f in test_files))

        # Apply the held-back grading tests, then run every graded test at once.
        ex.write_file("/tmp/test_patch.diff", task["test_patch"])
        apply_rc, _, apply_err = ex.run("git apply -v /tmp/test_patch.diff")

        test_run = TestRun(fail_to_pass + pass_to_pass, test_files)
        test_cmd = spec.build_command(test_run)
        _, out, err = ex.run(test_cmd, timeout=TEST_TIMEOUT)

    score = score_swebench(out + err, fail_to_pass, pass_to_pass, parse=spec.parse)

    return {
        "task_id": instance_id,
        "passed": score.resolved,
        "resolved": score.resolved,
        "score": score.score,
        "fail_to_pass": score.fail_to_pass,
        "pass_to_pass_passed": score.pass_to_pass_passed,
        "pass_to_pass_total": score.pass_to_pass_total,
        "steps": agent.steps,
        "completed": agent.completed,
        "prompt_tokens": agent.prompt_tokens,
        "completion_tokens": agent.completion_tokens,
        "duration_s": round(time.time() - started, 1),
        "diff": agent_diff,
        "patch_applied": apply_rc == 0,
        "patch_error": apply_err if apply_rc != 0 else "",
        "malformed_ids": malformed_ids,
        "test_runner": spec.name,
        "score_detail": score.detail,
        "trace": agent.trace.to_list(),
    }
