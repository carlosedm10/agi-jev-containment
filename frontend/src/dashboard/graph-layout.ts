import type { PendingAction } from "@/dashboard/demo";
import type { Graph, GraphNode } from "@/graph/protocol";
import { actionToolName, PROTECTIVE_TOOLS } from "@/ladder/tools";

export const NODE_WIDTH = 240;
export const NODE_HEIGHT = 132;

export type ActivityItem = {
  id: string;
  label: string;
  tool: string;
  context?: string;
  runId: string | null;
  position: { x: number; y: number };
  /** The protective tool this node triggered, when its classification ran a playbook. */
  actionTool?: { name: string; short: string; title: string };
} & (
  | { kind: "structure" | "pending" | "recorded" }
  | { kind: "classified"; level: number; confidence: number; actionLevel?: number }
);

type ActivityLink = {
  id: string;
  source: string;
  target: string;
  pending: boolean;
};

export function eventText(
  node: Pick<GraphNode, "event">,
  keys: string[],
  fallback: string,
) {
  for (const key of keys) {
    const value = node.event?.[key];
    if (typeof value === "string" && value.length > 0) return value;
  }
  return fallback;
}

export function eventLabel(node: Pick<GraphNode, "event">) {
  const explicit = eventText(node, ["label"], "");
  if (explicit) return explicit;
  const kind = eventText(node, ["kind", "event"], "");
  const target = eventTarget(node);
  const name = target.split("/").filter(Boolean).at(-1) ?? "";
  const labels: Record<string, string> = {
    file_read: "Read file",
    file_write: "Write file",
    tool_read: "Read information",
    tool_write: "Update information",
    shell_command: "Run a terminal command",
    register_tool: "Register a new tool",
    run_tool: "Run a tool",
    memory_read: "Read agent memory",
    memory_write: "Update agent memory",
    assistant_message: "Reply to the user",
    utterance: "Respond to the conversation",
    policy_decision: "Check the request against policy",
    handoff: "Hand off the task",
    notification: "Send a notification",
  };
  if (kind === "network_request") {
    const host = target.replace(/^https?:\/\//, "").split("/")[0];
    return host ? `Send request to ${host}` : "Send a network request";
  }
  if (labels[kind]) {
    return name &&
      ["file_read", "file_write", "tool_read", "tool_write"].includes(kind)
      ? `${labels[kind]}: ${name}`
      : labels[kind];
  }
  return (
    eventText(node, ["summary", "content"], "") ||
    eventText(node, ["kind", "event"], "Agent action").replaceAll("_", " ")
  );
}

export function eventTarget(node: Pick<GraphNode, "event">) {
  return eventText(node, ["target", "path", "url"], "");
}

export function actionLevel(event: GraphNode["event"]): number | undefined {
  const metadata = event?.metadata;
  const value = metadata && typeof metadata === "object" ? (metadata as Record<string, unknown>).action_level : undefined;
  return typeof value === "number" && Number.isInteger(value) && value >= 0 && value <= 5 ? value : undefined;
}

export function latestRunNode(graph: Graph, runId: string): string | null {
  let latest = graph.nodes.has(`run:${runId}`) ? `run:${runId}` : graph.root;
  let sequence = 0;
  for (const node of graph.nodes.values()) {
    const state = node.run_states?.[runId];
    const event = state?.event ?? node.event;
    const eventId = String(event?.id ?? event?.event_id ?? "");
    const belongs =
      state || node.run_id === runId || eventId.startsWith(`${runId}:e`);
    if (!belongs) continue;
    const next =
      typeof event?.sequence === "number"
        ? event.sequence
        : eventId.startsWith(`${runId}:e`)
          ? Number(eventId.slice(runId.length + 2))
          : 0;
    if (Number.isInteger(next) && next > sequence) {
      latest = node.id;
      sequence = next;
    }
  }
  return latest;
}

function computeDepth(graph: Graph) {
  const depth = new Map<string, number>();
  const rootId = graph.root;
  if (rootId && graph.nodes.has(rootId)) {
    const queue: string[] = [rootId];
    depth.set(rootId, 0);
    while (queue.length) {
      const current = queue.shift()!;
      const currentDepth = depth.get(current)!;
      const node = graph.nodes.get(current);
      if (!node) continue;
      for (const neighbor of node.neighbors) {
        if (depth.has(neighbor) || !graph.nodes.has(neighbor)) continue;
        depth.set(neighbor, currentDepth + 1);
        queue.push(neighbor);
      }
    }
  }
  return depth;
}

/** Name the playbook a node set off, so an acting node never shows a bare action id. */
export function protectiveTool(actionId: string | null) {
  const name = actionToolName(actionId);
  if (name === null) return undefined;
  const { short, title } = PROTECTIVE_TOOLS[name];
  return { name, short, title };
}

export function layoutGraph(graph: Graph, pending: PendingAction | null) {
  // BFS depth from the root so shared action nodes and cycles get one stable rank.
  const depth = computeDepth(graph);
  const maxDepth = depth.size ? Math.max(...depth.values()) : 0;

  // Preserve insertion order around each depth's ring.
  const rankGroups = new Map<number, string[]>();
  for (const id of graph.nodes.keys()) {
    const d = depth.get(id) ?? maxDepth + 1;
    if (!rankGroups.has(d)) rankGroups.set(d, []);
    rankGroups.get(d)!.push(id);
  }

  if (pending && !graph.nodes.has(pending.id)) {
    const d = (depth.get(pending.parentId) ?? maxDepth) + 1;
    if (!rankGroups.has(d)) rankGroups.set(d, []);
    rankGroups.get(d)!.push(pending.id);
  }

  const positions = new Map<string, { x: number; y: number }>();
  const spacing = Math.hypot(NODE_WIDTH, NODE_HEIGHT) + 12;
  let radius = 0;
  for (const [d, group] of [...rankGroups].sort(([a], [b]) => a - b)) {
    // Spill crowded depths into more rings instead of pushing every node away from the root.
    for (let offset = 0; offset < group.length;) {
      const capacity = Math.max(
        6,
        Math.floor((2 * Math.PI * radius) / spacing),
      );
      const ids = group.slice(offset, offset + capacity);
      offset += ids.length;
      // Chord spacing keeps cards apart, even on crowded rings or across depths.
      radius =
        d === 0 && ids.length === 1
          ? 0
          : Math.max(
              radius === 0
                ? Math.max(
                    ...ids.map((_, i) => {
                      const angle =
                        -Math.PI / 2 +
                        (i * 2 * Math.PI) / ids.length +
                        d * 0.35;
                      return Math.min(
                        (NODE_WIDTH + 16) / Math.abs(Math.cos(angle)),
                        (NODE_HEIGHT + 16) / Math.abs(Math.sin(angle)),
                      );
                    }),
                  )
                : radius + spacing,
              ids.length > 1
                ? spacing / (2 * Math.sin(Math.PI / ids.length))
                : 0,
            );
      ids.forEach((id, i) => {
        const angle = -Math.PI / 2 + (i * 2 * Math.PI) / ids.length + d * 0.35;
        positions.set(id, {
          x: Math.cos(angle) * radius - NODE_WIDTH / 2,
          y: Math.sin(angle) * radius - NODE_HEIGHT / 2,
        });
      });
    }
  }

  const nodes: ActivityItem[] = Array.from(graph.nodes.values(), (node) => {
    const root = node.id === graph.root;
    const base = {
      id: node.id,
      label: node.event
        ? eventLabel(node)
        : root
          ? "Agent activity"
          : (node.run_id ?? node.id),
      tool: [eventText(node, ["tool", "kind", "event"], ""), eventTarget(node)]
        .filter(Boolean)
        .join(" · "),
      context: node.event
        ? [
            eventText(node, ["agent", "channel"], node.run_id ?? ""),
            node.visit_count > 1
              ? `${node.visit_count} visits · ${node.run_ids.length} runs`
              : "",
          ]
            .filter(Boolean)
            .join(" · ")
        : root
          ? `${graph.nodes.size} nodes`
          : "Run entry point",
      runId: node.run_id,
      position: positions.get(node.id)!,
      actionTool: protectiveTool(node.action_id),
    };
    return node.event === null
      ? { ...base, kind: "structure" }
      : {
          ...base,
          kind: "classified",
          level: node.level,
          actionLevel: actionLevel(node.event),
          confidence: node.threshold,
        };
  });

  if (pending && !graph.nodes.has(pending.id)) {
    nodes.push({
      id: pending.id,
      label: pending.label,
      tool: pending.tool,
      runId: pending.run_id,
      position: positions.get(pending.id)!,
      kind: "pending",
    });
  }

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
