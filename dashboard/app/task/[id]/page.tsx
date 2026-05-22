import Link from "next/link";
import { notFound } from "next/navigation";
import { getData, getTask, shortName, type Task } from "@/lib/data";
import { formatScore, num } from "@/lib/format";
import { Diff } from "@/components/diff";
import { Trace } from "@/components/trace";
import { CollapsiblePre } from "@/components/collapsible-pre";

/** Pre-render one static page per task in data.json. */
export function generateStaticParams() {
  return getData().tasks.map((task) => ({ id: task.instance_id }));
}

export async function generateMetadata({
  params,
}: PageProps<"/task/[id]">) {
  const { id } = await params;
  return { title: `${id} — Agent Eval Harness` };
}

/** Audit callout shown when a task carries one or more benchmark-quality flags. */
function AuditCallout({ task }: { task: Task }) {
  if (task.audit_flags.length === 0) return null;
  const hasContaminated = task.audit_flags.some(
    (f) => f.category === "contaminated",
  );
  return (
    <div className={`callout${hasContaminated ? "" : " amber"}`}>
      <div className="ct">
        ⬤&nbsp; Audit flag —{" "}
        {task.audit_flags.map((f) => f.category).join(", ")}
      </div>
      {task.audit_flags.map((flag, i) => (
        <p key={i}>{flag.detail}</p>
      ))}
      <p>
        <Link
          className="callout-link"
          href={`/audit#${task.audit_flags[0].category}`}
        >
          what does this mean? →
        </Link>
      </p>
    </div>
  );
}

export default async function TaskDetailPage({
  params,
}: PageProps<"/task/[id]">) {
  const { id } = await params;
  const task = getTask(id);
  if (!task) notFound();

  const { run } = getData();
  const totalGraded = task.fail_to_pass_total + task.pass_to_pass_total;
  const totalPassed = task.fail_to_pass_passed + task.pass_to_pass_passed;
  const allGreen = totalPassed === totalGraded && totalGraded > 0;

  return (
    <>
      <section>
        <div className="wrap">
          <div className="crumb">
            <Link href="/">Leaderboard</Link> &nbsp;<b>/</b>&nbsp;{" "}
            {shortName(task.instance_id)}
          </div>

          <div className="thead">
            <div>
              <h3>{task.instance_id}</h3>
              <div className="meta">
                {task.repo} · v{task.version} &nbsp;·&nbsp; {task.steps} steps ·{" "}
                {num(task.prompt_tokens + task.completion_tokens)} tokens ·{" "}
                {Math.round(task.duration_s)}s
              </div>
            </div>
            <div className="verdict">
              <div className={`v${task.resolved ? "" : " no"}`}>
                <span className={`dot ${task.resolved ? "on" : "off"}`} />
                {task.resolved ? "resolved" : "partial"}
              </div>
              <div className="s">{formatScore(task.score)}</div>
            </div>
          </div>

          <AuditCallout task={task} />

          {/* ---- The task ---- */}
          <div className="shead" style={{ marginTop: 30 }}>
            <h2>The task</h2>
            <p>
              The bug report the agent was given — plus the gold fix and hidden
              tests, shown here for reference. The agent saw only the problem
              statement.
            </p>
          </div>

          <div className="panel">
            <div className="ph">
              <span className="pt">Problem statement</span>
              <span className="px">github issue</span>
            </div>
            <div className="pb prose">
              <CollapsiblePre text={task.problem_statement} />
            </div>
          </div>

          <div className="panel">
            <div className="ph">
              <span className="pt">Gold patch</span>
              <span className="px">held back · the reference fix</span>
            </div>
            <div className="pb" style={{ padding: "14px 0" }}>
              <Diff patch={task.gold_patch} />
            </div>
          </div>

          <div className="panel">
            <div className="ph">
              <span className="pt">Hidden test</span>
              <span className="px">test_patch · applied only to grade</span>
            </div>
            <div className="pb">
              <Diff patch={task.test_patch} />
              <div className="graded">
                <div className="gchip">
                  <b>{task.fail_to_pass_passed}</b>
                  <span>
                    FAIL → PASS{" "}
                    {task.fail_to_pass_total !== task.fail_to_pass_passed
                      ? `(of ${task.fail_to_pass_total})`
                      : ""}
                  </span>
                </div>
                <div className="gchip">
                  <b>{task.pass_to_pass_passed}</b>
                  <span>
                    PASS → PASS{" "}
                    {task.pass_to_pass_total !== task.pass_to_pass_passed
                      ? `(of ${task.pass_to_pass_total})`
                      : ""}
                  </span>
                </div>
                <div className="gchip">
                  <b style={{ color: allGreen ? "var(--green)" : "var(--amber)" }}>
                    {totalPassed} / {totalGraded}
                  </b>
                  <span>{allGreen ? "green" : "graded tests"}</span>
                </div>
              </div>
            </div>
          </div>

          {/* ---- The agent run ---- */}
          <div className="shead" style={{ marginTop: 30 }}>
            <h2>The agent run</h2>
            <p>
              The agent&apos;s step-by-step attempt — its reasoning, the tools it
              called, and the patch it produced.
            </p>
          </div>

          <div className="panel">
            <div className="ph">
              <span className="pt">System prompt</span>
              <span className="px">harness.agent.build_system_prompt</span>
            </div>
            <div className="pb">
              <CollapsiblePre text={run.system_prompt} />
            </div>
          </div>

          <Trace trace={task.trace} />

          <div className="panel">
            <div className="ph">
              <span className="pt">Agent diff</span>
              <span className="px">
                {task.patch_applied
                  ? "captured before grading"
                  : "captured · patch did not apply"}
              </span>
            </div>
            <div className="pb" style={{ padding: "14px 0" }}>
              {task.agent_diff.trim() ? (
                <Diff patch={task.agent_diff} />
              ) : (
                <div style={{ padding: "0 14px", color: "var(--faint)" }}>
                  The agent produced no diff for this task.
                </div>
              )}
            </div>
          </div>
        </div>
      </section>
    </>
  );
}
