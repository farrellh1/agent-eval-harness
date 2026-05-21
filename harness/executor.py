"""Executors: where the agent's tools actually run.

The agent loop never changes. Only the Executor changes - the host filesystem
for toy tasks, a Docker container for real SWE-bench tasks. Same agent, same
tools, different environment.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Protocol

COMMAND_TIMEOUT = 30


class Executor(Protocol):
    """A place the agent can read files, write files, and run commands.

    Implementations decide *where* that happens; the agent never knows.
    """

    @property
    def workdir(self) -> str:
        """The working directory, as the agent should be told it."""
        ...

    def read_file(self, path: str) -> str:
        """Return the contents of `path`, relative to the workdir."""
        ...

    def write_file(self, path: str, content: str) -> None:
        """Write `content` to `path`, relative to the workdir."""
        ...

    def run(self, command: str) -> tuple[int, str, str]:
        """Run `command` in the workdir; return (exit_code, stdout, stderr)."""
        ...


class LocalExecutor:
    """Runs the agent's tools against a directory on the host filesystem.

    Used for the toy tasks. Every path is resolved inside `root`, so the agent
    cannot touch anything outside its sandboxed working copy.
    """

    def __init__(self, root: Path):
        self._root = Path(root).resolve()

    @property
    def workdir(self) -> str:
        return str(self._root)

    def _safe_path(self, path: str) -> Path:
        """Resolve `path` inside the root, rejecting anything that escapes it."""
        resolved = (self._root / path).resolve()
        if not resolved.is_relative_to(self._root):
            raise ValueError(f"path escapes workdir: {path}")
        return resolved

    def read_file(self, path: str) -> str:
        return self._safe_path(path).read_text()

    def write_file(self, path: str, content: str) -> None:
        p = self._safe_path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)

    def run(self, command: str) -> tuple[int, str, str]:
        # Put the harness's own interpreter dir first on PATH so `python` and
        # `pytest` resolve to the same environment the harness runs in.
        env = os.environ.copy()
        env["PATH"] = (
            str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
        )
        try:
            result = subprocess.run(
                command,
                cwd=self._root,
                env=env,
                capture_output=True,
                shell=True,
                text=True,
                timeout=COMMAND_TIMEOUT,
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return 124, "", f"command timed out after {COMMAND_TIMEOUT}s: {command}"
