import json
import os
import subprocess

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
MAX_STEPS = 15

client = OpenAI(
    api_key=os.environ.get("API_KEY"),
    base_url=DEEPSEEK_BASE_URL,
)

# --- Tool schemas ---

read_file_tool = {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Read and return the full contents of a file at the given path.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file, relative to the project root.",
                },
            },
            "required": ["path"],
        },
    },
}

write_file_tool = {
    "type": "function",
    "function": {
        "name": "write_file",
        "description": "Write content to a file at the given path. Overwrites if it exists.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file, relative to the project root.",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file.",
                },
            },
            "required": ["path", "content"],
        },
    },
}

run_bash_tool = {
    "type": "function",
    "function": {
        "name": "run_bash",
        "description": "Run a bash command and return the output.",
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
}

tools = [read_file_tool, write_file_tool, run_bash_tool]

# --- Tool implementations ---


def read_file(path):
    try:
        with open(path, "r") as f:
            return f.read()
    except Exception as e:
        return f"ERROR: could not read {path}: {e}"


def write_file(path, content):
    try:
        with open(path, "w") as f:
            f.write(content)
        return f"File {path} written successfully."
    except Exception as e:
        return f"ERROR: could not write to {path}: {e}"


def run_bash(command):
    try:
        result = subprocess.run(
            command, capture_output=True, shell=True, text=True, timeout=30
        )
        return f"exitcode: {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
    except subprocess.TimeoutExpired:
        return f"ERROR: command timed out: {command}"


tool_mapping = {
    "read_file": read_file,
    "write_file": write_file,
    "run_bash": run_bash,
}

# --- Agent loop ---


def run_agent():
    messages = [
        {
            "role": "system",
            "content": "You are an AI coding assistant. You will need to fix the bugs in the code.",
        },
        {
            "role": "user",
            "content": (
                "Help me fix playground/buggy.py and ensure the tests in playground/test_buggy.py pass. "
                "Only edit the buggy.py file. Do not edit the test_buggy.py file."
            ),
        },
    ]

    for step in range(MAX_STEPS):
        response = client.chat.completions.create(
            model="deepseek-v4-pro",
            messages=messages,
            tools=tools,
            reasoning_effort="high",
            extra_body={"thinking": {"type": "enabled"}},
        )

        message = response.choices[0].message
        messages.append(message)

        print(f"\n--- Step {step} ---")
        print(f"Reasoning: {message.reasoning_content}")
        print(f"Content:   {message.content}")
        print(f"Tool calls: {message.tool_calls}")

        if message.tool_calls is None:
            break

        for tool_call in message.tool_calls:
            fn = tool_mapping[tool_call.function.name]
            result = fn(**json.loads(tool_call.function.arguments))
            print(f"\nTool [{tool_call.function.name}] result: {result}")
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                }
            )
    else:
        print("ERROR: maximum number of steps exceeded")


if __name__ == "__main__":
    run_agent()
