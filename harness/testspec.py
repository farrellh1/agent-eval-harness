"""Per-repo test specs: how to run and score a SWE-bench task's graded tests.

A TestSpec builds the shell command that runs a set of tests and parses that
command's output into a {node id: outcome} map. pytest is the default; django
and sympy run their tests differently and get their own spec.
"""

from __future__ import annotations

import re
import shlex
from collections.abc import Callable
from dataclasses import dataclass

from .scorer import parse_pytest_outcomes


@dataclass
class TestRun:
    """The inputs a TestSpec needs to build its test command."""

    node_ids: list[str]  # FAIL_TO_PASS + PASS_TO_PASS
    test_files: list[str]  # files the task's test_patch touches


@dataclass
class TestSpec:
    """How to run and read one repo's tests."""

    name: str
    build_command: Callable[[TestRun], str]
    parse: Callable[[str], dict[str, str]]  # output -> {node id: outcome}


def _pytest_command(run: TestRun) -> str:
    nodes = " ".join(shlex.quote(n) for n in run.node_ids)
    return f"python -m pytest -rA --tb=no -p no:cacheprovider {nodes}"


PYTEST_SPEC = TestSpec("pytest", _pytest_command, parse_pytest_outcomes)


# A django node id `test_x (a.b.Cls)` is really the test label `a.b.Cls.test_x`.
_DJANGO_NODE = re.compile(r"^(\S+) \(([\w.]+)\)$")


def _django_label(node_id: str) -> str:
    """Turn a django node id into a runtests.py test label."""
    m = _DJANGO_NODE.match(node_id)
    if not m:
        return node_id
    name, dotted_path = m.group(1), m.group(2)
    return f"{dotted_path}.{name}"


def _django_command(run: TestRun) -> str:
    # `--verbosity 2` makes django print one line per test (what the parser
    # reads); `--parallel 1` keeps those lines in order instead of interleaved.
    labels = " ".join(shlex.quote(_django_label(n)) for n in run.node_ids)
    return (
        "python tests/runtests.py --verbosity 2 "
        f"--settings=test_sqlite --parallel 1 {labels}"
    )


# django prints the test id and its `... ok` on one line - but on two when the
# test has a docstring, so the status is tracked against the last id seen.
_DJANGO_TEST_ID = re.compile(r"^(test\S+ \([\w.]+\))")
_DJANGO_STATUS = re.compile(
    r"\.\.\. (ok|FAIL|ERROR|skipped|expected failure|unexpected success)"
)
_DJANGO_OUTCOME = {
    "ok": "PASSED",
    "expected failure": "PASSED",
    "FAIL": "FAILED",
    "ERROR": "ERROR",
    "unexpected success": "FAILED",
    "skipped": "SKIPPED",
}


def parse_django_outcomes(output: str) -> dict[str, str]:
    """Map each django test id to its outcome, from `--verbosity 2` output."""
    outcomes: dict[str, str] = {}
    current: str | None = None
    for line in output.splitlines():
        line = line.strip()
        id_match = _DJANGO_TEST_ID.match(line)
        if id_match:
            current = id_match.group(1)
        status_match = _DJANGO_STATUS.search(line)
        if status_match and current:
            outcomes[current] = _DJANGO_OUTCOME[status_match.group(1)]
            current = None
    return outcomes


DJANGO_SPEC = TestSpec("django", _django_command, parse_django_outcomes)


# sympy node ids are bare function names: run the test_patch's files under
# pytest, then key results by function name (see parse_sympy_outcomes).
def _sympy_command(run: TestRun) -> str:
    files = " ".join(shlex.quote(f) for f in run.test_files)
    # sympy's Docker images ship no pytest (sympy has its own bin/test), so
    # install it into the testbed env before running the tests.
    return (
        "python -m pip install -q pytest && "
        f"python -m pytest -rA --tb=no -p no:cacheprovider {files}"
    )


def parse_sympy_outcomes(output: str) -> dict[str, str]:
    """Parse pytest output, keyed by bare function name (sympy's node id form)."""
    return {
        node.split("::")[-1]: outcome
        for node, outcome in parse_pytest_outcomes(output).items()
    }


SYMPY_SPEC = TestSpec("sympy", _sympy_command, parse_sympy_outcomes)


REPO_SPECS: dict[str, TestSpec] = {
    "django/django": DJANGO_SPEC,
    "sympy/sympy": SYMPY_SPEC,
}


def test_spec_for(repo: str) -> TestSpec:
    """The TestSpec for a repo - pytest unless the repo needs its own runner."""
    return REPO_SPECS.get(repo, PYTEST_SPEC)


_PATCH_FILE = re.compile(r"^\+\+\+ b/(.+)$", re.MULTILINE)


def test_files_from_patch(test_patch: str) -> list[str]:
    """File paths a test_patch adds to or modifies, in order, de-duplicated."""
    seen: dict[str, None] = {}
    for path in _PATCH_FILE.findall(test_patch):
        seen.setdefault(path.strip(), None)
    return list(seen)


# SWE-bench's dataset corrupts some test ids: parametrized ids get truncated on
# whitespace (`test_x[w/ space]` -> `test_x[w/`), and progress markers like
# `[100%]` are captured as ids. pytest aborts the whole run when handed one.
def split_malformed_ids(node_ids: list[str]) -> tuple[list[str], list[str]]:
    """Split node ids into (valid, malformed).

    Malformed = unbalanced square brackets (a truncated id) or a leading `[`
    (a progress marker); no real node id of any runner looks like either.
    """
    valid: list[str] = []
    malformed: list[str] = []
    for nid in node_ids:
        bad = nid.startswith("[") or nid.count("[") != nid.count("]")
        (malformed if bad else valid).append(nid)
    return valid, malformed
