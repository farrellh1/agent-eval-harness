# Agent Eval Harness

**Runs coding agents on SWE-bench Verified — and audits the benchmark itself.**

Most eval harnesses score the *agent*. This one also scores the *benchmark*.

Running a coding agent across a 25-task slice of **SWE-bench Verified**, the
built-in audit flagged **5 of the 25 tasks as defective** — including **6
corrupted test ids** that silently score a correct fix as 0, an abnormally
broad task, and one whose **solution is pasted verbatim into the prompt**.
Those are defects in the *gold-standard* benchmark. A score is only as
trustworthy as the task behind it — so this harness checks both.

**▶ Live dashboard:** **https://dashboard-phi-woad-35.vercel.app**
— every run, every agent trace, every audit flag.

## Results

`deepseek-v4-pro`, on a 25-task stratified slice of SWE-bench Verified (12 repositories):

| | |
|---|---|
| Resolved | **14 / 25** — all hidden tests pass, no regressions |
| Mean score | **0.975** — partial credit (fraction of graded tests passing) |
| Flagged by the audit | **5 / 25** — corrupted, broad, or contaminated tasks |

The agent is deliberately minimal — it is the *subject* of the measurement,
not the product. The engineered part is the harness and the audit.

## The audit — the part that's different

A benchmark is only as honest as its weakest task. `python cli.py audit`
statically inspects every task — no agent, no Docker, instant — and flags
three defect classes:

- **`broken-tests`** — the task's list of grading tests contains corrupted
  ids. SWE-bench's data pipeline truncates any test name that contains a
  space (`test_x[w/ a flag]` becomes the fragment `test_x[w/`). One such id
  makes pytest abort the entire run, silently scoring a correct fix as 0.
  *Found in 3 tasks, 6 ids.*
- **`broad`** — the task expects an abnormal number of tests to flip from
  failing to passing (one task: **438**, against a normal 1–2). That is a
  sweeping change, not a focused bug fix. *Found in 1 task.*
- **`contaminated`** — the gold solution's code appears in the problem
  statement. The agent can copy the answer; a pass measures retrieval, not
  problem-solving. *Found in 1 task.*

The harness quarantines corrupted ids so scoring stays correct, and records
every flag — so a "resolved" never silently overclaims.

## How it works

A coding agent is not a function. It runs a loop — think → call a tool →
observe → repeat — and its "output" is a mutated repository. Scoring that
needs a real harness.

- **The agent** (`harness/agent.py`) — a minimal loop with four tools
  (`read_file`, `write_file`, `edit_file`, `run_bash`). Kept simple on
  purpose: it is what gets measured.
- **Executors** (`harness/executor.py`) — the agent's tools run against a
  swappable environment: a sandboxed local directory for toy tasks, or a
  per-task **Docker** container for SWE-bench. Swap the environment, never
  the agent.
- **Per-repo test specs** (`harness/testspec.py`) — SWE-bench's 12 repos do
  not all use pytest; django and sympy need their own runners and parsers.
- **Scoring** (`harness/scorer.py`) — partial credit, the SWE-bench way:
  every `FAIL_TO_PASS` test must now pass and every `PASS_TO_PASS` test must
  stay green.
- **The audit** (`harness/audit.py`) — the static benchmark-quality checks.
- **The dashboard** (`dashboard/`) — a static Next.js app: a leaderboard,
  per-task detail (problem statement, gold patch, hidden tests, the agent's
  full trace and diff), and an `/audit` explainer.

Cheat isolation throughout: the agent sees only the problem statement —
never the hidden tests, never the gold patch — and the grading tests are
applied only after it stops.

## What a real run surfaced

The harness was hardened by *running* it. The first full run exposed — and
the harness now handles — a row of real-world integration defects:

- pytest output wrapped in ANSI colour codes, breaking the result parser
- SWE-bench containers with no UTF-8 locale, crashing django on non-ASCII output
- sympy's Docker images shipping no pytest at all
- a 1,870-test task overflowing the OS command-length limit
- the agent editing a *test* file and corrupting its own grading

Each was caught by a real run, not by guessing — and fixed.

## Run it

Requires Python 3.12+ and Docker (for SWE-bench tasks).

```bash
pip install -e .
cp .env.example .env            # add your DeepSeek API key

python cli.py audit             # audit the corpus — static, instant, no API key
python cli.py swebench --task pallets__flask-5014   # run one task
python cli.py swebench          # run the full 25-task slice
```

The dashboard ships with its data committed, so it runs immediately:

```bash
cd dashboard && npm install && npm run dev
```

Regenerate the dashboard's data after a new run with
`python dashboard/scripts/build_data.py`.

## Layout

```
harness/      the harness — agent, executors, runner, scorer, test specs, audit
corpus/       the 25-task SWE-bench Verified slice + audit.json
cli.py        run tasks, or audit the corpus
runs/         one JSON record per run (generated)
dashboard/    the Next.js results dashboard
```
