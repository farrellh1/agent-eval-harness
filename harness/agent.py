"""The coding agent: a think -> call tool -> observe loop.

This is the *system under test*. The harness measures it; it is deliberately
simple so that what we are measuring stays legible. Anything clever belongs in
the harness, not here.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .tools import TOOL_SCHEMAS, Toolbox
from .trace import Trace

MAX_STEPS = 15


def build_system_prompt(workdir: Path) -> str:
    """Build the system prompt for a run, anchored to the real working directory.

    Telling the agent its actual path stops it guessing conventional paths like
    /repo or /home/user and wasting steps when the guess is wrong.
    """
    return (
        "You are an AI coding assistant working inside a code repository that "
        "contains a bug. Investigate the code, find the bug, and fix it.\n\n"
        f"Your working directory is: {workdir}\n"
        "All three tools (read_file, write_file, run_bash) already run from "
        "that directory. Use plain relative paths; do not prefix shell commands "
        "with cd. Fix the bug by editing source files only; do not create or "
        "edit test files."
    )


@dataclass
class AgentResult:
    completed: bool  # ended on its own (True) vs hit the step cap (False)
    steps: int
    prompt_tokens: int
    completion_tokens: int
    trace: Trace


def run_agent(
    client, model: str, workdir: Path, task_prompt: str, max_steps: int = MAX_STEPS
) -> AgentResult:
    """Run the agent loop in `workdir` until it stops or hits `max_steps`."""
    tools = Toolbox(Path(workdir))
    tool_mapping = {
        "read_file": tools.read_file,
        "write_file": tools.write_file,
        "run_bash": tools.run_bash,
    }
    trace = Trace()
    messages = [
        {"role": "system", "content": build_system_prompt(Path(workdir))},
        {"role": "user", "content": task_prompt},
    ]
    prompt_tokens = completion_tokens = 0

    for step in range(max_steps):
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=TOOL_SCHEMAS,
            reasoning_effort="high",  # DeepSeek-specific reasoning controls
            extra_body={"thinking": {"type": "enabled"}},
        )
        if response.usage:
            prompt_tokens += response.usage.prompt_tokens
            completion_tokens += response.usage.completion_tokens

        message = response.choices[0].message
        messages.append(message)

        reasoning = getattr(message, "reasoning_content", None)
        if reasoning:
            trace.add(step, "reasoning", content=reasoning)
        if message.content:
            trace.add(step, "reasoning", content=message.content)

        # No tool calls means the agent considers itself done.
        if not message.tool_calls:
            return AgentResult(True, step + 1, prompt_tokens, completion_tokens, trace)

        for tool_call in message.tool_calls:
            name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)
            trace.add(step, "tool_call", name=name, content=json.dumps(args))

            result = tool_mapping[name](**args)
            trace.add(step, "tool_result", name=name, content=result)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                }
            )

    return AgentResult(False, max_steps, prompt_tokens, completion_tokens, trace)
