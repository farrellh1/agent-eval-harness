import type { TraceEvent } from "@/lib/data";
import { CollapsibleText } from "./collapsible-text";

/** One step's worth of trace events: a reasoning block + any tool calls. */
type StepGroup = {
  step: number;
  reasoning: string[];
  calls: { call: TraceEvent; result?: TraceEvent }[];
};

/** Group the flat trace event list into per-step blocks, preserving order. */
function groupSteps(trace: TraceEvent[]): StepGroup[] {
  const groups: StepGroup[] = [];
  const byStep = new Map<number, StepGroup>();

  for (const event of trace) {
    let group = byStep.get(event.step);
    if (!group) {
      group = { step: event.step, reasoning: [], calls: [] };
      byStep.set(event.step, group);
      groups.push(group);
    }
    if (event.kind === "reasoning") {
      group.reasoning.push(event.content);
    } else if (event.kind === "tool_call") {
      group.calls.push({ call: event });
    } else if (event.kind === "tool_result") {
      // Attach to the most recent call without a result yet.
      const open = [...group.calls].reverse().find((c) => !c.result);
      if (open) open.result = event;
      else group.calls.push({ call: event, result: event });
    }
  }
  return groups;
}

/** Pretty-print tool call arguments; falls back to the raw string. */
function formatArgs(raw: string): string {
  try {
    const obj = JSON.parse(raw);
    const entries = Object.entries(obj).map(([k, v]) => {
      let val = typeof v === "string" ? v : JSON.stringify(v);
      if (val.length > 160) val = val.slice(0, 160) + "…";
      return `${k}: ${JSON.stringify(val)}`;
    });
    return `{ ${entries.join(", ")} }`;
  } catch {
    return raw.length > 200 ? raw.slice(0, 200) + "…" : raw;
  }
}

/** Vertical timeline of the agent's run, matching the prototype trace layout. */
export function Trace({ trace }: { trace: TraceEvent[] }) {
  const groups = groupSteps(trace);
  if (groups.length === 0) {
    return (
      <div className="result" style={{ marginTop: 14 }}>
        <div className="rbody">No trace recorded for this task.</div>
      </div>
    );
  }

  return (
    <div className="trace">
      {groups.map((group) => {
        const active = group.calls.length > 0;
        const label = active ? "tool use" : "reasoning";
        return (
          <div key={group.step} className={`step${active ? " act" : ""}`}>
            <div className="gutter">
              <div className="node" />
            </div>
            <div className="sb">
              <div className="sn">
                Step {String(group.step + 1).padStart(2, "0")} &nbsp;
                <span>{label}</span>
              </div>

              {group.reasoning.map((text, i) => (
                <div className="think" key={i}>
                  {text}
                </div>
              ))}

              {group.calls.map(({ call, result }, i) => (
                <div key={i}>
                  <div className="call">
                    <span className="fn">{call.name || "tool"}</span>
                    <span className="ar">{formatArgs(call.content)}</span>
                  </div>
                  {result && (
                    <div className="result">
                      <div className="rh">
                        tool result · {result.name || call.name}
                      </div>
                      <CollapsibleText text={result.content} />
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
