import { useEffect, useMemo, useState } from "react";
import { Background, MarkerType, ReactFlow, type Edge } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Button } from "@/components/ui/button";
import { PageTabs } from "@/components/page-tabs";
import {
  FollowViewport,
  GraphControls,
  nodeTypes,
  useReducedMotion,
  type ActivityNode,
} from "@/components/activity-graph";
import { eventLabel, NODE_HEIGHT, NODE_WIDTH } from "@/dashboard/graph-layout";

import { useIncidentFeed } from "@/dashboard/useIncidentFeed";
import {
  ForensicsSummary,
  type ExplanationSource,
} from "./ForensicsSummary";

/**
 * Upper bound on a generated audit paragraph, mirroring MAX_CHARS in
 * backend/app/runs/explanations.py. It guards against a model that ignores its
 * limit; set below the backend's cap it silently rejects every valid response and
 * the page falls back to recorded labels, which is how it failed before.
 */
const MAX_COPY_CHARS = 340;

export type TraceEvent = {
  id: string;
  sequence: number | null;
  timestamp: string;
  kind: string;
  phase: string;
  tool: string | null;
  target: string | null;
  agent: string | null;
  channel: string | null;
  content: string | null;
  level: number | null;
  action_level?: number;
};
type Trace = { run_id: string; events: TraceEvent[]; warning: string | null };

export function TracePage({
  runId = new URLSearchParams(window.location.search).get("run") ?? "",
}: {
  runId?: string;
}) {
  const [trace, setTrace] = useState<Trace | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [explanations, setExplanations] = useState<Record<
    string,
    string
  > | null>(null);
  const [explanationSource, setExplanationSource] =
    useState<ExplanationSource | null>(null);
  // Named by the API so the page reports the model that actually wrote the copy.
  const [explanationModel, setExplanationModel] = useState<string | null>(null);
  const reducedMotion = useReducedMotion();
  const incident = useIncidentFeed(runId || null);
  useEffect(() => {
    if (!runId) return;
    const controller = new AbortController();
    setTrace(null);
    setError(null);
    setSelectedId(null);
    setExplanations(null);
    setExplanationSource(null);
    setExplanationModel(null);
    fetch(`/api/runs/${encodeURIComponent(runId)}/trace`, {
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) throw new Error("Could not load this trace.");
        const data = await response.json();
        if (
          !Array.isArray(data.events) ||
          !data.events.every(
            (event: TraceEvent) =>
              event &&
              typeof event.id === "string" &&
              typeof event.kind === "string",
          )
        )
          throw new Error("Invalid trace response.");
        if (!controller.signal.aborted) {
          setTrace(data);
          setSelectedId(data.events[0]?.id ?? null);
          if (data.events.length) {
            void fetch(
              `/api/runs/${encodeURIComponent(runId)}/trace/explanations`,
              {
                method: "POST",
                signal: controller.signal,
              },
            )
              .then(async (response) => {
                if (!response.ok) throw new Error("Explanations unavailable");
                const result = await response.json();
                const copy = result.explanations;
                if (
                  !copy ||
                  typeof copy !== "object" ||
                  Array.isArray(copy) ||
                  !Object.values(copy).every(
                    (value) =>
                      typeof value === "string" && value.length <= MAX_COPY_CHARS,
                  )
                )
                  throw new Error("Invalid explanations");
                const explained = Object.keys(copy).length;
                const source: ExplanationSource =
                  result.source === "llm" ||
                  result.source === "partial" ||
                  result.source === "unavailable"
                    ? result.source
                    : explained === 0
                      ? "unavailable"
                      : explained === data.events.length
                        ? "llm"
                        : "partial";
                if (!controller.signal.aborted) {
                  setExplanations(copy);
                  setExplanationSource(source);
                  setExplanationModel(
                    typeof result.model === "string" && result.model
                      ? result.model
                      : null,
                  );
                }
              })
              .catch(() => {
                if (!controller.signal.aborted) {
                  setExplanations({});
                  setExplanationSource("unavailable");
                }
              });
          }
        }
      })
      .catch((reason: Error) => {
        if (!controller.signal.aborted) setError(reason.message);
      });
    return () => controller.abort();
  }, [runId, attempt]);
  const nodes = useMemo<ActivityNode[]>(
    () =>
      (trace?.events ?? []).map((event, index) => ({
        id: event.id,
        type: "activity",
        position: { x: index * (NODE_WIDTH + 80), y: 0 },
        width: NODE_WIDTH,
        height: NODE_HEIGHT + 32,
        selected: event.id === selectedId,
        data: {
          reducedMotion,
          horizontal: true,
          timestamp: event.timestamp,
          onSelect: setSelectedId,
          item: {
            id: event.id,
            runId,
            label: `${index + 1}. ${explanations?.[event.id] ?? eventLabel({ event })}`,
            tool: [event.tool, event.target].filter(Boolean).join(" · "),
            // "completed" is every ordinary step; only an unfinished phase is worth saying.
            context: event.phase && event.phase !== "completed" ? event.phase : "",
            position: { x: index * (NODE_WIDTH + 80), y: 0 },
            ...(event.level === null
              ? { kind: "recorded" as const }
              : {
                  kind: "classified" as const,
                  level: event.level,
                  actionLevel: event.action_level,
                  confidence: Number.NaN,
                }),
          },
        },
      })),
    [trace, selectedId, reducedMotion, runId, explanations],
  );
  const edges = useMemo<Edge[]>(
    () =>
      nodes.slice(1).map((node, index) => ({
        id: `next:${index}`,
        source: nodes[index].id,
        target: node.id,
        type: "smoothstep",
        markerEnd: { type: MarkerType.ArrowClosed, color: "#b06a38" },
        style: { stroke: "#b06a38", strokeWidth: 1.5 },
      })),
    [nodes],
  );
  return (
    <main className="flex h-dvh flex-col bg-[#fdfcf4] p-4 text-zinc-900">
      <header className="mx-auto mb-4 flex w-full max-w-[1920px] shrink-0 items-center justify-between gap-4">
        <a href="/" aria-label="Back to dashboard">
          <img
            src="/angry-robot-wordmark.svg"
            alt="AngryRobot"
            className="h-12 w-auto"
          />
        </a>
        <PageTabs page="trace" runId={runId} />
      </header>
      <section className="mx-auto flex w-full min-h-0 max-w-[1920px] flex-1 flex-col overflow-hidden rounded-md border shadow-xs">
        {!runId ? (
          <p className="p-6">
            Open a completed run’s “View trace” link from the dashboard.
          </p>
        ) : error ? (
          <div role="alert" className="p-6">
            {error}{" "}
            <Button variant="outline" onClick={() => setAttempt(attempt + 1)}>
              Retry
            </Button>
          </div>
        ) : !trace ? (
          <p role="status" className="p-6">
            Loading trace…
          </p>
        ) : !trace.events.length ? (
          <p role="status" className="p-6">
            No recorded actions found for this run.
          </p>
        ) : (
          <>
            {trace.warning && (
              <p
                role="status"
                className="border-b bg-amber-50 px-4 py-2 text-xs"
              >
                {trace.warning}
              </p>
            )}
            <header className="flex h-10 shrink-0 items-center border-b border-[#b06a38] bg-[#d59566] px-4">
              <h1 className="text-sm font-semibold uppercase tracking-wider text-[#1a1614]">
                Run trace &amp; forensics
              </h1>
            </header>
            <div className="grid min-h-0 flex-1 lg:grid-cols-2">
              <div className="flex min-h-[320px] min-w-0 flex-col border-r border-[#e2ddd4]">
                <div
                  className="min-h-0 flex-1 bg-[#fcfcfc]"
                  aria-label="Action timeline"
                >
                <ReactFlow
                  nodes={nodes}
                  edges={edges}
                  nodeTypes={nodeTypes}
                  nodesDraggable={false}
                  nodesConnectable={false}
                  elementsSelectable={false}
                  onNodeClick={(_, node) => setSelectedId(node.id)}
                  deleteKeyCode={null}
                  minZoom={0.15}
                  maxZoom={1.8}
                >
                  <Background gap={20} size={1} color="#e9edf2" />
                  <GraphControls />
                  <FollowViewport
                    nodeKey={selectedId ?? runId}
                    focusNodeId={selectedId}
                    zoom={1.25}
                    reducedMotion={reducedMotion}
                  />
                </ReactFlow>
                </div>
              </div>
              <ForensicsSummary
                events={trace.events}
                explanations={explanations}
                incident={incident}
                model={explanationModel}
                state={
                  explanations === null
                    ? "loading"
                    : (explanationSource ?? "unavailable")
                }
                selectedNodeId={selectedId}
                onSelectNode={setSelectedId}
              />
            </div>
          </>
        )}
      </section>
    </main>
  );
}
