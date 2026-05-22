"""Scoring: did the agent fix the bug, and how cleanly?

Scoring an agent is not `assertEqual`. The output is a mutated repository, so
we score by running the task's test command and reading the result. The score
is partial-credit (fraction of tests passing), not a bare pass/fail, so a
near-miss is distinguishable from a total failure.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Callable
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


@dataclass
class SweScore:
    """SWE-bench result: did the target tests pass without regressions?"""

    resolved: bool  # all FAIL_TO_PASS green AND all PASS_TO_PASS still green
    fail_to_pass: dict[str, bool]  # target test id -> passed
    pass_to_pass_passed: int
    pass_to_pass_total: int
    score: float  # fraction of all graded tests passing (partial credit)
    detail: str

    def to_dict(self) -> dict:
        return asdict(self)


# Some repos force coloured test output, wrapping each line in ANSI escape
# codes. Strip them before any line-anchored parsing, or a `^PASSED` regex
# never matches a coloured "\x1b[32mPASSED".
_ANSI = re.compile(r"\x1b\[[0-9;]*m")

# pytest's `-rA` summary prints one line per test: "PASSED path::test_name".
_OUTCOME_LINE = re.compile(r"^(PASSED|FAILED|ERROR|SKIPPED)\s+(\S+)", re.MULTILINE)


def parse_pytest_outcomes(output: str) -> dict[str, str]:
    """Map each test node id to its outcome, from pytest `-rA` output."""
    return {m.group(2): m.group(1) for m in _OUTCOME_LINE.finditer(output)}


def score_swebench(
    output: str,
    fail_to_pass: list[str],
    pass_to_pass: list[str],
    parse: Callable[[str], dict[str, str]] = parse_pytest_outcomes,
) -> SweScore:
    """Grade a SWE-bench run the way SWE-bench does: every FAIL_TO_PASS test
    must now pass, and every PASS_TO_PASS test must still pass.

    `parse` turns raw test output into a {node id: outcome} map. It defaults to
    pytest's format; a repo with its own runner passes its own parser instead
    (see harness.testspec)."""
    output = _ANSI.sub("", output)
    outcomes = parse(output)

    ftp = {t: outcomes.get(t) == "PASSED" for t in fail_to_pass}
    ptp_passed = sum(outcomes.get(t) == "PASSED" for t in pass_to_pass)

    resolved = all(ftp.values()) and ptp_passed == len(pass_to_pass)
    graded = len(fail_to_pass) + len(pass_to_pass)
    passed = sum(ftp.values()) + ptp_passed
    score = passed / graded if graded else 0.0

    return SweScore(
        resolved=resolved,
        fail_to_pass=ftp,
        pass_to_pass_passed=ptp_passed,
        pass_to_pass_total=len(pass_to_pass),
        score=round(score, 3),
        detail=output[-2000:],
    )
