import type { Log } from "@/components/ui/interactive-logs-table";
import type { SafeAction } from "@/dashboard/demo";
import { eventText } from "@/dashboard/graph-layout";
import type { Graph, GraphNode } from "@/graph/protocol";

function classified(graph: Graph): GraphNode[] {
  return Array.from(graph.nodes.values())
    .filter((node) => node.event !== null && node.run_id !== null)
    .sort((a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? ""));
}

function eventDetails(node: GraphNode) {
  const details: { label: string; meta: string }[] = [];
  for (const key of ["summary", "tool", "kind"] as const) {
    const value = node.event?.[key];
    if (typeof value === "string" && value.length > 0) {
      details.push({ label: key, meta: value });
    }
  }
  return details;
}

export function actionsFromGraph(graph: Graph): SafeAction[] {
  return classified(graph).map((node) => ({
    id: node.id,
    nodeId: node.id,
    title: eventText(node, ["label", "kind", "event"], node.id),
    source: node.action_id === null ? "Monitor" : "Host playbook",
    status: "done",
    level: node.level,
    startedAt: node.created_at ?? "",
    details: [
      { label: "Intent", meta: node.intent ?? "—" },
      { label: "Confidence", meta: `${Math.round(node.threshold * 100)}%` },
      { label: "Run", meta: node.run_id ?? "—" },
      ...(node.action_id === null
        ? []
        : [{ label: "Response trace", meta: node.action_id }]),
      ...eventDetails(node),
    ],
  }));
}

export function logsFromGraph(graph: Graph): Log[] {
  return classified(graph).map((node) => ({
    id: `log-${node.id}`,
    timestamp: node.created_at ?? "",
    level: node.level >= 3 ? "error" : node.level >= 1 ? "warning" : "info",
    service: `run:${node.run_id}`,
    message: eventText(node, ["label", "kind", "event"], node.id),
    duration: "—",
    status: `L${node.level}`,
    tags: [node.run_id ?? "", node.id, node.intent ?? ""].filter(Boolean),
  }));
}
