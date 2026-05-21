"""SWE-bench task support: map a corpus row to a runnable task.

Each SWE-bench task is a real GitHub issue. We do not build its environment -
SWE-bench publishes a prebuilt Docker image per task, with the repo checked
out at the base commit and every dependency installed.
"""

from __future__ import annotations

import json
import platform
from pathlib import Path


def host_arch() -> str:
    """SWE-bench's architecture token for this machine."""
    return "arm64" if platform.machine() in ("arm64", "aarch64") else "x86_64"


def docker_platform() -> str:
    """The Docker --platform value matching the host architecture."""
    return "linux/arm64" if host_arch() == "arm64" else "linux/amd64"


def instance_image(instance_id: str, arch: str | None = None) -> str:
    """The published SWE-bench image for a task.

    SWE-bench tags one image per instance, rewriting `__` to `_1776_` (its
    org/repo separator), e.g.
        pallets__flask-5014 -> swebench/sweb.eval.arm64.pallets_1776_flask-5014
    """
    arch = arch or host_arch()
    tag = instance_id.replace("__", "_1776_")
    return f"swebench/sweb.eval.{arch}.{tag}"


def load_swebench_tasks(path: Path) -> list[dict]:
    """Load SWE-bench task records from a .jsonl corpus file."""
    with Path(path).open() as f:
        return [json.loads(line) for line in f if line.strip()]
