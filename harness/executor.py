"""Executors: where the agent's tools actually run.

The agent loop never changes. Only the Executor changes - the host filesystem
for toy tasks, a Docker container for real SWE-bench tasks. Same agent, same
tools, different environment.
"""

from __future__ import annotations

import os
import shlex
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

    def run(self, command: str, timeout: int = COMMAND_TIMEOUT) -> tuple[int, str, str]:
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

    def run(self, command: str, timeout: int = COMMAND_TIMEOUT) -> tuple[int, str, str]:
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
                timeout=timeout,
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return 124, "", f"command timed out after {timeout}s: {command}"


class DockerExecutor:
    """Runs the agent's tools inside a Docker container.

    Used for real SWE-bench tasks, whose repo and dependencies live in a
    prebuilt per-task image. Use it as a context manager: the container is
    started on enter and force-removed on exit.
    """

    def __init__(
        self,
        image: str,
        workdir: str = "/testbed",
        platform: str = "linux/amd64",
        env_path: str | None = None,
        remove_image: bool = False,
    ):
        self.image = image
        self._workdir = workdir
        self.platform = platform
        # Dir to prepend to PATH for every command, e.g. a conda env's bin.
        # SWE-bench images install deps into a `testbed` env, not base.
        self.env_path = env_path
        # If set, remove the image on exit - but only when this run pulled it
        # (see __enter__). SWE-bench images are large; a long run would
        # otherwise fill the disk.
        self.remove_image = remove_image
        self.container: str | None = None
        self._pulled_image = False

    @property
    def workdir(self) -> str:
        return self._workdir

    def __enter__(self) -> "DockerExecutor":
        """Start a detached container, kept alive by `sleep infinity`."""
        # Note whether the image is already local. `docker run` pulls it if
        # not; cleanup on exit then removes only what this run brought in.
        inspect = subprocess.run(
            ["docker", "image", "inspect", self.image],
            capture_output=True,
            text=True,
        )
        self._pulled_image = inspect.returncode != 0
        result = subprocess.run(
            [
                "docker",
                "run",
                "-d",
                "--platform",
                self.platform,
                "--entrypoint",
                "sleep",
                self.image,
                "infinity",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        self.container = result.stdout.strip()
        return self

    def __exit__(self, *_) -> None:
        if self.container:
            subprocess.run(
                ["docker", "rm", "-f", self.container],
                capture_output=True,
                text=True,
            )
            self.container = None
        # Remove the image only if cleanup is on and this run pulled it -
        # never delete an image the machine already had.
        if self.remove_image and self._pulled_image:
            subprocess.run(
                ["docker", "rmi", self.image],
                capture_output=True,
                text=True,
            )

    def read_file(self, path: str) -> str:
        result = subprocess.run(
            ["docker", "exec", "-w", self._workdir, self.container, "cat", path],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise FileNotFoundError(result.stderr.strip() or path)
        return result.stdout

    def write_file(self, path: str, content: str) -> None:
        parent = os.path.dirname(path)
        if parent:
            subprocess.run(
                [
                    "docker",
                    "exec",
                    "-w",
                    self._workdir,
                    self.container,
                    "mkdir",
                    "-p",
                    parent,
                ],
                capture_output=True,
                text=True,
            )
        # Stream the content in over stdin, so no quoting of `content` is needed.
        result = subprocess.run(
            [
                "docker",
                "exec",
                "-i",
                "-w",
                self._workdir,
                self.container,
                "sh",
                "-c",
                f"cat > {shlex.quote(path)}",
            ],
            input=content,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise OSError(result.stderr.strip() or path)

    def run(self, command: str, timeout: int = COMMAND_TIMEOUT) -> tuple[int, str, str]:
        # Prepend the task's environment (e.g. a conda env) to PATH if set.
        if self.env_path:
            command = f'export PATH="{self.env_path}:$PATH"\n{command}'
        try:
            result = subprocess.run(
                [
                    "docker",
                    "exec",
                    "-w",
                    self._workdir,
                    self.container,
                    "bash",
                    "-c",
                    command,
                ],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return 124, "", f"command timed out after {timeout}s: {command}"
