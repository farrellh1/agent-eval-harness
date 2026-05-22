"""SWE-bench task support: map a corpus row to a runnable task.

Each SWE-bench task is a real GitHub issue. We do not build its environment -
SWE-bench publishes a prebuilt Docker image per task, with the repo checked
out at the base commit and every dependency installed.
"""

from __future__ import annotations

import json
from pathlib import Path

# SWE-bench images install task dependencies into this conda env, not base.
TESTBED_ENV_PATH = "/opt/miniconda3/envs/testbed/bin"

# SWE-bench publishes an x86_64 image for every instance but arm64 for only
# some, so always use x86_64 - on Apple Silicon it runs under emulation.
IMAGE_ARCH = "x86_64"
DOCKER_PLATFORM = "linux/amd64"


def instance_image(instance_id: str) -> str:
    """The published SWE-bench image for a task.

    SWE-bench tags one image per instance, rewriting `__` to `_1776_` (its
    org/repo separator), e.g.
        pallets__flask-5014 -> swebench/sweb.eval.x86_64.pallets_1776_flask-5014
    """
    tag = instance_id.replace("__", "_1776_")
    return f"swebench/sweb.eval.{IMAGE_ARCH}.{tag}"


def load_swebench_tasks(path: Path) -> list[dict]:
    """Load SWE-bench task records from a .jsonl corpus file."""
    with Path(path).open() as f:
        return [json.loads(line) for line in f if line.strip()]
