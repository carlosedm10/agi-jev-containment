import { useEffect, useMemo, useRef } from "react";
import {
  Background,
  BackgroundVariant,
  ReactFlow,
  type Edge,
} from "@xyflow/react";
import { Play, RotateCcw, Square, Workflow } from "lucide-react";
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
import {
  eventText,
  layoutGraph,
  NODE_HEIGHT,
  NODE_WIDTH,
} from "@/dashboard/graph-layout";
import type { Graph } from "@/graph/protocol";
import type { GraphStreamStatus } from "@/graph/useGraphStream";
import { cn } from "@/lib/utils";

type GraphPanelProps = {
  graph: Graph;
  pending: PendingAction | null;
  selectedNodeId: string | null;
  onSelectNode: (id: string) => void;
  onRestart?: () => void;
  onTrigger?: () => void;
  focusNodeId?: string | null;
  triggerError?: string | null;
  triggering?: boolean;
  onStop?: () => void;
  stopping?: boolean;
  runActive?: boolean;
  status?: GraphStreamStatus | null;
};

const STATUS_PILL: Record<GraphStreamStatus, { dot: string; text: string }> = {
  live: { dot: "bg-[#027a48] animate-pulse", text: "LIVE" },
  connecting: { dot: "bg-[#1447e6]", text: "CONNECTING" },
  reconnecting: { dot: "bg-[#b06a38]", text: "RECONNECTING" },
};

export function GraphPanel({
  graph,
  pending,
  selectedNodeId,
  onSelectNode,
  onRestart,
  onTrigger,
  focusNodeId,
  triggerError,
  triggering,
  onStop,
  stopping,
  runActive,
  status = null,
}: GraphPanelProps) {
  const reducedMotion = useReducedMotion();

  const layout = useMemo(() => layoutGraph(graph, pending), [graph, pending]);

  const seen = useRef(new Set<string>());
  const fresh = useMemo(
    () =>
      new Set(
        layout.nodes
          .filter((item) => !seen.current.has(item.id))
          .map((item) => item.id),
      ),
    [layout.nodes],
  );
  useEffect(() => {
    for (const id of fresh) seen.current.add(id);
  }, [fresh]);

  const nodes = useMemo<ActivityNode[]>(
    () =>
      layout.nodes.map((item) => ({
        id: item.id,
        type: "activity",
        position: item.position,
        width: NODE_WIDTH,
        height: NODE_HEIGHT,
        selected: item.id === (focusNodeId ?? selectedNodeId),
        className: fresh.has(item.id) ? "live-node-new" : undefined,
        data: { item, reducedMotion, onSelect: onSelectNode },
      })),
    [
      layout.nodes,
      fresh,
      selectedNodeId,
      focusNodeId,
      reducedMotion,
      onSelectNode,
    ],
  );
  const edges = useMemo<Edge[]>(() => {
    return layout.links.map((link) => ({
      id: link.id,
      source: link.source,
      target: link.target,
      type:
        (link.pending ||
          link.source === focusNodeId ||
          link.target === focusNodeId) &&
        !reducedMotion
          ? "activity"
          : "default",
      data: { duration: 3, path: "bezier" },
      style: {
        stroke: link.pending ? "#a8bbef" : "#c8c3bc",
        strokeWidth: 1.5,
        strokeDasharray: link.pending ? "4 4" : undefined,
      },
      selectable: false,
      focusable: false,
    }));
  }, [layout.links, reducedMotion, focusNodeId]);
  const focused = focusNodeId ? graph.nodes.get(focusNodeId) : undefined;
  const nodeKey = JSON.stringify([
    focused
      ? [
          focused.id,
          layout.nodes.find((node) => node.id === focused.id)?.position,
        ]
      : layout.nodes.map((node) => node.id),
    focused ? eventText(focused, ["id", "event_id"], "") : null,
  ]);
  const pill = status === null ? null : STATUS_PILL[status];

  return (
    <section
      className="graph-panel"
      aria-label="Agent activity graph"
      style={{
        height: "100%",
        minHeight: 0,
        display: "flex",
        flexDirection: "column",
        background: "#fcfcfc",
      }}
    >
      <header className="flex h-10 shrink-0 items-center justify-between gap-3 border-b border-[#b06a38] bg-[#d59566] px-4">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-[#1a1614]">
          Agent activity
        </h2>
        <div className="flex items-center gap-2">
          {pill && (
            <span
              aria-label="Stream status"
              className="flex items-center gap-1.5 rounded-full border border-transparent bg-[#fdfcf4] px-2.5 py-0.5 font-mono text-[10px] tracking-widest text-[#1a1614]"
            >
              <span
                aria-hidden="true"
                className={cn(
                  "inline-block h-1.5 w-1.5 rounded-full",
                  pill.dot,
                )}
              />
              {pill.text}
            </span>
          )}
          {onTrigger && (
            <Button
              variant="default"
              size="icon-sm"
              aria-label="Trigger a live demo run"
              title="Run again"
              onClick={onTrigger}
              disabled={triggering || runActive}
              className="bg-[#fdfcf4] text-[#1a1614] hover:bg-[#f2f2f2]"
            >
              <Play aria-hidden="true" />
            </Button>
          )}
          {onRestart && (
            <Button
              variant="outline"
              size="icon-sm"
              aria-label="Restart test run"
              title="Restart test run"
              onClick={onRestart}
              className="border-[#1a1614]/20 bg-[#fdfcf4] text-[#1a1614] hover:bg-[#f2f2f2]"
            >
              <RotateCcw aria-hidden="true" />
            </Button>
          )}
          {onStop && (
            <Button
              variant="outline"
              size="icon-sm"
              onClick={onStop}
              disabled={!runActive || stopping}
              aria-label="Stop run"
              title={stopping ? "Stopping…" : "Stop run"}
              aria-busy={stopping}
            >
              <Square aria-hidden="true" />
            </Button>
          )}
        </div>
      </header>
      {triggerError && (
        <p role="alert" className="px-4 py-2 text-xs text-red-700">
          {triggerError}
        </p>
      )}
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
          style={{ background: "#fcfcfc", color: "#4e81d1" }}
          aria-label="Read-only agent activity. Select a node for details; drag the canvas to pan."
        >
          <Background
            variant={BackgroundVariant.Dots}
            gap={20}
            size={1}
            color="#e9edf2"
          />
          <GraphControls />
          <FollowViewport
            nodeKey={nodeKey}
            reducedMotion={reducedMotion}
            focusNodeId={focusNodeId}
          />
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
