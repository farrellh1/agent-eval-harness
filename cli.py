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


def _run_local(client, model: str, only: str | None, save) -> list[dict]:
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
        try:
            result = run_task(client, model, task)
        except Exception as e:  # broad on purpose: one bad task must not end the run
            result = _error_result(task["id"], e)
        _print_result(result)
        results.append(result)
        save(results)
    return results


def _run_swebench(
    client, model: str, only: str | None, save, cleanup_image: bool
) -> list[dict]:
    tasks = load_swebench_tasks(CORPUS)
    if only:
        tasks = [t for t in tasks if t["instance_id"] == only]
        if not tasks:
            raise SystemExit(f"no SWE-bench task with instance_id '{only}'")

    results = []
    for task in tasks:
        print(f"running SWE-bench task: {task['instance_id']} ...")
        try:
            result = run_swebench_task(client, model, task, cleanup_image=cleanup_image)
        except Exception as e:  # broad on purpose: one bad task must not end the run
            result = _error_result(task["instance_id"], e)
        _print_result(result)
        results.append(result)
        save(results)  # write after every task: a long run stays recoverable
    return results


def _print_result(result: dict) -> None:
    mark = "PASS" if result["passed"] else "FAIL"
    tokens = result["prompt_tokens"] + result["completion_tokens"]
    print(
        f"  {mark}  score={result['score']}  steps={result['steps']}"
        f"  tokens={tokens}  {result['duration_s']}s"
    )
    if result.get("error"):
        print(f"  ERROR: {result['error']}")


def _error_result(task_id: str, error: Exception) -> dict:
    """A result record for a task that crashed before it could be scored.

    A bad image or a network blip on one task must not lose the rest of a long
    run, so the loop records the failure as a result and moves on.
    """
    return {
        "task_id": task_id,
        "passed": False,
        "score": 0.0,
        "steps": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "duration_s": 0.0,
        "error": f"{type(error).__name__}: {error}",
    }


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
        if name == "swebench":
            p.add_argument(
                "--keep-images",
                action="store_true",
                help="keep each task's Docker image instead of removing it",
            )
    args = parser.parse_args()

    client = _client()
    run_id = time.strftime("run-%Y%m%d-%H%M%S")
    created_at = time.strftime("%Y-%m-%dT%H:%M:%S")
    RUNS_DIR.mkdir(exist_ok=True)
    out_path = RUNS_DIR / f"{run_id}.json"

    def save(results: list[dict]) -> None:
        """Write the run file. Called after every task, so an interrupted run
        still leaves a complete record of the tasks that did finish."""
        run = {
            "run_id": run_id,
            "model": args.model,
            "created_at": created_at,
            "tasks_total": len(results),
            "tasks_passed": sum(r["passed"] for r in results),
            "results": results,
        }
        out_path.write_text(json.dumps(run, indent=2))

    if args.command == "run":
        results = _run_local(client, args.model, args.task, save)
    else:
        results = _run_swebench(
            client, args.model, args.task, save, cleanup_image=not args.keep_images
        )

    if results:
        passed = sum(r["passed"] for r in results)
        print(
            f"\n{passed}/{len(results)} tasks passed  ->  {out_path.relative_to(ROOT)}"
        )


if __name__ == "__main__":
    main()
