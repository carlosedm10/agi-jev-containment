import type { Log } from "@/components/ui/interactive-logs-table";
import type { SafeAction } from "@/dashboard/demo";
import { eventTarget, eventText } from "@/dashboard/graph-layout";
import type { Graph, GraphNode } from "@/graph/protocol";
import { ACTION_STATUS_LABEL, CALL_LABEL } from "@/ladder/copy";
import { PROTECTIVE_TOOLS as COUNTER_TOOLS } from "@/ladder/tools";
import type { ActionTransition, IncidentState } from "@/ladder/types";
import { localTime } from "@/lib/time";

export type TraceLogEvent = {
  id: string;
  run_id: string;
  timestamp: string;
  kind: string;
  phase?: string;
  agent?: string;
  channel?: string;
  tool?: string;
  target?: string;
  level: number | null;
};

/** The full record behind a row, shown only when someone opens it. */
function logRaw(fields: Record<string, unknown>): string {
  return `stdout F ${JSON.stringify(
    Object.fromEntries(
      Object.entries(fields).filter(
        ([, value]) => value !== "" && value !== null && value !== undefined,
      ),
    ),
  )}`;
}

export function logsFromEvents(events: TraceLogEvent[]): Log[] {
  return events.map((event) => ({
    id: JSON.stringify([event.run_id, event.id]),
    timestamp: event.timestamp,
    level:
      (event.level ?? 0) >= 3
        ? "error"
        : (event.level ?? 0) >= 1
          ? "warning"
          : "info",
    // `agent` already ends in the run id, so listing it again just eats the width.
    service: [event.agent, event.channel].filter(Boolean).join(" · "),
    message: `stdout F ${JSON.stringify({
      event: event.kind,
      ...(event.tool ? { tool: event.tool } : {}),
      ...(event.target ? { target: event.target } : {}),
      // Every ordinary step is completed; only an unfinished one is worth the width.
      ...(event.phase && event.phase !== "completed"
        ? { phase: event.phase }
        : {}),
    })}`,
    // Opening a row must add something: the full record, ids and level included.
    raw: logRaw({
      event: event.kind,
      event_id: event.id,
      run_id: event.run_id,
      tool: event.tool,
      target: event.target,
      phase: event.phase,
      level: event.level,
    }),
    status: event.level === null ? "Recorded" : `L${event.level}`,
    tags: [event.run_id, event.id],
  }));
}

function classified(graph: Graph): GraphNode[] {
  return Array.from(graph.nodes.values())
    .filter((node) => node.event !== null && node.run_id !== null)
    .sort((a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? ""));
}

/**
 * A spoken turn the pager journalled while the line was open.
 *
 * The text is whatever was said on the call, so it is displayed and never
 * interpreted; the decision itself arrives through the authenticated webhook.
 */
/**
 * The journal prefixes every detail with `elapsed_ms=… provider_run_id=…` before its
 * JSON, so the payload starts partway through the line. Parsing the whole string
 * throws and the row falls back to printing raw JSON at the reader.
 */
function payload(detail: string | null): Record<string, unknown> | null {
  if (!detail) return null;
  const start = detail.indexOf("{");
  if (start < 0) return null;
  try {
    const parsed: unknown = JSON.parse(detail.slice(start));
    return typeof parsed === "object" && parsed !== null && !Array.isArray(parsed)
      ? (parsed as Record<string, unknown>)
      : null;
  } catch {
    return null;
  }
}

/**
 * A spoken turn, labelled by who said it. The human's side carries the name we rang.
 * The text is whatever was said on the line, so it is displayed and never
 * interpreted; the decision itself arrives through the authenticated webhook.
 */
function speechTurn(detail: string | null): { who: string; said: string } | null {
  const line = payload(detail);
  if (!line || line.stage !== "speech" || typeof line.said !== "string") return null;
  const name = typeof line.name === "string" && line.name ? line.name : null;
  return {
    who: line.who === "oncall" ? (name ?? "On-call") : "Support",
    said: line.said,
  };
}

const CALL_STAGE: Record<string, string> = {
  webhook_request: "Placing the call",
  webhook_accepted: "Call accepted by the provider",
  webhook_retry: "Retrying the call",
  retry: "Calling again",
  error: "Call failed",
};

/**
 * Turn the machine evidence into a line a person can read at a glance.
 *
 * Anything this does not recognise is returned unchanged rather than dropped: this is
 * an audit surface, and losing evidence is worse than showing it raw.
 */
function evidenceLine(detail: string | null): string | null {
  if (!detail) return null;
  const staged = /stage=([a-z_]+)/.exec(detail);
  if (staged && CALL_STAGE[staged[1]]) return CALL_STAGE[staged[1]];
  const line = payload(detail);
  if (!line) return detail;
  if (line.stage === "call_state") {
    const duration =
      typeof line.duration === "number" && line.duration > 0
        ? ` · ${line.duration}s`
        : "";
    const ended =
      typeof line.call_end_event === "string" &&
      line.call_end_event !== "unknown"
        ? ` · ${String(line.call_end_event).replaceAll("_", " ")}`
        : "";
    const status =
      typeof line.call_status === "string" ? line.call_status : "in progress";
    return `Call ${status.replaceAll("-", " ")}${duration}${ended}`;
  }
  return detail;
}

export function actionsFromIncident(incident: IncidentState): SafeAction[] {
  // The feed casts whatever the API returned; a body without transitions must render
  // as "nothing ran", not throw the panel away.
  if (!Array.isArray(incident?.actions)) return [];
  const latest = new Map<string, ActionTransition>();
  for (const action of incident.actions) latest.set(action.action_id, action);
  return [...latest.values()].map((action) => ({
    id: action.action_id,
    nodeId: `run:${incident.incident_id}`,
    title: COUNTER_TOOLS[action.name]?.title ?? action.name,
    source: action.ladder_level === null ? "HappyRobot" : "Host playbook",
    status: action.status === "ok" ? "done" : action.status,
    level: action.level,
    startedAt: action.timestamp,
    details: [
      { label: "Tool", meta: action.name },
      {
        label: "Requested by",
        meta:
          action.source === "oncall_phone"
            ? "On-call, authorized during the call"
            : "Monitor",
      },
      ...(COUNTER_TOOLS[action.name] ? [
        { label: "Purpose", meta: COUNTER_TOOLS[action.name].purpose },
        ...(COUNTER_TOOLS[action.name].command ? [{ label: "Reference commands", meta: COUNTER_TOOLS[action.name].command! }] : [{ label: "Command", meta: "No shell command; application-level monitoring step." }]),
      ] : []),
      ...(action.ladder_level === null
        ? []
        : [{ label: "Ladder level", meta: `L${action.ladder_level}` }]),
      ...(action.call_status === null
        ? []
        : [{ label: "Call", meta: CALL_LABEL[action.call_status] }]),
      // The latest transition may be a spoken turn; the conversation is listed below
      // in order, so repeating it here as raw JSON helps nobody.
      ...(action.detail === null || speechTurn(action.detail) !== null
        ? []
        : [{ label: "Detail", meta: evidenceLine(action.detail) ?? action.detail }]),
      ...(action.error_code === null
        ? []
        : [{ label: "Error", meta: action.error_code }]),
      ...(action.ladder_level !== null
        ? []
        : incident.actions
            .filter((entry) => entry.action_id === action.action_id)
            .map((entry) => {
              const turn = speechTurn(entry.detail);
              // What was actually said, attributed to whoever said it.
              if (turn) return { label: turn.who, meta: turn.said };
              return {
                label: `${localTime(entry.timestamp)} · ${entry.call_status ? CALL_LABEL[entry.call_status] : ACTION_STATUS_LABEL[entry.status]}`,
                meta:
                  [evidenceLine(entry.detail), entry.error_code]
                    .filter(Boolean)
                    .join(" · ") || ACTION_STATUS_LABEL[entry.status],
              };
            })),
    ],
  }));
}

function logLine(node: GraphNode): string {
  const kind = eventText(node, ["kind", "event"], "event");
  const tool = eventText(node, ["tool"], "");
  const target = eventTarget(node);
  const phase = eventText(node, ["phase"], "");
  // Same shape as the live feed: the row, the source line and the tags already carry
  // the ids and the level, so the line itself only says what the step did.
  return `stdout F ${JSON.stringify({
    event: kind,
    ...(tool ? { tool } : {}),
    ...(target ? { target } : {}),
    ...(phase && phase !== "completed" ? { phase } : {}),
    ...(node.intent ? { intent: node.intent } : {}),
  })}`;
}

export function logsFromGraph(graph: Graph): Log[] {
  return classified(graph).map((node) => ({
    id: `log-${node.id}`,
    timestamp: node.created_at ?? "",
    level: node.level >= 3 ? "error" : node.level >= 1 ? "warning" : "info",
    service: [
      eventText(node, ["agent"], "Monitor"),
      eventText(node, ["channel"], ""),
    ]
      .filter(Boolean)
      .join(" · "),
    message: logLine(node),
    // Opening a row must add something: the full record, ids and level included.
    raw: logRaw({
      event: eventText(node, ["kind", "event"], "event"),
      event_id: eventText(node, ["id", "event_id"], node.id),
      run_id: node.run_id,
      tool: eventText(node, ["tool"], ""),
      target: eventTarget(node),
      phase: eventText(node, ["phase"], ""),
      level: node.level,
      ...(node.intent ? { intent: node.intent } : {}),
    }),
    status: `L${node.level}`,
    tags: [
      ...node.run_ids,
      eventText(node, ["id", "event_id"], node.id),
      node.intent ?? "",
      eventText(node, ["scenario"], ""),
      eventText(node, ["trust"], ""),
      node.visit_count > 1 ? `${node.visit_count} visits (shared action)` : "",
    ].filter(Boolean),
  }));
}
