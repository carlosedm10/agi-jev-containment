import type { PendingAction } from "@/dashboard/demo";
import type { Graph, GraphNode } from "@/graph/protocol";

export const NODE_WIDTH = 216;
export const NODE_HEIGHT = 104;
const COLUMN_GAP = 260;
const ROW_GAP = 142;

export type ActivityItem = {
  id: string;
  label: string;
  tool: string;
  runId: string | null;
  position: { x: number; y: number };
} & (
  | { kind: "structure" | "pending" }
  | { kind: "classified"; level: number; confidence: number }
);

export type ActivityLink = {
  id: string;
  source: string;
  target: string;
  pending: boolean;
};

function eventText(node: GraphNode, keys: string[], fallback: string) {
  for (const key of keys) {
    const value = node.event?.[key];
    if (typeof value === "string" && value.length > 0) return value;
  }
  return fallback;
}

export function layoutGraph(graph: Graph, pending: PendingAction | null) {
  const columns = new Map<string | null, { index: number; row: number }>();
  const nextPosition = (runId: string | null) => {
    let column = columns.get(runId);
    if (!column) {
      column = { index: columns.size, row: 0 };
      columns.set(runId, column);
    }
    return { x: column.index * COLUMN_GAP, y: ++column.row * ROW_GAP };
  };

  const nodes: ActivityItem[] = Array.from(graph.nodes.values(), (node) => {
    const root = node.id === graph.root;
    const base = {
      id: node.id,
      label: eventText(
        node,
        ["label", "kind", "event"],
        root ? "Activity entry point" : (node.run_id ?? node.id),
      ),
      tool: eventText(node, ["tool", "target", "event"], ""),
      runId: node.run_id,
      position: root ? { x: COLUMN_GAP / 2, y: 0 } : nextPosition(node.run_id),
    };
    return node.event === null
      ? { ...base, kind: "structure" }
      : {
          ...base,
          kind: "classified",
          level: node.level,
          confidence: node.threshold,
        };
  });

  if (pending && !graph.nodes.has(pending.id)) {
    nodes.push({
      id: pending.id,
      label: pending.label,
      tool: pending.tool,
      runId: pending.run_id,
      position: nextPosition(pending.run_id),
      kind: "pending",
    });
  }

  const positions = new Map(nodes.map((node) => [node.id, node.position]));
  const links = new Map<string, ActivityLink>();
  for (const node of graph.nodes.values()) {
    for (const neighbor of node.neighbors) {
      if (neighbor === node.id || !graph.nodes.has(neighbor)) continue;
      const pair = [node.id, neighbor].sort();
      const id = JSON.stringify(pair);
      const a = positions.get(pair[0])!;
      const b = positions.get(pair[1])!;
      const forward = a.y < b.y || (a.y === b.y && a.x <= b.x);
      links.set(id, {
        id,
        source: pair[forward ? 0 : 1],
        target: pair[forward ? 1 : 0],
        pending: false,
      });
    }
  }
  if (
    pending &&
    !graph.nodes.has(pending.id) &&
    graph.nodes.has(pending.parentId)
  ) {
    const id = JSON.stringify([pending.parentId, pending.id].sort());
    links.set(id, {
      id,
      source: pending.parentId,
      target: pending.id,
      pending: true,
    });
  }
  return {
    nodes,
    links: Array.from(links.values()).sort((a, b) => a.id.localeCompare(b.id)),
  };
}
