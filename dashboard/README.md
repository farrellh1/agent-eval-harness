# agent-eval-harness — Phase 2 dashboard

A static Next.js dashboard for the agent-eval-harness. It presents one
SWE-bench Verified run: a leaderboard of all 25 tasks and a per-task detail
page with the problem statement, gold patch, the agent's trace, and the
benchmark-quality audit flags.

Everything is statically generated (SSG) from a single build-time data file —
there is no server or API at runtime.

## Stack

- Next.js (App Router) + TypeScript
- Tailwind CSS v4 + shadcn/ui (themed to the prototype palette)
- Fonts: Poppins (UI) and IBM Plex Mono (code/diffs/trace), via `next/font`

The visual design is ported verbatim from `prototype.html`, which is the
approved Phase 2 design and is kept in this directory for reference.

## Regenerate the data

The dashboard reads `public/data.json`, produced by joining three sources:

- `corpus/swe_bench_verified_subset.jsonl` — the 25 SWE-bench tasks
- `runs/run-20260522-172308.json` — the full 25-task agent run
- `corpus/audit.json` — benchmark-quality audit flags

Run the build script **from the repository root** (it imports `harness.agent`
to capture the agent's real system prompt):

```bash
python dashboard/scripts/build_data.py
```

This writes `dashboard/public/data.json`. Re-run it whenever the corpus, run,
or audit inputs change.

## Develop

```bash
cd dashboard
npm install        # first time only
npm run dev        # http://localhost:3000
```

## Build

```bash
cd dashboard
npm run build      # generates the leaderboard + one static page per task
```

## Deploy to Vercel

This app lives in the `dashboard/` subdirectory of the repository. When
importing the project into Vercel, **set the project's Root Directory to
`dashboard`** so Vercel runs `npm run build` in the right place. No further
configuration is required — every route is prerendered to static HTML.
