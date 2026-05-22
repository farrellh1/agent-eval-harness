import Link from "next/link";
import { getData, getSortedTasks, shortName, type Task } from "@/lib/data";
import { barClass, formatScore } from "@/lib/format";

/** Render the audit-flag badges (or an em-dash) for a leaderboard row. */
function FlagBadges({ task }: { task: Task }) {
  if (task.audit_flags.length === 0) {
    return <span className="dash">—</span>;
  }
  return (
    <>
      {task.audit_flags.map((flag, i) => (
        <span
          key={i}
          className={`flag${flag.category === "contaminated" ? " red" : ""}`}
        >
          <span className="d" />
          {flag.category}
        </span>
      ))}
    </>
  );
}

export default function LeaderboardPage() {
  const { run } = getData();
  const tasks = getSortedTasks();
  const repoCount = new Set(tasks.map((t) => t.repo)).size;

  return (
    <>
      <header>
        <div className="wrap">
          <h1>
            Agent Eval Harness <span>/ SWE-bench Verified</span>
          </h1>
          <div className="sub">
            <b>{run.model}</b> &nbsp;·&nbsp; {run.tasks_total} tasks across{" "}
            {repoCount} repositories &nbsp;·&nbsp; run {run.run_id}
          </div>
          <p className="intro">
            <b>{run.model}</b> was run on {run.tasks_total} real bug-fix tasks
            from SWE-bench Verified — each a genuine GitHub issue from a major
            Python project. The agent sees only the bug report and must produce
            a fix; hidden tests it never sees decide the score. The harness also{" "}
            <Link href="/audit">audits the tasks themselves</Link>.
          </p>
          <div className="readouts">
            <div className="readout">
              <div className="rl">Resolved</div>
              <div className="rv">
                {run.tasks_passed}
                <small>&nbsp;/ {run.tasks_total}</small>
              </div>
              <div className="rd">all FAIL→PASS and PASS→PASS tests green</div>
            </div>
            <div className="readout">
              <div className="rl">Mean score</div>
              <div className="rv">{run.mean_score.toFixed(3)}</div>
              <div className="rd">
                partial credit · fraction of graded tests passing
              </div>
            </div>
            <Link href="/audit" className="readout readout-flag">
              <div className="rl">Flagged by audit</div>
              <div className="rv">{run.tasks_flagged}</div>
              <div className="rd">tasks with a benchmark-quality defect</div>
            </Link>
          </div>
        </div>
      </header>

      <section>
        <div className="wrap">
          <div className="shead">
            <h2>Leaderboard</h2>
            <p>Per-task results · click a row for the full trace</p>
          </div>
          <div className="board">
            <div className="row head">
              <div>#</div>
              <div>Task</div>
              <div>Resolved</div>
              <div className="col-score">Score</div>
              <div className="col-audit">Audit</div>
            </div>

            {tasks.map((task, i) => (
              <Link
                key={task.instance_id}
                href={`/task/${task.instance_id}`}
                className="row task"
                style={{ animationDelay: `${(i + 1) * 0.02}s` }}
              >
                <div className="idx">{String(i + 1).padStart(2, "0")}</div>
                <div className="name">
                  <b>{shortName(task.instance_id)}</b>
                </div>
                <div>
                  <span className={`res${task.resolved ? " y" : ""}`}>
                    <span className={`dot ${task.resolved ? "on" : "off"}`} />
                    {task.resolved ? "resolved" : "partial"}
                  </span>
                </div>
                <div className="score col-score">
                  <span className="num">{formatScore(task.score)}</span>
                  <span className={barClass(task.score)}>
                    <i
                      style={{
                        width: `${Math.round(task.score * 100)}%`,
                      }}
                    />
                  </span>
                </div>
                <div className="flags col-audit">
                  <FlagBadges task={task} />
                </div>
              </Link>
            ))}
          </div>
          <div className="hint">
            Click any row for its full task detail — problem statement, gold
            patch, the agent&apos;s trace and the captured diff.
          </div>
        </div>
      </section>
    </>
  );
}
