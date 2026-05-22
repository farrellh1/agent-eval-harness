"""Corpus audit: per-task quality flags.

Most harnesses score the agent; this one also scores the *benchmark*, flagging
tasks whose result cannot be trusted. Three flags, all computed statically from
the task data:

  - broken-tests   the task's test ids are corrupt (see split_malformed_ids)
  - broad          an abnormally large FAIL_TO_PASS set - not a focused bug
  - contaminated   the gold solution's code appears in the problem statement
"""

from __future__ import annotations

import json
import statistics
from dataclasses import asdict, dataclass

from .testspec import split_malformed_ids

# A FAIL_TO_PASS set larger than this is not a focused bug fix; in SWE-bench
# Verified the count is otherwise in the single digits.
BROAD_FAIL_TO_PASS = 10

# Shortest gold-patch line worth checking for a leak into the problem
# statement; below this a match is more likely coincidence than the answer.
MIN_LEAK_LINE = 20


@dataclass
class Flag:
    category: str  # broken-tests | broad | contaminated
    detail: str


@dataclass
class TaskAudit:
    task_id: str
    flags: list[Flag]

    @property
    def clean(self) -> bool:
        return not self.flags

    def to_dict(self) -> dict:
        return asdict(self)


def _check_broken_tests(task: dict) -> Flag | None:
    ids = json.loads(task["FAIL_TO_PASS"]) + json.loads(task["PASS_TO_PASS"])
    _, malformed = split_malformed_ids(ids)
    if not malformed:
        return None
    return Flag(
        "broken-tests",
        f"{len(malformed)} of {len(ids)} test ids are corrupt "
        f"(truncated or progress markers): {malformed}",
    )


def _check_broad(task: dict) -> Flag | None:
    n = len(json.loads(task["FAIL_TO_PASS"]))
    if n <= BROAD_FAIL_TO_PASS:
        return None
    return Flag(
        "broad",
        f"{n} FAIL_TO_PASS tests - a focused bug fix rarely flips this many; "
        "the task is a sweeping change or mis-scoped",
    )


def _patch_added_lines(patch: str) -> list[str]:
    """The substantive code lines a diff adds."""
    lines = []
    for ln in patch.splitlines():
        if ln.startswith("+") and not ln.startswith("+++"):
            code = ln[1:].strip()
            if len(code) >= MIN_LEAK_LINE and any(c.isalpha() for c in code):
                lines.append(code)
    return lines


def _check_contaminated(task: dict) -> Flag | None:
    problem = " ".join(task["problem_statement"].split())
    leaked = [
        line
        for line in _patch_added_lines(task["patch"])
        if " ".join(line.split()) in problem
    ]
    if not leaked:
        return None
    return Flag(
        "contaminated",
        f"the problem statement contains {len(leaked)} line(s) of the gold "
        f"solution, e.g. {leaked[0]!r} - the agent can copy the answer",
    )


_CHECKS = (_check_broken_tests, _check_broad, _check_contaminated)


def audit_task(task: dict) -> TaskAudit:
    """Apply every quality check to one SWE-bench task."""
    flags = []
    for check in _CHECKS:
        flag = check(task)
        if flag:
            flags.append(flag)
    return TaskAudit(task_id=task["instance_id"], flags=flags)


def audit_corpus(tasks: list[dict]) -> list[TaskAudit]:
    return [audit_task(t) for t in tasks]


def _patch_size(patch: str) -> int:
    """Lines a diff changes - added or removed, excluding headers."""
    return sum(
        1
        for ln in patch.splitlines()
        if ln[:1] in "+-" and not ln.startswith(("+++", "---"))
    )


def _spread(values: list[int]) -> dict:
    return {
        "min": min(values),
        "median": round(statistics.median(values)),
        "max": max(values),
    }


def corpus_profile(tasks: list[dict]) -> dict:
    """Descriptive stats for the corpus - context for the flags, not verdicts."""
    return {
        "fail_to_pass": _spread([len(json.loads(t["FAIL_TO_PASS"])) for t in tasks]),
        "pass_to_pass": _spread([len(json.loads(t["PASS_TO_PASS"])) for t in tasks]),
        "gold_patch_lines": _spread([_patch_size(t["patch"]) for t in tasks]),
        "problem_words": _spread([len(t["problem_statement"].split()) for t in tasks]),
    }
