import Link from "next/link";
import type { Metadata } from "next";
import { getData, shortName, type Task } from "@/lib/data";

export const metadata: Metadata = {
  title: "The Audit — Agent Eval Harness",
  description:
    "How the harness audits SWE-bench Verified's own tasks for defects that would make a score meaningless.",
};

/** One row in the corpus-profile stats table. */
const PROFILE_ROWS: { key: string; label: string }[] = [
  { key: "fail_to_pass", label: "FAIL → PASS tests" },
  { key: "pass_to_pass", label: "PASS → PASS tests" },
  { key: "gold_patch_lines", label: "Gold patch lines" },
  { key: "problem_words", label: "Problem statement words" },
];

export default function AuditPage() {
  const { audit_profile, tasks } = getData();
  const flagged = tasks.filter((t) => t.audit_flags.length > 0);

  return (
    <>
      <section>
        <div className="wrap">
          <div className="crumb">
            <Link href="/">Leaderboard</Link> &nbsp;<b>/</b>&nbsp; The Audit
          </div>

          {/* ---- Intro ---- */}
          <div className="shead">
            <h2>The Audit</h2>
            <p>Why some tasks in this corpus cannot be trusted to score the agent</p>
          </div>

          <div className="panel">
            <div className="pb prose">
              <p>
                Most eval harnesses score the agent. This one also scores the{" "}
                <i>benchmark</i>. Before trusting any number, it audits SWE-bench
                Verified&apos;s tasks for defects that would make a score
                meaningless. Of the 25 tasks in this corpus, 5 are flagged,
                across three defect types.
              </p>
            </div>
          </div>

          {/* ---- Flag type 1: broken-tests ---- */}
          <div className="shead" style={{ marginTop: 30 }}>
            <h2>Three defect types</h2>
            <p>Each defect below quarantines or discounts the affected task</p>
          </div>

          <div className="panel" id="broken-tests">
            <div className="ph">
              <span className="pt">Broken grading data</span>
              <span className="px flag">
                <span className="d" />
                broken-tests
              </span>
            </div>
            <div className="pb prose">
              <p>
                The grading data is damaged. Each task carries a list of tests
                to run for grading, each referenced by its name (its id). For
                some tasks, SWE-bench&apos;s data pipeline truncated those names
                wherever they contain a space — the real id{" "}
                <code>test_stem[png-w/ line collection]</code> is stored as the
                fragment <code>test_stem[png-w/</code>. A truncated id points to
                no real test; hand one to pytest and it aborts the entire run,
                so the task would falsely score 0 even for a perfect fix. The
                harness detects these (unbalanced brackets, or stray progress
                markers like <code>[100%]</code>) and quarantines them before
                scoring.
              </p>
              <p>
                <span className="cap">Flagged</span>
                matplotlib-13989, pytest-10081, pytest-5262.
              </p>
            </div>
          </div>

          {/* ---- Flag type 2: broad ---- */}
          <div className="panel" id="broad">
            <div className="ph">
              <span className="pt">Too broad to be one bug</span>
              <span className="px flag">
                <span className="d" />
                broad
              </span>
            </div>
            <div className="pb prose">
              <p>
                The task is too large to be one bug. Every task lists the tests
                that should flip from failing to passing once the bug is fixed
                (its FAIL_TO_PASS set). A focused bug fix flips one or two;
                django-10097 flips 438. That is not a bug fix — it is a sweeping
                change, and any score on it is dominated by sheer test volume
                rather than the quality of the fix.
              </p>
              <p>
                <span className="cap">Flagged</span>
                django-10097.
              </p>
            </div>
          </div>

          {/* ---- Flag type 3: contaminated ---- */}
          <div className="panel" id="contaminated">
            <div className="ph">
              <span className="pt">Contaminated prompt</span>
              <span className="px flag red">
                <span className="d" />
                contaminated
              </span>
            </div>
            <div className="pb prose">
              <p>
                The answer is in the question. The agent is given only the bug
                report — but in scikit-learn-12585 the bug report quotes the
                gold fix verbatim, a line of the actual solution pasted into the
                prompt. The agent can copy it instead of solving anything. A
                pass here measures whether the model can transcribe a line, not
                whether it can fix a bug.
              </p>
              <p>
                <span className="cap">Flagged</span>
                scikit-learn-12585.
              </p>
            </div>
          </div>

          {/* ---- Corpus profile ---- */}
          <div className="shead" style={{ marginTop: 30 }}>
            <h2>Corpus profile</h2>
            <p>Descriptive statistics, not verdicts</p>
          </div>

          <div className="panel">
            <div className="ph">
              <span className="pt">Distribution across all 25 tasks</span>
              <span className="px">min · median · max</span>
            </div>
            <div className="board" style={{ border: 0, borderRadius: 0 }}>
              <div
                className="row head"
                style={{ gridTemplateColumns: "1fr 110px 110px 110px" }}
              >
                <div>Metric</div>
                <div>Min</div>
                <div>Median</div>
                <div>Max</div>
              </div>
              {PROFILE_ROWS.map(({ key, label }) => {
                const stat = audit_profile[key];
                if (!stat) return null;
                return (
                  <div
                    key={key}
                    className="row"
                    style={{ gridTemplateColumns: "1fr 110px 110px 110px" }}
                  >
                    <div className="name">
                      <b>{label}</b>
                    </div>
                    <div className="num-cell">{stat.min}</div>
                    <div className="num-cell">{stat.median}</div>
                    <div className="num-cell">{stat.max}</div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* ---- Flagged tasks ---- */}
          <div className="shead" style={{ marginTop: 30 }}>
            <h2>Flagged tasks</h2>
            <p>The {flagged.length} tasks carrying a benchmark-quality defect</p>
          </div>

          <div className="board">
            <div
              className="row head"
              style={{ gridTemplateColumns: "34px 1fr 200px" }}
            >
              <div>#</div>
              <div>Task</div>
              <div>Defect</div>
            </div>
            {flagged.map((task: Task, i) => (
              <Link
                key={task.instance_id}
                href={`/task/${task.instance_id}`}
                className="row task"
                style={{
                  gridTemplateColumns: "34px 1fr 200px",
                  animationDelay: `${(i + 1) * 0.02}s`,
                }}
              >
                <div className="idx">{String(i + 1).padStart(2, "0")}</div>
                <div className="name">
                  <b>{shortName(task.instance_id)}</b>
                </div>
                <div className="flags">
                  {task.audit_flags.map((flag, j) => (
                    <span
                      key={j}
                      className={`flag${
                        flag.category === "contaminated" ? " red" : ""
                      }`}
                    >
                      <span className="d" />
                      {flag.category}
                    </span>
                  ))}
                </div>
              </Link>
            ))}
          </div>
          <div className="hint">
            Click any row for its full task detail — the defect is described in
            the audit callout at the top of the page.
          </div>
        </div>
      </section>
    </>
  );
}
