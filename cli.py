"""CLI entry point for the agent eval harness.

Usage:
    python cli.py run                  # run every task in tasks/
    python cli.py run --task factorial # run a single task
    python cli.py run --model <name>   # override the model

Each invocation writes one JSON file to runs/. That file is the contract the
Phase 2 dashboard reads — nothing else is needed to render it.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from harness.runner import load_task, run_task

ROOT = Path(__file__).parent
TASKS_DIR = ROOT / "tasks"
RUNS_DIR = ROOT / "runs"

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-v4-pro"


def main() -> None:
    parser = argparse.ArgumentParser(description="Agent eval harness")
    sub = parser.add_subparsers(dest="command", required=True)
    run_p = sub.add_parser("run", help="run the eval suite")
    run_p.add_argument("--task", help="run only this task id")
    run_p.add_argument("--model", default=DEFAULT_MODEL, help="model to evaluate")
    args = parser.parse_args()

    load_dotenv()
    client = OpenAI(api_key=os.environ.get("API_KEY"), base_url=DEEPSEEK_BASE_URL)

    task_dirs = sorted(
        d for d in TASKS_DIR.iterdir() if d.is_dir() and (d / "task.json").exists()
    )
    if args.task:
        task_dirs = [d for d in task_dirs if d.name == args.task]
        if not task_dirs:
            parser.error(f"no task with id '{args.task}'")

    results = []
    for task_dir in task_dirs:
        task = load_task(task_dir)
        print(f"running task: {task['id']} ...")
        result = run_task(client, args.model, task)
        mark = "PASS" if result["passed"] else "FAIL"
        print(
            f"  {mark}  score={result['score']}  steps={result['steps']}"
            f"  tokens={result['prompt_tokens'] + result['completion_tokens']}"
        )
        results.append(result)

    passed = sum(r["passed"] for r in results)
    run = {
        "run_id": time.strftime("run-%Y%m%d-%H%M%S"),
        "model": args.model,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "tasks_total": len(results),
        "tasks_passed": passed,
        "results": results,
    }

    RUNS_DIR.mkdir(exist_ok=True)
    out = RUNS_DIR / f"{run['run_id']}.json"
    out.write_text(json.dumps(run, indent=2))
    print(f"\n{passed}/{len(results)} tasks passed  ->  {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
