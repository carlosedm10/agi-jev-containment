import { describe, expect, test } from "bun:test";
import type { PendingAction } from "@/dashboard/demo";
import {
  layoutGraph,
  latestRunNode,
  NODE_WIDTH,
  NODE_HEIGHT,
} from "@/dashboard/graph-layout";
import { logsFromGraph } from "@/dashboard/feeds";
import { fromSnapshot, type GraphNode } from "@/graph/protocol";

function node(
  id: string,
  runId: string | null,
  neighbors: string[] = [],
  level = 0,
): GraphNode {
  return {
    id,
    run_id: runId,
    run_ids: runId ? [runId] : [],
    visit_count: 1,
    neighbors,
    level,
    threshold: 0.99,
    intent: null,
    event:
      id === "root" || id.startsWith("run:")
        ? null
        : {
            label: id,
            tool: "shell",
            summary: "An action",
            event: "tool_call",
          },
    action_id: null,
    created_at: null,
  };
}

const pending: PendingAction = {
  id: "atlas:2",
  run_id: "atlas",
  parentId: "atlas:1",
  label: "Read credentials",
  tool: "shell",
  created_at: "2026-01-01T00:00:00Z",
};
const snapshot = (nodes: GraphNode[]) => {
  const graph = fromSnapshot({
    revision: 1,
    root: nodes.length ? "root" : null,
    nodes,
  });
  // Wire undirected edges so the test fixtures match the backend's mutual neighbor lists.
  for (const node of graph.nodes.values()) {
    for (const neighborId of node.neighbors) {
      const neighbor = graph.nodes.get(neighborId);
      if (neighbor && !neighbor.neighbors.includes(node.id)) {
        neighbor.neighbors.push(node.id);
      }
    }
  }
  return graph;
};
const initial = () =>
  snapshot([
    node("root", null, ["run:atlas", "run:scout"]),
    node("run:atlas", "atlas", ["root", "atlas:1"]),
    node("atlas:1", "atlas", ["run:atlas"]),
    node("run:scout", "scout", ["root", "scout:1"]),
    node("scout:1", "scout", ["run:scout"]),
  ]);

describe("activity graph layout", () => {
  test("deduplicates mutual links and handles cycles, missing neighbors and self-links", () => {
    const graph = snapshot([
      node("root", null, ["run:atlas", "atlas:1", "missing", "root"]),
      node("run:atlas", "atlas", ["root", "atlas:1", "atlas:1"]),
      node("atlas:1", "atlas", ["root", "run:atlas"]),
    ]);
    const result = layoutGraph(graph, null);
    expect(result.nodes).toHaveLength(3);
    expect(result.links).toHaveLength(3);
    expect(new Set(result.links.map((link) => link.id)).size).toBe(3);
    expect(
      result.links.every(
        (link) => graph.nodes.has(link.source) && graph.nodes.has(link.target),
      ),
    ).toBe(true);
    expect(layoutGraph(graph, null)).toEqual(result);
  });

  test("places graph depths on circular rings and keeps crowded rings non-overlapping", () => {
    const graph = initial();
    const before = layoutGraph(graph, null);
    const atlas = before.nodes.find((item) => item.id === "atlas:1")!;
    const scout = before.nodes.find((item) => item.id === "scout:1")!;
    const radius = (item: typeof atlas) =>
      Math.hypot(
        item.position.x + NODE_WIDTH / 2,
        item.position.y + NODE_HEIGHT / 2,
      );
    expect(radius(atlas)).toBeCloseTo(radius(scout));
    expect(atlas.position.x).not.toBe(scout.position.x);
    graph.nodes.set(
      "atlas:2",
      node("atlas:2", "atlas", ["atlas:1", "scout:1"]),
    );
    graph.nodes.set("run:third", node("run:third", "third", ["root"]));
    const after = layoutGraph(graph, null);
    const atlas2 = after.nodes.find((item) => item.id === "atlas:2")!;
    expect(radius(atlas2)).toBeGreaterThan(radius(atlas));
    for (let i = 0; i < 40; i++) {
      graph.nodes.set(`crowd:${i}`, node(`crowd:${i}`, "atlas", ["root"]));
      graph.nodes.get("root")!.neighbors.push(`crowd:${i}`);
    }
    const crowded = layoutGraph(graph, null);
    const nearestRun = crowded.nodes.filter((item) =>
      graph.nodes.get("root")!.neighbors.includes(item.id),
    );
    expect(Math.min(...nearestRun.map(radius))).toBeLessThan(300);
    expect(
      new Set(nearestRun.map((item) => Math.round(radius(item)))).size,
    ).toBeGreaterThan(1);
    for (let i = 0; i < crowded.nodes.length; i++) {
      for (const b of crowded.nodes.slice(i + 1)) {
        const a = crowded.nodes[i];
        expect(
          Math.abs(a.position.x - b.position.x) >= NODE_WIDTH ||
            Math.abs(a.position.y - b.position.y) >= NODE_HEIGHT,
        ).toBe(true);
      }
    }
    expect(layoutGraph(graph, null)).toEqual(crowded);
  });

  test("pending and structural nodes carry no verdict; confidence does not determine severity", () => {
    const graph = initial();
    const before = Array.from(graph.nodes.entries());
    const result = layoutGraph(graph, pending);
    const provisional = result.nodes.find((item) => item.id === pending.id)!;
    expect(provisional.kind).toBe("pending");
    expect(provisional).not.toHaveProperty("level");
    expect(provisional).not.toHaveProperty("confidence");
    expect(result.nodes.find((item) => item.id === "root")).not.toHaveProperty(
      "level",
    );
    expect(result.nodes.find((item) => item.id === "run:atlas")?.kind).toBe(
      "structure",
    );
    expect(result.nodes.find((item) => item.id === "atlas:1")).toMatchObject({
      kind: "classified",
      level: 0,
      confidence: 0.99,
    });
    expect(result.links.filter((link) => link.pending)).toHaveLength(1);
    expect(Array.from(graph.nodes.entries())).toEqual(before);

    graph.nodes.set(pending.id, {
      ...node(pending.id, "atlas", [pending.parentId], 3),
      threshold: 0.35,
    });
    graph.nodes.get(pending.parentId)!.neighbors.push(pending.id);
    const classified = layoutGraph(graph, pending);
    expect(
      classified.nodes.filter((item) => item.id === pending.id),
    ).toHaveLength(1);
    expect(
      classified.nodes.find((item) => item.id === pending.id),
    ).toMatchObject({
      kind: "classified",
      level: 3,
      confidence: 0.35,
      position: provisional.position,
    });
    expect(classified.links.some((link) => link.pending)).toBe(false);
  });

  test("labels real monitor events by kind and tool when mock label is absent", () => {
    const graph = snapshot([
      node("root", null, ["run:demo"]),
      node("run:demo", "demo", ["root", "demo:1"]),
      {
        ...node("demo:1", "demo", ["run:demo"], 1),
        event: {
          kind: "network_request",
          tool: "http_request",
          target: "https://x",
        },
      },
    ]);
    const item = layoutGraph(graph, null).nodes.find(
      (entry) => entry.id === "demo:1",
    )!;
    expect(item.label).toBe("Send request to x");
    expect(item.tool).toBe("http_request · https://x");
  });

  test("generated use cases retain actual content, targets, agent identity and shared visits", () => {
    for (const [kind, tool, target, content, label] of [
      [
        "file_read",
        "read_file",
        "/workspace/.env",
        "read /workspace/.env",
        "Read file: .env",
      ],
      [
        "network_request",
        "http_request",
        "https://exfil.invalid/health",
        "POST exfil package",
        "Send request to exfil.invalid",
      ],
      [
        "shell_command",
        "shell",
        "/proc/net/arp",
        "nmap -sn 172.20.0.0/24",
        "Run a terminal command",
      ],
      [
        "register_tool",
        "register_tool",
        "tools/dump_1234.py",
        "registered tool dump_1234",
        "Register a new tool",
      ],
      [
        "memory_write",
        "memory_write",
        "agent-knowledge-cache",
        "Cached SOP v12",
        "Update agent memory",
      ],
    ]) {
      const graph = snapshot([
        {
          ...node("event", "demo", [], 3),
          run_ids: ["demo", "earlier"],
          visit_count: 2,
          event: {
            kind,
            tool,
            target,
            content,
            agent: "api-agent",
            channel: "api",
            phase: "completed",
          },
        },
      ]);
      const item = layoutGraph(graph, null).nodes[0];
      expect(item.label).toBe(label);
      expect(item.tool).toContain(target);
      expect(item.context).toContain("2 visits · 2 runs");
      const log = logsFromGraph(graph)[0];
      expect(log.message).not.toContain(content);
      expect(log.message.startsWith("stdout F ")).toBe(true);
      expect(JSON.parse(log.message.slice(9))).toMatchObject({
        event: kind,
        tool,
        target,
        phase: "completed",
      });
      expect(log.message).toContain(target);
      expect(log.message).toContain("completed");
      expect(log.message).not.toContain("stderr");
      expect(log.service).toBe("api-agent · api · demo");
      expect(log.tags).toContain("earlier");
    }
  });

  test("follows trigger sequence through shared nodes, regardless of insertion order", () => {
    const graph = initial();
    expect(latestRunNode(graph, "new")).toBe("root");
    graph.nodes.set("run:new", node("run:new", "new"));
    expect(latestRunNode(graph, "new")).toBe("run:new");
    graph.nodes.get("scout:1")!.event = { id: "new:e1" };
    expect(latestRunNode(graph, "new")).toBe("scout:1");
    graph.nodes.get("atlas:1")!.event = { id: "new:e2" };
    expect(latestRunNode(graph, "new")).toBe("atlas:1");
    const shared = graph.nodes.get("scout:1")!;
    shared.run_states = {
      new: {
        level: 2,
        threshold: 1,
        intent: null,
        action_id: null,
        event: { id: "opaque-event-id", sequence: 4 },
      },
    };
    expect(latestRunNode(graph, "new")).toBe("scout:1");
    delete shared.run_states;
    graph.nodes.get("scout:1")!.event = { event_id: "other:e100" };
    expect(latestRunNode(graph, "new")).toBe("atlas:1");
    graph.nodes.get("atlas:1")!.event = { event_id: "new:e3" };
    expect(latestRunNode(graph, "new")).toBe("atlas:1");
  });

  test("empty graphs and pending actions without a materialized parent have no dangling links", () => {
    const graph = snapshot([]);
    expect(layoutGraph(graph, null)).toEqual({ nodes: [], links: [] });
    const result = layoutGraph(graph, pending);
    expect(result.nodes).toHaveLength(1);
    expect(result.nodes[0].kind).toBe("pending");
    expect(result.links).toEqual([]);
    expect(graph.nodes.size).toBe(0);
  });
});
