"""CLI entry point for the agent eval harness.

Usage:
    python cli.py run                   # every toy task in tasks/
    python cli.py run --task factorial  # one toy task
    python cli.py swebench              # every SWE-bench task in the corpus
    python cli.py swebench --task <id>  # one SWE-bench task by instance_id

Each invocation writes one JSON file to runs/ - the contract the Phase 2
dashboard reads.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from harness.runner import load_task, run_swebench_task, run_task
from harness.swebench import load_swebench_tasks

ROOT = Path(__file__).parent
TASKS_DIR = ROOT / "tasks"
RUNS_DIR = ROOT / "runs"
CORPUS = ROOT / "corpus" / "swe_bench_verified_subset.jsonl"

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-v4-pro"


def _client() -> OpenAI:
    load_dotenv()
    return OpenAI(api_key=os.environ.get("API_KEY"), base_url=DEEPSEEK_BASE_URL)


def _run_local(client, model: str, only: str | None) -> list[dict]:
    task_dirs = sorted(
        d for d in TASKS_DIR.iterdir() if d.is_dir() and (d / "task.json").exists()
    )
    if only:
        task_dirs = [d for d in task_dirs if d.name == only]
        if not task_dirs:
            raise SystemExit(f"no task with id '{only}'")

    results = []
    for task_dir in task_dirs:
        task = load_task(task_dir)
        print(f"running task: {task['id']} ...")
        result = run_task(client, model, task)
        _print_result(result)
        results.append(result)
    return results


def _run_swebench(client, model: str, only: str | None) -> list[dict]:
    tasks = load_swebench_tasks(CORPUS)
    if only:
        tasks = [t for t in tasks if t["instance_id"] == only]
        if not tasks:
            raise SystemExit(f"no SWE-bench task with instance_id '{only}'")

    results = []
    for task in tasks:
        print(f"running SWE-bench task: {task['instance_id']} ...")
        result = run_swebench_task(client, model, task)
        _print_result(result)
        results.append(result)
    return results


def _print_result(result: dict) -> None:
    mark = "PASS" if result["passed"] else "FAIL"
    tokens = result["prompt_tokens"] + result["completion_tokens"]
    print(
        f"  {mark}  score={result['score']}  steps={result['steps']}"
        f"  tokens={tokens}  {result['duration_s']}s"
    )


def _write_run(model: str, results: list[dict]) -> None:
    passed = sum(r["passed"] for r in results)
    run = {
        "run_id": time.strftime("run-%Y%m%d-%H%M%S"),
        "model": model,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "tasks_total": len(results),
        "tasks_passed": passed,
        "results": results,
    }
    RUNS_DIR.mkdir(exist_ok=True)
    out = RUNS_DIR / f"{run['run_id']}.json"
    out.write_text(json.dumps(run, indent=2))
    print(f"\n{passed}/{len(results)} tasks passed  ->  {out.relative_to(ROOT)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Agent eval harness")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, help_text in [
        ("run", "run the toy-task suite"),
        ("swebench", "run SWE-bench Verified tasks"),
    ]:
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--task", help="run only this task / instance id")
        p.add_argument("--model", default=DEFAULT_MODEL, help="model to evaluate")
    args = parser.parse_args()

    client = _client()
    if args.command == "run":
        results = _run_local(client, args.model, args.task)
    else:
        results = _run_swebench(client, args.model, args.task)

    if results:
        _write_run(args.model, results)


if __name__ == "__main__":
    main()
