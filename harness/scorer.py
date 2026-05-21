"""Scoring: did the agent fix the bug, and how cleanly?

Scoring an agent is not `assertEqual`. The output is a mutated repository, so
we score by running the task's test command and reading the result. The score
is partial-credit (fraction of tests passing), not a bare pass/fail, so a
near-miss is distinguishable from a total failure.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class Score:
    passed: bool  # all tests green
    tests_passed: int
    tests_failed: int
    score: float  # tests_passed / total — the partial-credit number
    detail: str  # tail of the test output, for diagnosis

    def to_dict(self) -> dict:
        return asdict(self)


def score_task(workdir: Path, test_command: str) -> Score:
    """Run `test_command` in `workdir` and turn its output into a Score."""
    result = subprocess.run(
        test_command,
        cwd=workdir,
        capture_output=True,
        shell=True,
        text=True,
        timeout=120,
    )
    output = result.stdout + result.stderr

    passed_n = _count(output, r"(\d+) passed")
    failed_n = _count(output, r"(\d+) failed") + _count(output, r"(\d+) error")
    total = passed_n + failed_n
    score = passed_n / total if total else 0.0

    return Score(
        passed=(result.returncode == 0 and failed_n == 0 and passed_n > 0),
        tests_passed=passed_n,
        tests_failed=failed_n,
        score=round(score, 3),
        detail=output[-1000:],
    )


def _count(text: str, pattern: str) -> int:
    match = re.search(pattern, text)
    return int(match.group(1)) if match else 0
