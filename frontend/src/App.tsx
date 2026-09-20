import { useEffect, useMemo, useState } from "react";
import { MotionConfig } from "framer-motion";

import { PageTabs } from "@/components/page-tabs";
import { InteractiveLogsTable } from "@/components/ui/interactive-logs-table";
import { ActivityPanel } from "@/dashboard/ActivityPanel";
import { GraphPanel } from "@/dashboard/GraphPanel";
import {
  useDemo,
  type DemoLog,
  type PendingAction,
  type SafeAction,
} from "@/dashboard/demo";
import { actionsFromIncident, logsFromGraph } from "@/dashboard/feeds";
import { latestRunNode } from "@/dashboard/graph-layout";
import { useIncidentFeed } from "@/dashboard/useIncidentFeed";
import { useLogFeed } from "@/dashboard/useLogFeed";
import type { Graph } from "@/graph/protocol";
import { useGraphStream, type GraphStreamStatus } from "@/graph/useGraphStream";

const EMPTY_GRAPH: Graph = { revision: 0, root: null, nodes: new Map() };

type DashboardProps = {
  graph: Graph;
  pending: PendingAction | null;
  actions: SafeAction[];
  logs: DemoLog[];
  status: GraphStreamStatus | null;
  onRestart?: () => void;
  onTrigger?: () => void;
  focusNodeId?: string | null;
  triggerError?: string | null;
  triggering?: boolean;
  onStop?: () => void;
  stopping?: boolean;
  runActive?: boolean;
  traceRunId?: string | null;
};

function Dashboard({
  graph,
  pending,
  actions,
  logs,
  status,
  onRestart,
  onTrigger,
  focusNodeId,
  triggerError,
  triggering,
  onStop,
  stopping,
  runActive,
  traceRunId,
}: DashboardProps) {
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  useEffect(() => {
    setSelectedNodeId(focusNodeId ?? null);
  }, [focusNodeId]);

  return (
    <MotionConfig reducedMotion="user">
      <main
        id="dashboard"
        aria-label={
          status === null
            ? "Agent safety dashboard · simulated data"
            : "Agent safety dashboard"
        }
        className="mx-auto min-h-dvh max-w-[1920px] bg-[#fdfcf4] p-4 text-zinc-900"
      >
        <header
          aria-label="AngryRobot"
          className="relative mb-2 flex h-14 items-center justify-center"
        >
          <h1>
            <img
              src="/angry-robot-wordmark.svg"
              alt="AngryRobot"
              width={110}
              height={48}
              className="h-12 w-auto"
            />
          </h1>
          <div className="absolute right-0"><PageTabs page="dashboard" runId={traceRunId} /></div>
        </header>
        <div className="dashboard-grid grid gap-2 lg:grid-cols-2">
          <section
            aria-label="Action graph and analysis"
            className="flex min-h-0 min-w-0 flex-col overflow-hidden rounded-md border shadow-xs"
          >
            <div className="min-h-0 flex-1">
              <GraphPanel
                graph={graph}
                pending={pending}
                selectedNodeId={selectedNodeId}
                onSelectNode={setSelectedNodeId}
                onRestart={onRestart}
                onTrigger={onTrigger}
                focusNodeId={focusNodeId}
                triggerError={triggerError}
                triggering={triggering}
                onStop={onStop}
                stopping={stopping}
                runActive={runActive}
                status={status}
              />
            </div>
          </section>
          <div className="grid min-h-0 min-w-0 grid-rows-[minmax(250px,0.95fr)_minmax(280px,1fr)] gap-2">
            <ActivityPanel
              actions={actions}
              selectedNodeId={selectedNodeId}
              onSelectNode={setSelectedNodeId}
            />
            <section
              aria-label="Container log viewer"
              className="min-h-0 min-w-0 overflow-hidden rounded-md border shadow-xs"
            >
              <InteractiveLogsTable logs={logs} />
            </section>
          </div>
        </div>
      </main>
    </MotionConfig>
  );
}

function DemoDashboard() {
  const demo = useDemo();
  return (
    <Dashboard
      key={demo.run}
      graph={demo.graph}
      pending={demo.pending}
      actions={demo.actions}
      logs={demo.logs}
      status={null}
      onRestart={demo.restart}
    />
  );
}

function StreamDashboard() {
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [stopping, setStopping] = useState(false);
  const [followRunId, setFollowRunId] = useState<string | null>(() => new URLSearchParams(window.location.search).get("run"));
  const [triggering, setTriggering] = useState(false);
  const [triggerError, setTriggerError] = useState<string | null>(null);
  const { graph, status } = useGraphStream();
  const incident = useIncidentFeed(followRunId);
  const { logs: liveLogs, clear: clearLogs } = useLogFeed();
  const view = useMemo(() => {
    const current = graph ?? EMPTY_GRAPH;
    if (!followRunId) return current;
    return {
      ...current,
      nodes: new Map(
        [...current.nodes].map(([id, node]) => {
          const state = node.run_states?.[followRunId];
          return [
            id,
            state ? { ...node, ...state, run_id: followRunId } : node,
          ];
        }),
      ),
    };
  }, [graph, followRunId]);
  const actions = useMemo(
    () => (incident === null ? [] : actionsFromIncident(incident)),
    [incident],
  );
  const logs = useMemo(
    () => liveLogs ?? logsFromGraph(graph ?? EMPTY_GRAPH),
    [liveLogs, graph],
  );

  useEffect(() => {
    if (!activeRunId) return;
    const controller = new AbortController();
    const timer = setInterval(async () => {
      try {
        const response = await fetch(
          `/api/demo/trigger/${encodeURIComponent(activeRunId)}`,
          { signal: controller.signal },
        );
        if (!response.ok) return;
        const state = await response.json();
        if (!controller.signal.aborted && state.active === false) {
          setActiveRunId(null);
          setStopping(false);
        }
      } catch {
        /* Retry while the run is active. */
      }
    }, 750);
    return () => {
      controller.abort();
      clearInterval(timer);
    };
  }, [activeRunId]);

  const stopRun = async () => {
    if (!activeRunId) return;
    setStopping(true);
    setTriggerError(null);
    try {
      const response = await fetch(
        `/api/demo/trigger/${encodeURIComponent(activeRunId)}/stop`,
        { method: "POST" },
      );
      if (!response.ok) throw new Error("Stop failed");
    } catch {
      setStopping(false);
      setTriggerError("Could not stop the run. Try again.");
    }
  };

  const triggerRun = async () => {
    clearLogs();
    setTriggering(true);
    setFollowRunId(null);
    setTriggerError(null);
    try {
      const response = await fetch("/api/demo/trigger", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        // Chains are 11-14 steps now; 900ms read as a blur across a branching graph.
        body: JSON.stringify({ delay_ms: 1800 }),
      });
      if (!response.ok) throw new Error("Trigger failed");
      const result = await response.json();
      if (typeof result.run_id !== "string") throw new Error("Missing run ID");
      setFollowRunId(result.run_id);
      setActiveRunId(result.run_id);
    } catch {
      setTriggerError("Could not start the run. Try again.");
    } finally {
      setTriggering(false);
    }
  };

  return (
    <Dashboard
      graph={view}
      pending={null}
      actions={actions}
      logs={logs}
      status={status}
      onTrigger={triggerRun}
      triggering={triggering}
      onStop={stopRun}
      stopping={stopping}
      runActive={activeRunId !== null}
      traceRunId={!activeRunId && !triggering ? followRunId : null}
      triggerError={triggerError}
      focusNodeId={
        triggering
          ? view.root
          : followRunId
            ? latestRunNode(view, followRunId)
            : null
      }
    />
  );
}

export default function App({ demo = false }: { demo?: boolean }) {
  return demo ? <DemoDashboard /> : <StreamDashboard />;
}
