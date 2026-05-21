"""Structured trace of an agent run: every reasoning step and tool call.

The trace is the diagnostic backbone of the harness. The Phase 2 dashboard
renders it directly (the "trace view"), so every event must be JSON-friendly
and the shape must stay stable.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field


@dataclass
class TraceEvent:
    step: int
    kind: str  # "reasoning" | "tool_call" | "tool_result"
    name: str = ""  # tool name, for tool_call / tool_result events
    content: str = ""  # reasoning text, JSON-encoded args, or tool output
    timestamp: float = field(default_factory=time.time)


@dataclass
class Trace:
    events: list[TraceEvent] = field(default_factory=list)

    def add(self, step: int, kind: str, name: str = "", content: str = "") -> None:
        self.events.append(TraceEvent(step, kind, name, content))

    def to_list(self) -> list[dict]:
        """Serialize for writing into a run's JSON file."""
        return [asdict(e) for e in self.events]
