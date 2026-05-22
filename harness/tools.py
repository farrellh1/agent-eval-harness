"""The agent's four tools: read_file, write_file, edit_file, run_bash.

Toolbox shapes tool results into the strings the model sees. *Where* a tool
runs - host filesystem or Docker container - is the Executor's job, not this
file's. The agent only ever sees a Toolbox.
"""

from __future__ import annotations

from .executor import Executor


class Toolbox:
    """The four agent tools, backed by a swappable Executor."""

    def __init__(self, executor: Executor):
        self.executor = executor

    def read_file(self, path: str) -> str:
        try:
            return self.executor.read_file(path)
        except Exception as e:
            return f"ERROR: could not read {path}: {e}"

    def write_file(self, path: str, content: str) -> str:
        try:
            self.executor.write_file(path, content)
            return f"File {path} written successfully."
        except Exception as e:
            return f"ERROR: could not write {path}: {e}"

    def edit_file(self, path: str, old_string: str, new_string: str) -> str:
        # old_string must match exactly one place: a unique match means the
        # agent had to read enough context to know what it is changing.
        if old_string == new_string:
            return "ERROR: old_string and new_string are identical."
        try:
            content = self.executor.read_file(path)
        except Exception as e:
            return f"ERROR: could not read {path}: {e}"
        occurrences = content.count(old_string)
        if occurrences == 0:
            return f"ERROR: old_string not found in {path}."
        if occurrences > 1:
            return (
                f"ERROR: old_string appears {occurrences} times in {path}; "
                "add surrounding context so it matches exactly one place."
            )
        try:
            self.executor.write_file(path, content.replace(old_string, new_string))
        except Exception as e:
            return f"ERROR: could not write {path}: {e}"
        return f"File {path} edited successfully."

    def run_bash(self, command: str) -> str:
        exit_code, stdout, stderr = self.executor.run(command)
        return f"exitcode: {exit_code}\nstdout: {stdout}\nstderr: {stderr}"


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
            "name": "edit_file",
            "description": (
                "Replace one exact, unique occurrence of old_string with "
                "new_string in a file. Prefer it over write_file when "
                "changing an existing file."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path relative to the project root.",
                    },
                    "old_string": {
                        "type": "string",
                        "description": (
                            "Exact text to find. Must match exactly one "
                            "place; add surrounding lines to make it unique."
                        ),
                    },
                    "new_string": {
                        "type": "string",
                        "description": "The replacement text.",
                    },
                },
                "required": ["path", "old_string", "new_string"],
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
