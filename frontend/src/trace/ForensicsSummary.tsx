import { useEffect, useRef } from "react";

import type { TraceEvent } from "./TracePage";
import type { IncidentState } from "@/ladder/types";
import { actionToolName, PROTECTIVE_TOOLS } from "@/ladder/tools";
import { localTime } from "@/lib/time";

export type ExplanationSource = "llm" | "partial" | "unavailable";
export type ExplanationState = "loading" | ExplanationSource;

/**
 * The call the agent made, as it would be written down.
 *
 * Only fields the tape actually carries: a shell step reads as a command, everything
 * else as its tool and target. Arguments and HTTP methods are not in the trace
 * payload, so none are invented here.
 */
function invocation(event: TraceEvent) {
  const target = event.target ?? "";
  if (event.kind === "shell_command") return `$ ${target}`;
  if (!event.tool) return target;
  return `${event.tool}(${target ? `"${target}"` : ""})`;
}

/** How long the run took, wall clock, from its first recorded step to its last. */
function runDuration(events: TraceEvent[]): string {
  if (events.length < 2) return "";
  const first = new Date(events[0].timestamp).getTime();
  const last = new Date(events.at(-1)!.timestamp).getTime();
  if (Number.isNaN(first) || Number.isNaN(last) || last < first) return "";
  const seconds = Math.round((last - first) / 1000);
  if (seconds < 60) return `${seconds}s`;
  return `${Math.floor(seconds / 60)}m ${String(seconds % 60).padStart(2, "0")}s`;
}

/** One protective step we ran, in the order it happened. */
type Response = {
  key: string;
  title: string;
  purpose: string;
  command: string;
  at: string;
  requestedBy: string;
  failed: boolean;
};

/**
 * What we did about it, from the action journal.
 *
 * Only steps that reached a terminal state are listed, each with the command the
 * playbook runs, so the account says how the incident was handled and not just what
 * the agent did. Commands are the documented ones; nothing here is inferred.
 */
function responses(incident: IncidentState | null): Response[] {
  if (!incident || !Array.isArray(incident.actions)) return [];
  const latest = new Map<string, Response>();
  for (const action of incident.actions) {
    if (action.status !== "ok" && action.status !== "failed") continue;
    const name = actionToolName(action.action_id) ?? action.name;
    const tool = PROTECTIVE_TOOLS[name];
    if (!tool) continue;
    latest.set(action.action_id, {
      key: action.action_id,
      title: tool.title,
      purpose: tool.purpose,
      command: tool.command ?? "",
      at: action.timestamp,
      requestedBy: action.source === "oncall_phone" ? "authorised on the call" : "monitor",
      failed: action.status === "failed",
    });
  }
  return [...latest.values()].sort((a, b) => a.at.localeCompare(b.at));
}

/**
 * The run as a list of calls, and nothing else.
 *
 * Scrolling it moves the graph: each call reports its position as it reaches the top
 * of the reading area and the graph pans to the matching node, so reading the run and
 * following the chain are one gesture.
 */
export function ForensicsSummary({
  events,
  explanations,
  incident,
  model,
  selectedNodeId,
  onSelectNode,
}: {
  events: TraceEvent[];
  explanations: Record<string, string> | null;
  state: ExplanationState;
  incident: IncidentState | null;
  model: string | null;
  selectedNodeId: string | null;
  onSelectNode: (id: string) => void;
}) {
  const handled = responses(incident);
  const duration = runDuration(events);
  const scroller = useRef<HTMLDivElement>(null);
  const steps = useRef(new Map<string, HTMLElement>());
  const onSelectRef = useRef(onSelectNode);
  onSelectRef.current = onSelectNode;

  useEffect(() => {
    const root = scroller.current;
    if (!root || typeof IntersectionObserver !== "function") return;
    const visible = new Set<string>();
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          const id = entry.target.getAttribute("data-step");
          if (!id) continue;
          if (entry.isIntersecting) visible.add(id);
          else visible.delete(id);
        }
        const first = events.find((event) => visible.has(event.id));
        if (first) onSelectRef.current(first.id);
      },
      { root, rootMargin: "0px 0px -70% 0px", threshold: 0 },
    );
    for (const node of steps.current.values()) observer.observe(node);
    return () => observer.disconnect();
  }, [events]);

  const previous = useRef(selectedNodeId);
  useEffect(() => {
    if (selectedNodeId === previous.current) return;
    previous.current = selectedNodeId;
    if (!selectedNodeId) return;
    const node = steps.current.get(selectedNodeId);
    const root = scroller.current;
    if (!node || !root) return;
    const offset = node.offsetTop - root.offsetTop;
    if (Math.abs(root.scrollTop - offset) > root.clientHeight * 0.6) {
      root.scrollTo({ top: offset, behavior: "smooth" });
    }
  }, [selectedNodeId]);

  return (
    <div
      ref={scroller}
      aria-label="Forensics"
      className="h-full min-h-0 overflow-y-auto bg-[#fdfcf4] px-8 pb-6 pt-12"
    >
      {(duration || model) && (
        <div className="mx-auto mb-4 max-w-[62ch] font-mono text-[11px] leading-relaxed text-zinc-400">
          {duration && <p>{duration}</p>}
          {model && <p>{model}</p>}
        </div>
      )}
      <ol className="mx-auto max-w-[62ch]">
        {events.map((event) => (
          <li
            key={event.id}
            data-step={event.id}
            ref={(node) => {
              if (node) steps.current.set(event.id, node);
              else steps.current.delete(event.id);
            }}
            onClick={() => onSelectNode(event.id)}
            className="cursor-pointer py-2.5"
          >
            <p className="mb-1.5 text-[12px] leading-snug text-zinc-500">
              {explanations?.[event.id] ?? event.content ?? ""}
            </p>
            <pre
              className={`overflow-x-auto rounded border px-3 py-2 transition-colors ${
                event.id === selectedNodeId
                  ? "border-[#b06a38] bg-[#fdf7f1]"
                  : "border-zinc-200 bg-white"
              }`}
            >
              <code className="font-mono text-[12px] leading-relaxed text-zinc-800">
                {invocation(event)}
              </code>
            </pre>
            <span className="mt-1 block font-mono text-[10px] text-zinc-400">
              {localTime(event.timestamp)}
            </span>
          </li>
        ))}
      </ol>
      {handled.length > 0 && (
        <section aria-label="How we solved it" className="mx-auto max-w-[62ch]">
          <h2 className="mb-1 mt-8 border-t pt-6 text-[13px] font-semibold text-zinc-700">
            How we solved it
          </h2>
          <p className="mb-3 text-[12px] leading-snug text-zinc-500">
            {handled.length} step{handled.length === 1 ? "" : "s"} ran against this
            run. Commands are the ones the playbook executes on the monitoring host.
          </p>
          <ol>
            {handled.map((step) => (
              <li key={step.key} className="py-2.5">
                <p className="mb-1.5 text-[12px] leading-snug text-zinc-500">
                  {step.purpose}
                </p>
                <pre className="overflow-x-auto rounded border border-zinc-200 bg-white px-3 py-2">
                  <code className="whitespace-pre-wrap font-mono text-[12px] leading-relaxed text-zinc-800">
                    {step.command || `# ${step.title}`}
                  </code>
                </pre>
                <span className="mt-1 block font-mono text-[10px] text-zinc-400">
                  {localTime(step.at)} · {step.requestedBy}
                  {step.failed ? " · failed" : ""}
                </span>
              </li>
            ))}
          </ol>
        </section>
      )}
      <div aria-hidden="true" className="h-[55vh]" />
    </div>
  );
}
