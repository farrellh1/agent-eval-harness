"""Corpus audit: per-task quality flags.

This is the differentiated value of the project. Most harnesses score the
agent; this one also scores the *benchmark* — flagging tasks that are
contaminated, have weak hidden tests, or fail to discriminate good agents
from bad. A benchmark is only as honest as its weakest task.

Not yet implemented. Populated during the SWE-bench Verified audit pass; see
the roadmap in README.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Flag vocabulary the audit pass will assign.
KNOWN_FLAGS = ("contaminated", "weak-tests", "trivial", "ambiguous", "env-drift")


@dataclass
class TaskAudit:
    task_id: str
    flags: list[str] = field(default_factory=list)
    notes: str = ""


def audit_task(task: dict) -> TaskAudit:
    """Placeholder. The real audit applies the benchmark-integrity lens to each
    SWE-bench task. For now every task comes back unflagged."""
    return TaskAudit(task_id=task["id"])
