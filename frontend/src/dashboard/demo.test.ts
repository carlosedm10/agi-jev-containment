import { describe, expect, test } from "bun:test";

import { DEMO_END, getDemoFrame } from "@/dashboard/demo";

describe("mock monitoring timeline", () => {
  test("keeps unreviewed events out of the classified graph", () => {
    const waiting = getDemoFrame(1);
    expect(waiting.pending?.id).toBe("atlas:1");
    expect(waiting.graph.nodes.has("atlas:1")).toBe(false);
    expect(waiting.actions).toHaveLength(0);
    const reviewed = getDemoFrame(2);
    expect(reviewed.pending).toBeNull();
    expect(reviewed.graph.nodes.get("atlas:1")?.level).toBe(0);
    expect(reviewed.graph.nodes.get("atlas:1")?.threshold).toBeGreaterThan(0.9);
  });

  test("only starts playbooks after the corresponding Jev verdict", () => {
    expect(getDemoFrame(11).actions.some((a) => a.id === "tag:atlas")).toBe(
      false,
    );
    expect(getDemoFrame(12).actions.find((a) => a.id === "tag:atlas")?.status).toBe(
      "running",
    );
    expect(getDemoFrame(12).actions.some((a) => a.id === "contain:atlas")).toBe(
      false,
    );
    expect(
      getDemoFrame(13).actions.find((a) => a.id === "contain:atlas")?.status,
    ).toBe("running");
    expect(getDemoFrame(14).actions.some((a) => a.id === "cut-egress")).toBe(false);
    expect(getDemoFrame(15).actions.find((a) => a.id === "cut-egress")?.status).toBe(
      "running",
    );
    expect(getDemoFrame(15).actions.some((a) => a.id === "page:atlas")).toBe(false);
    expect(
      getDemoFrame(16).actions.find((a) => a.id === "cut-egress")?.status,
    ).toBe("done");
    expect(
      getDemoFrame(16).actions.find((a) => a.id === "page:atlas")?.status,
    ).toBe("running");
  });

  test("preserves mutual adjacency and trace references through every frame", () => {
    let previousLevel = 0;
    for (let tick = 0; tick <= DEMO_END; tick++) {
      const { graph, actions, logs } = getDemoFrame(tick);
      for (const node of graph.nodes.values()) {
        for (const neighbor of node.neighbors) {
          expect(graph.nodes.get(neighbor)?.neighbors).toContain(node.id);
        }
      }
      for (const action of actions)
        expect(graph.nodes.has(action.nodeId)).toBe(true);
      expect(new Set(logs.map((log) => log.id)).size).toBe(logs.length);
      const level = Math.max(
        0,
        ...Array.from(graph.nodes.values(), (node) => node.level),
      );
      expect(level).toBeGreaterThanOrEqual(previousLevel);
      previousLevel = level;
    }
  });

  test("finishes with completed traces, mixed severity logs, and deterministic replay", () => {
    const done = getDemoFrame(DEMO_END);
    expect(done.pending).toBeNull();
    expect(done.actions.every((a) => a.status === "done")).toBe(true);
    expect(new Set(done.logs.map((log) => log.level))).toEqual(
      new Set(["info", "warning", "error"]),
    );
    expect(getDemoFrame(0).graph.nodes.size).toBe(3);
    expect(getDemoFrame(0).actions).toHaveLength(0);
    expect(getDemoFrame(0)).toEqual(getDemoFrame(0));
  });
});
