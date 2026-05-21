"""Select a stratified subset of SWE-bench Verified for the eval harness corpus.

Methodology (day-1 selection; full audit-driven curation comes later):
  - stratify across every repository so no single repo dominates the subset
  - bias toward shorter fixes ("<15 min fix" first) so tasks are tractable for
    a smoke-test harness, with some "15 min - 1 hour" tasks for difficulty range
  - deterministic: the same subset every run, so eval scores stay comparable

Run:  python corpus/select_subset.py
Out:  corpus/swe_bench_verified_subset.jsonl
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from datasets import load_dataset

TARGET = 25
PER_REPO_CAP = 2
DIFFICULTY_RANK = {
    "<15 min fix": 0,
    "15 min - 1 hour": 1,
    "1-4 hours": 2,
    ">4 hours": 3,
}
OUT = Path(__file__).parent / "swe_bench_verified_subset.jsonl"


def main() -> None:
    ds = load_dataset("princeton-nlp/SWE-bench_Verified", split="test")

    by_repo: dict[str, list[dict]] = defaultdict(list)
    for row in ds:
        by_repo[row["repo"]].append(dict(row))

    # Within each repo: easiest first, then deterministic by instance_id.
    for rows in by_repo.values():
        rows.sort(
            key=lambda r: (DIFFICULTY_RANK.get(r["difficulty"], 9), r["instance_id"])
        )

    selected: list[dict] = []
    # Pass 1: up to PER_REPO_CAP tasks from every repo (breadth).
    for repo in sorted(by_repo):
        selected.extend(by_repo[repo][:PER_REPO_CAP])
    # Pass 2: top up from the largest repos until TARGET is reached.
    for repo in sorted(by_repo, key=lambda r: -len(by_repo[r])):
        for row in by_repo[repo][PER_REPO_CAP:]:
            if len(selected) >= TARGET:
                break
            selected.append(row)
        if len(selected) >= TARGET:
            break

    selected.sort(key=lambda r: r["instance_id"])
    with OUT.open("w") as f:
        for row in selected:
            f.write(json.dumps(row) + "\n")

    print(f"wrote {len(selected)} tasks -> {OUT.relative_to(OUT.parent.parent)}")
    print("\nby repo:")
    for repo, n in Counter(r["repo"] for r in selected).most_common():
        print(f"  {n:3d}  {repo}")
    print("\nby difficulty:")
    for diff, n in Counter(r["difficulty"] for r in selected).most_common():
        print(f"  {n:3d}  {diff}")


if __name__ == "__main__":
    main()
