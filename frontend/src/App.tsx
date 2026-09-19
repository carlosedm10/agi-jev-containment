import { useState } from "react";
import { ArrowUpRight, X } from "lucide-react";
import { MotionConfig } from "framer-motion";

import { Button } from "@/components/ui/button";
import { InteractiveLogsTable } from "@/components/ui/interactive-logs-table";
import { ActivityPanel } from "@/dashboard/ActivityPanel";
import { GraphPanel } from "@/dashboard/GraphPanel";
import { LEVEL_LABELS, useDemo } from "@/dashboard/demo";
import { cn } from "@/lib/utils";

export default function App() {
  const demo = useDemo();
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const selected = selectedNodeId ? demo.graph.nodes.get(selectedNodeId) : null;
  const pendingSelected =
    selectedNodeId === demo.pending?.id ? demo.pending : null;
  const inspectorTitle =
    pendingSelected?.label ??
    String(selected?.event?.label ?? selected?.id ?? "");

  return (
    <MotionConfig reducedMotion="user">
      <main
        id="dashboard"
        aria-label="Agent safety dashboard · simulated data"
        className="mx-auto min-h-dvh max-w-[1920px] bg-white p-4 text-zinc-900"
      >
        <header
          aria-label="AngryRobot"
          className="mb-2 flex h-14 items-center justify-center"
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
        </header>
        <div
          key={demo.run}
          className="dashboard-grid grid gap-2 lg:grid-cols-2"
        >
          <section
            aria-label="Action graph and analysis"
            className="flex min-h-0 min-w-0 flex-col overflow-hidden rounded-xl border shadow-xs"
          >
            <div className="min-h-0 flex-1">
              <GraphPanel
                graph={demo.graph}
                pending={demo.pending}
                selectedNodeId={selectedNodeId}
                onSelectNode={setSelectedNodeId}
                onRestart={() => {
                  setSelectedNodeId(null);
                  demo.restart();
                }}
              />
            </div>
            {(selected || pendingSelected) && (
              <section
                aria-label="Selected action analysis"
                className="max-h-56 shrink-0 overflow-y-auto border-t bg-white p-4"
              >
                <div className="mb-2 flex items-start justify-between gap-2">
                  <h3 className="text-sm font-semibold">{inspectorTitle}</h3>
                  <Button
                    aria-label="Close analysis"
                    size="icon-sm"
                    variant="ghost"
                    onClick={() => setSelectedNodeId(null)}
                  >
                    <X />
                  </Button>
                </div>
                <p className="text-xs leading-relaxed text-zinc-600">
                  {pendingSelected
                    ? "Awaiting Jev. No safety verdict or protective action has been assigned to this event."
                    : String(
                        selected?.event?.summary ??
                          "Structural graph node. This groups the session or run; it is not a safety verdict.",
                      )}
                </p>
                {selected?.event && (
                  <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px]">
                    <span
                      className={cn(
                        "rounded-md border px-2 py-1 font-medium",
                        selected.level >= 3
                          ? "border-red-200 bg-red-50 text-red-700"
                          : selected.level > 0
                            ? "border-amber-200 bg-amber-50 text-amber-800"
                            : "border-emerald-200 bg-emerald-50 text-emerald-700",
                      )}
                    >
                      L{selected.level} · {LEVEL_LABELS[selected.level]}
                    </span>
                    <span className="rounded-md bg-zinc-100 px-2 py-1">
                      {Math.round(selected.threshold * 100)}% confidence
                    </span>
                    <span className="font-mono text-zinc-500">
                      {selected.intent}
                    </span>
                  </div>
                )}
                {selected?.action_id && (
                  <p className="mt-2 flex items-center gap-1 text-[11px] text-zinc-500">
                    <ArrowUpRight className="size-3" />
                    Response trace:{" "}
                    <span className="font-mono">{selected.action_id}</span>
                  </p>
                )}
              </section>
            )}
          </section>
          <div className="grid min-h-0 min-w-0 grid-rows-[minmax(250px,0.95fr)_minmax(280px,1fr)] gap-2">
            <ActivityPanel
              actions={demo.actions}
              selectedNodeId={selectedNodeId}
              onSelectNode={setSelectedNodeId}
            />
            <section
              aria-label="Container log viewer"
              className="min-h-0 min-w-0 overflow-hidden rounded-xl border shadow-xs"
            >
              <InteractiveLogsTable logs={demo.logs} />
            </section>
          </div>
        </div>
      </main>
    </MotionConfig>
  );
}
