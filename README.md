# Agent Eval Harness

**A test suite for coding agents — and an audit of the benchmark they're scored on.**

Ordinary tests use `assertEqual`. An agent doesn't return a value: it runs a
loop (think → call a tool → observe → repeat) and its "output" is a changed
repository. Scoring that needs a real harness. This is that harness.

> **Status:** in active development (started 2026-05-21). Phase 1 (harness) underway.

## What it does

Given a task — *"this repo has a failing test, fix it"* — the harness:

1. **Runs** the agent inside an isolated working copy of the repo.
2. **Scores** the result — did the failing test pass? were others broken? how
   many steps and tokens did it cost? Partial credit, not bare pass/fail.
3. **Traces** every reasoning step and tool call, so failures are diagnosable.
4. **Records** each run as structured JSON for regression diffing across runs.
5. **Audits** the task corpus itself — which tasks are contaminated, have weak
   hidden tests, or fail to separate good agents from bad. *(planned)*

## Why

Most engineers can build an agent. Far fewer can rigorously measure one. The
corpus is **SWE-bench Verified**, and a core deliverable is a quality audit of
it: a benchmark is only as honest as its weakest task.

## Layout

```
harness/
  agent.py     the coding agent — the system under test
  tools.py     read_file / write_file / run_bash, sandboxed to a workdir
  trace.py     structured step-by-step event log
  scorer.py    run the tests, compute pass/fail and partial credit
  runner.py    task -> isolated workdir -> agent -> score
  audit.py     per-task corpus quality flags (planned)
cli.py         command-line entry point
tasks/         eval tasks — toy tasks now, SWE-bench Verified subset next
runs/          one JSON file per suite run (committed; the dashboard reads these)
```

## Run it

```bash
cp .env.example .env   # then add your API key
python cli.py run                   # run the whole suite
python cli.py run --task factorial  # run a single task
```

## Roadmap

- [x] Phase 1 scaffold — agent loop, runner, scorer, trace, JSON output
- [ ] SWE-bench Verified subset (20–30 tasks), Docker-isolated execution
- [ ] Corpus audit — contamination / weak-test / discrimination flags
- [ ] FDE-grade run hardening — retries, checkpointing, cost tracking
- [ ] Regression diffing across runs
- [ ] Phase 2 — Next.js dashboard on Vercel, reads `runs/*.json`
