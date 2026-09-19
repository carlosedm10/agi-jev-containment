import { useEffect, useMemo, useState } from "react";
import {
  Background,
  BackgroundVariant,
  Controls,
  ControlButton,
  Handle,
  Position,
  ReactFlow,
  useReactFlow,
  useStore,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import {
  Check,
  GitBranch,
  LoaderCircle,
  Maximize2,
  Minus,
  Plus,
  RotateCcw,
  ShieldAlert,
  Terminal,
  Workflow,
} from "lucide-react";
import "@xyflow/react/dist/style.css";

import { AnimatedSvgEdge } from "@/components/ui/animated-svg-edge";
import { BaseNode } from "@/components/ui/base-node";
import { Button } from "@/components/ui/button";
import { NodeStatusIndicator } from "@/components/ui/node-status-indicator";
import type { PendingAction } from "@/dashboard/demo";
import {
  layoutGraph,
  NODE_HEIGHT,
  NODE_WIDTH,
  type ActivityItem,
} from "@/dashboard/graph-layout";
import type { Graph } from "@/graph/protocol";

export type GraphPanelProps = {
  graph: Graph;
  pending: PendingAction | null;
  selectedNodeId: string | null;
  onSelectNode: (id: string) => void;
  onRestart: () => void;
};

type ActivityNode = Node<
  {
    item: ActivityItem;
    reducedMotion: boolean;
    onSelect: (id: string) => void;
  },
  "activity"
>;

const levels = [
  { label: "Benign", color: "#16814c", background: "#eef9f1" },
  { label: "Mild", color: "#a46708", background: "#fff8e8" },
  { label: "Moderate", color: "#a46708", background: "#fff8e8" },
  { label: "Severe", color: "#c74a27", background: "#fff2ed" },
  { label: "Critical", color: "#d32f3c", background: "#fff0f1" },
  { label: "Catastrophic", color: "#8f1d2c", background: "#fcebed" },
];

function ActivityCard({ data, selected }: NodeProps<ActivityNode>) {
  const { item, reducedMotion, onSelect } = data;
  const verdict = item.kind === "classified" ? levels[item.level] : undefined;
  const awaiting = item.kind === "pending";
  const structural = item.kind === "structure";
  const color = awaiting ? "#2563eb" : (verdict?.color ?? "#667085");
  const status = awaiting
    ? "Awaiting Jev"
    : structural
      ? item.runId
        ? "Agent run"
        : "Graph root"
      : `L${item.kind === "classified" ? item.level : ""} · ${verdict?.label ?? "Unrecognized level"}`;
  const Icon = awaiting
    ? LoaderCircle
    : structural
      ? item.runId
        ? GitBranch
        : Workflow
      : item.kind === "classified" && item.level === 0
        ? Check
        : ShieldAlert;

  return (
    <NodeStatusIndicator
      status={awaiting && !reducedMotion ? "loading" : "initial"}
    >
      <BaseNode
        role="button"
        aria-label={`${item.label}, ${status}${item.tool ? `, ${item.tool}` : ""}`}
        aria-pressed={selected}
        className="activity-node nodrag nopan focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-blue-600"
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            event.stopPropagation();
            onSelect(item.id);
          }
        }}
        style={{
          width: NODE_WIDTH,
          height: NODE_HEIGHT,
          borderRadius: 12,
          padding: "12px 14px",
          background: verdict?.background ?? "#fff",
          border: `1px solid ${selected ? color : awaiting ? "#b9d0fd" : verdict ? `${color}55` : "#e1e5eb"}`,
          boxShadow: selected
            ? `0 0 0 2px ${color}25, 0 5px 16px #172b4d10`
            : "0 2px 6px #172b4d06",
          cursor: "pointer",
          color: "#182230",
        }}
      >
        <Handle
          type="target"
          position={Position.Top}
          isConnectable={false}
          style={{ opacity: 0 }}
        />
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 7,
            color,
            fontSize: 10,
            fontWeight: 650,
            marginBottom: 9,
          }}
        >
          <Icon
            size={13}
            aria-hidden="true"
            className={awaiting && !reducedMotion ? "animate-spin" : undefined}
          />
          <span>{status}</span>
          {item.kind === "classified" && Number.isFinite(item.confidence) && (
            <span
              title="Jev confidence, independent of severity level"
              style={{ marginLeft: "auto", color: "#7b8492", fontWeight: 500 }}
            >
              {Math.round(item.confidence * 100)}%
            </span>
          )}
        </div>
        <div
          title={item.label}
          style={{
            fontSize: 13,
            fontWeight: 650,
            lineHeight: "18px",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {item.label}
        </div>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 5,
            marginTop: 8,
            color: "#7b8492",
            fontSize: 10,
          }}
        >
          {!structural && <Terminal size={11} aria-hidden="true" />}
          <span
            style={{
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {item.tool || (structural ? "Unclassified structure" : item.runId)}
          </span>
          {verdict && (
            <span
              aria-hidden="true"
              style={{
                marginLeft: "auto",
                flexShrink: 0,
                height: 6,
                width: 6,
                borderRadius: "50%",
                background: color,
              }}
            />
          )}
        </div>
        <Handle
          type="source"
          position={Position.Bottom}
          isConnectable={false}
          style={{ opacity: 0 }}
        />
      </BaseNode>
    </NodeStatusIndicator>
  );
}

const nodeTypes = { activity: ActivityCard };
const edgeTypes = { activity: AnimatedSvgEdge };

function GraphControls() {
  const { zoomIn, zoomOut, fitBounds, getNodesBounds, getNodes } =
    useReactFlow();
  return (
    <Controls
      position="bottom-right"
      orientation="horizontal"
      showZoom={false}
      showFitView={false}
      showInteractive={false}
    >
      <ControlButton
        title="Zoom in"
        aria-label="Zoom in"
        onClick={() => void zoomIn()}
        style={{ width: 38, height: 38 }}
      >
        <Plus aria-hidden="true" />
      </ControlButton>
      <ControlButton
        title="Zoom out"
        aria-label="Zoom out"
        onClick={() => void zoomOut()}
        style={{ width: 38, height: 38 }}
      >
        <Minus aria-hidden="true" />
      </ControlButton>
      <ControlButton
        title="Fit graph to view"
        aria-label="Fit graph to view"
        onClick={() =>
          void fitBounds(getNodesBounds(getNodes()), { padding: 0.18 })
        }
        style={{ width: 38, height: 38 }}
      >
        <Maximize2 aria-hidden="true" />
      </ControlButton>
    </Controls>
  );
}

function FollowViewport({
  nodeKey,
  reducedMotion,
}: {
  nodeKey: string;
  reducedMotion: boolean;
}) {
  const width = useStore((state) => state.width);
  const height = useStore((state) => state.height);
  const { fitBounds, getNodesBounds, getNodes } = useReactFlow();
  useEffect(() => {
    if (!width || !height) return;
    const frame = requestAnimationFrame(() => {
      void fitBounds(getNodesBounds(getNodes()), {
        padding: 0.18,
        duration: reducedMotion ? 0 : 250,
      });
    });
    return () => cancelAnimationFrame(frame);
  }, [
    nodeKey,
    reducedMotion,
    fitBounds,
    getNodesBounds,
    getNodes,
    width,
    height,
  ]);
  return null;
}

export function GraphPanel({
  graph,
  pending,
  selectedNodeId,
  onSelectNode,
  onRestart,
}: GraphPanelProps) {
  const [reducedMotion, setReducedMotion] = useState(
    () =>
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  );
  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReducedMotion(media.matches);
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);

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
