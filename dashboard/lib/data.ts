/**
 * Loads and types the static run data produced by scripts/build_data.py.
 *
 * data.json is a build-time artifact read directly from disk; nothing here
 * touches the network or request context, so every page that uses it is
 * statically generated.
 */
import fs from "node:fs";
import path from "node:path";

export type AuditFlag = {
  category: string;
  detail: string;
};

export type TraceEvent = {
  step: number;
  kind: "reasoning" | "tool_call" | "tool_result";
  name: string;
  content: string;
  timestamp: number;
};

export type Task = {
  instance_id: string;
  repo: string;
  version: string;
  difficulty: string;
  resolved: boolean;
  score: number;
  fail_to_pass_passed: number;
  fail_to_pass_total: number;
  pass_to_pass_passed: number;
  pass_to_pass_total: number;
  problem_statement: string;
  gold_patch: string;
  test_patch: string;
  agent_diff: string;
  patch_applied: boolean;
  patch_error: string;
  malformed_ids: string[];
  test_runner: string;
  steps: number;
  completed: boolean;
  prompt_tokens: number;
  completion_tokens: number;
  duration_s: number;
  trace: TraceEvent[];
  audit_flags: AuditFlag[];
};

export type RunSummary = {
  run_id: string;
  model: string;
  created_at: string;
  tasks_total: number;
  tasks_passed: number;
  tasks_flagged: number;
  mean_score: number;
  system_prompt: string;
};

export type AuditProfile = Record<
  string,
  { min: number; median: number; max: number }
>;

export type DashboardData = {
  run: RunSummary;
  audit_profile: AuditProfile;
  tasks: Task[];
};

let cached: DashboardData | null = null;

/** Read and cache the joined dashboard data from public/data.json. */
export function getData(): DashboardData {
  if (cached) return cached;
  const file = path.join(process.cwd(), "public", "data.json");
  cached = JSON.parse(fs.readFileSync(file, "utf-8")) as DashboardData;
  return cached;
}

/** All tasks sorted resolved-first, then by score descending. */
export function getSortedTasks(): Task[] {
  return [...getData().tasks].sort((a, b) => {
    if (a.resolved !== b.resolved) return a.resolved ? -1 : 1;
    return b.score - a.score;
  });
}

/** Look up one task by its instance_id. */
export function getTask(instanceId: string): Task | undefined {
  return getData().tasks.find((t) => t.instance_id === instanceId);
}

/**
 * Short task label, e.g. "scikit-learn__scikit-learn-12585" -> "scikit-learn-12585".
 * Matches the leaderboard naming in the prototype.
 */
export function shortName(instanceId: string): string {
  const parts = instanceId.split("__");
  return parts[parts.length - 1] ?? instanceId;
}
