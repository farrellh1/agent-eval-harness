"""Per-repo test specs: how to run and score a SWE-bench task's graded tests.

Most SWE-bench repos run their tests with pytest, so pytest is the default.
Two repos in SWE-bench Verified are different and need their own spec:

  - django  - has its own runner (tests/runtests.py); its test node ids look
              like `test_name (dotted.module.Class)`, not pytest paths.
  - sympy   - its node ids are bare function names with no file path at all.

A TestSpec knows two things: how to build the shell command that runs a set of
graded tests, and how to parse that command's output back into a per-test
outcome map. The runner picks a spec by repo and stays otherwise unchanged -
swap the spec, never the runner.
"""

from __future__ import annotations

import re
import shlex
from collections.abc import Callable
from dataclasses import dataclass

from .scorer import parse_pytest_outcomes


@dataclass
class TestRun:
    """The inputs a TestSpec needs to build its test command.

    Both fields are always passed; a spec uses whichever it needs (pytest keys
    off node ids, sympy off the test files), so they travel together.
    """

    node_ids: list[str]  # graded test node ids (FAIL_TO_PASS + PASS_TO_PASS)
    test_files: list[str]  # files the task's test_patch touches


@dataclass
class TestSpec:
    """How to run and read one repo's tests."""

    name: str
    # a TestRun -> the shell command that runs its graded tests.
    build_command: Callable[[TestRun], str]
    # raw command output -> {node id: outcome}; the outcome "PASSED" means pass.
    parse: Callable[[str], dict[str, str]]


# --- pytest: the default for every SWE-bench Verified repo but django/sympy.


def _pytest_command(run: TestRun) -> str:
    nodes = " ".join(shlex.quote(n) for n in run.node_ids)
    return f"python -m pytest -rA --tb=no -p no:cacheprovider {nodes}"


PYTEST_SPEC = TestSpec("pytest", _pytest_command, parse_pytest_outcomes)


# --- django: its own runner. A node id `test_x (a.b.Cls)` is really the test
# label `a.b.Cls.test_x` split into method name and dotted path.

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


# django prints `test_x (a.b.Cls)` then `... ok` - usually on one line, but
# split across two when the test has a docstring. So: remember the most recent
# test id, then attach the next status line that appears to it.
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


# --- sympy: node ids are bare function names. Run the test files the test_patch
# touches under pytest, then key the results by function name so they match.


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


# --- helper: the test files a SWE-bench test_patch touches.

_PATCH_FILE = re.compile(r"^\+\+\+ b/(.+)$", re.MULTILINE)


def test_files_from_patch(test_patch: str) -> list[str]:
    """File paths a test_patch adds to or modifies, in order, de-duplicated."""
    seen: dict[str, None] = {}
    for path in _PATCH_FILE.findall(test_patch):
        seen.setdefault(path.strip(), None)
    return list(seen)


# --- helper: quarantine node ids that SWE-bench's own data pipeline corrupted.
# Two kinds seen: parametrized ids truncated on whitespace (`test_x[w/ space]`
# becomes the fragment `test_x[w/`, brackets no longer balanced), and pytest
# progress markers like `[100%]` captured as if they were test ids. Either
# matches no test and makes pytest abort the *entire* run, so both are filtered
# out (and recorded).


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
