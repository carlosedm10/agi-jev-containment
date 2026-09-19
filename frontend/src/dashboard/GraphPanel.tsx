import { useMemo } from "react";
import {
  Background,
  BackgroundVariant,
  ReactFlow,
  type Edge,
} from "@xyflow/react";
import { RotateCcw, Workflow } from "lucide-react";
import "@xyflow/react/dist/style.css";

import {
  edgeTypes,
  FollowViewport,
  GraphControls,
  nodeTypes,
  useReducedMotion,
  type ActivityNode,
} from "@/components/activity-graph";
import { Button } from "@/components/ui/button";
import type { PendingAction } from "@/dashboard/demo";
import { layoutGraph, NODE_HEIGHT, NODE_WIDTH } from "@/dashboard/graph-layout";
import type { Graph } from "@/graph/protocol";

export type GraphPanelProps = {
  graph: Graph;
  pending: PendingAction | null;
  selectedNodeId: string | null;
  onSelectNode: (id: string) => void;
  onRestart: () => void;
};

export function GraphPanel({
  graph,
  pending,
  selectedNodeId,
  onSelectNode,
  onRestart,
}: GraphPanelProps) {
  const reducedMotion = useReducedMotion();

  const layout = useMemo(() => layoutGraph(graph, pending), [graph, pending]);
  const nodes = useMemo<ActivityNode[]>(
    () =>
      layout.nodes.map((item) => ({
        id: item.id,
        type: "activity",
        position: item.position,
        width: NODE_WIDTH,
        height: NODE_HEIGHT,
        selected: item.id === selectedNodeId,
        data: { item, reducedMotion, onSelect: onSelectNode },
      })),
    [layout.nodes, selectedNodeId, reducedMotion, onSelectNode],
  );
  const edges = useMemo<Edge[]>(
    () =>
      layout.links.map((link) => ({
        id: link.id,
        source: link.source,
        target: link.target,
        type: link.pending && !reducedMotion ? "activity" : "default",
        data: {
          duration: 2.5,
          direction: "alternate",
          path: "bezier",
          shape: "circle",
        },
        style: {
          stroke: link.pending ? "#9dbaf0" : "#d4dae3",
          strokeWidth: 1.5,
          strokeDasharray: link.pending ? "4 4" : undefined,
        },
        selectable: false,
        focusable: false,
      })),
    [layout.links, reducedMotion],
  );
  const nodeKey = JSON.stringify(layout.nodes.map((node) => node.id));

  return (
    <section
      className="graph-panel"
      aria-label="Agent activity graph"
      style={{
        height: "100%",
        minHeight: 0,
        display: "flex",
        flexDirection: "column",
        background: "#fff",
      }}
    >
      <header className="flex shrink-0 items-center justify-between gap-3 border-b px-4 py-3">
        <h2 className="text-sm font-semibold text-zinc-900">Agent activity</h2>
        <Button
          variant="outline"
          size="sm"
          aria-label="Restart test run"
          onClick={onRestart}
        >
          <RotateCcw aria-hidden="true" />
          Restart test run
        </Button>
      </header>
      <div style={{ flex: 1, minHeight: 220, position: "relative" }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          nodesDraggable={false}
          nodesConnectable={false}
          nodesFocusable={false}
          edgesFocusable={false}
          elementsSelectable={false}
          onNodeClick={(_, node) => onSelectNode(node.id)}
          deleteKeyCode={null}
          minZoom={0.25}
          maxZoom={1.8}
          style={{ background: "#fff", color: "#4e81d1" }}
          aria-label="Read-only agent activity. Select a node for details; drag the canvas to pan."
        >
          <Background
            variant={BackgroundVariant.Dots}
            gap={20}
            size={1}
            color="#e9edf2"
          />
          <GraphControls />
          <FollowViewport nodeKey={nodeKey} reducedMotion={reducedMotion} />
        </ReactFlow>
        {nodes.length === 0 && (
          <div
            role="status"
            style={{
              position: "absolute",
              inset: 0,
              display: "grid",
              placeContent: "center",
              textAlign: "center",
              pointerEvents: "none",
              color: "#7b8492",
              fontSize: 12,
            }}
          >
            <Workflow
              size={26}
              aria-hidden="true"
              style={{ margin: "0 auto 12px", color: "#a5afbd" }}
            />
            <strong style={{ color: "#4a5565", fontWeight: 550 }}>
              Waiting for agent activity
            </strong>
            <span style={{ marginTop: 6 }}>
              Classified actions will appear here.
            </span>
          </div>
        )}
      </div>
    </section>
  );
}
