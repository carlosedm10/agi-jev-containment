import { expect, test } from "bun:test";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { GraphPanel } from "./GraphPanel";
import type { Graph, GraphNode } from "@/graph/protocol";

test("only the traversed edge animates, then clears on arrival and stop", async () => {
  const graph: Graph = {
    revision: 1, root: "a",
    nodes: new Map(["a", "b", "c"].map((id) => [id, {
      id, neighbors: ["a", "b", "c"].filter((other) => other !== id),
      run_id: "r", run_ids: ["r"], visit_count: 1, level: 0, threshold: 1,
      intent: null, event: { label: id }, action_id: null, created_at: null,
    } satisfies GraphNode])),
  };
  const container = document.createElement("div");
  document.body.append(container);
  const root = createRoot(container);
  const transition = () => container.querySelector("[data-transition]")?.getAttribute("data-transition");
  const render = (focusNodeId: string, runActive = true) => act(() => root.render(
    <GraphPanel graph={graph} pending={null} selectedNodeId={null} onSelectNode={() => {}}
      focusNodeId={focusNodeId} runActive={runActive} status="live" />,
  ));
  try {
    render("a");
    expect(transition()).toBeUndefined();
    render("b");
    expect(transition()).toBe("a->b");
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 700)); });
    expect(transition()).toBeUndefined();
    render("a");
    expect(transition()).toBe("b->a");
    render("a", false);
    expect(transition()).toBeUndefined();
  } finally {
    act(() => root.unmount());
    container.remove();
  }
});
