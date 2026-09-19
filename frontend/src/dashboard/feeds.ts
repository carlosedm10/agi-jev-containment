import type { Log } from "@/components/ui/interactive-logs-table";
import type { SafeAction } from "@/dashboard/demo";
import { eventTarget, eventText } from "@/dashboard/graph-layout";
import type { Graph, GraphNode } from "@/graph/protocol";
import { ACTION_STATUS_LABEL, CALL_LABEL } from "@/ladder/copy";
import type { ActionTransition, IncidentState } from "@/ladder/types";
import { actionModeLabel } from "@/ladder/wallboard";

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
    service: [event.agent, event.channel, event.run_id]
      .filter(Boolean)
      .join(" · "),
    message: `stdout F ${JSON.stringify({
      event: event.kind,
      event_id: event.id,
      run_id: event.run_id,
      tool: event.tool,
      target: event.target,
      phase: event.phase,
      level: event.level,
    })}`,
    duration: "—",
    status: event.level === null ? "Recorded" : `L${event.level}`,
    tags: [event.run_id, event.id],
  }));
}

function classified(graph: Graph): GraphNode[] {
  return Array.from(graph.nodes.values())
    .filter((node) => node.event !== null && node.run_id !== null)
    .sort((a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? ""));
}

export function actionsFromIncident(incident: IncidentState): SafeAction[] {
  const latest = new Map<string, ActionTransition>();
  for (const action of incident.actions) latest.set(action.action_id, action);
  return [...latest.values()].map((action) => ({
    id: action.action_id,
    nodeId: `run:${incident.incident_id}`,
    title: action.name,
    source: action.ladder_level === null ? "HappyRobot" : "Host playbook",
    status: action.status === "ok" ? "done" : action.status,
    level: action.level,
    startedAt: action.timestamp,
    details: [
      { label: "Status", meta: ACTION_STATUS_LABEL[action.status] },
      { label: "Mode", meta: actionModeLabel(action.mode) },
      ...(action.ladder_level === null
        ? []
        : [{ label: "Ladder level", meta: `L${action.ladder_level}` }]),
      ...(action.call_status === null
        ? []
        : [{ label: "Call", meta: CALL_LABEL[action.call_status] }]),
      ...(action.detail === null
        ? []
        : [{ label: "Detail", meta: action.detail }]),
      ...(action.error_code === null
        ? []
        : [{ label: "Error", meta: action.error_code }]),
      ...(action.ladder_level !== null
        ? []
        : incident.actions
            .filter((entry) => entry.action_id === action.action_id)
            .map((entry) => ({
              label: `${new Date(entry.timestamp).toLocaleTimeString("en-GB", { timeZone: "UTC" })} UTC · ${entry.call_status ? CALL_LABEL[entry.call_status] : ACTION_STATUS_LABEL[entry.status]}`,
              meta:
                [entry.detail, entry.error_code].filter(Boolean).join(" · ") ||
                ACTION_STATUS_LABEL[entry.status],
            }))),
    ],
  }));
}

function logLine(node: GraphNode): string {
  const kind = eventText(node, ["kind", "event"], "event");
  const tool = eventText(node, ["tool"], "");
  const target = eventTarget(node);
  const phase = eventText(node, ["phase"], "");
  return `stdout F ${JSON.stringify({
    event: kind,
    ...(tool ? { tool } : {}),
    ...(target ? { target } : {}),
    ...(phase ? { phase } : {}),
    event_id: eventText(node, ["id", "event_id"], node.id),
    level: node.level,
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
      node.run_id,
    ]
      .filter(Boolean)
      .join(" · "),
    message: logLine(node),
    duration: "—",
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
