"""Tools the agent can call: read_file, write_file, run_bash.

Every path is resolved against a sandbox `workdir` so the agent cannot read
or write outside the task's working copy. This is what makes a run isolated:
the agent mutates a throwaway copy, never the canonical task.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


class Toolbox:
    """The three agent tools, all scoped to one workdir."""

    def __init__(self, workdir: Path):
        self.workdir = Path(workdir).resolve()

    def _safe_path(self, path: str) -> Path:
        """Resolve `path` inside the workdir, rejecting anything that escapes it."""
        resolved = (self.workdir / path).resolve()
        if not resolved.is_relative_to(self.workdir):
            raise ValueError(f"path escapes workdir: {path}")
        return resolved

    def read_file(self, path: str) -> str:
        try:
            return self._safe_path(path).read_text()
        except Exception as e:
            return f"ERROR: could not read {path}: {e}"

    def write_file(self, path: str, content: str) -> str:
        try:
            p = self._safe_path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
            return f"File {path} written successfully."
        except Exception as e:
            return f"ERROR: could not write {path}: {e}"

    def run_bash(self, command: str) -> str:
        # Put the harness's own interpreter dir first on PATH so `python` and
        # `pytest` resolve to the same environment the harness runs in.
        env = os.environ.copy()
        env["PATH"] = (
            str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
        )
        try:
            result = subprocess.run(
                command,
                cwd=self.workdir,
                env=env,
                capture_output=True,
                shell=True,
                text=True,
                timeout=30,
            )
            return (
                f"exitcode: {result.returncode}\n"
                f"stdout: {result.stdout}\n"
                f"stderr: {result.stderr}"
            )
        except subprocess.TimeoutExpired:
            return f"ERROR: command timed out: {command}"


# OpenAI-format tool schemas advertised to the model.
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read and return the full contents of a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path relative to the project root.",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file, overwriting if it exists.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path relative to the project root.",
                    },
                    "content": {"type": "string", "description": "Content to write."},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_bash",
            "description": "Run a bash command in the project root and return its output.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The bash command to run.",
                    },
                },
                "required": ["command"],
            },
        },
    },
]
