import { Diamond } from "@/components/loading-ui/diamond";
import TaskRows from "@/components/ui/task-rows";
import type { SafeAction } from "@/dashboard/demo";
import { localTime } from "@/lib/time";

export function ActivityPanel({
  actions,
  selectedNodeId,
  onSelectNode,
  title = "Protective actions",
  empty = "Monitoring Jev",
}: {
  actions: SafeAction[];
  selectedNodeId: string | null;
  onSelectNode: (id: string) => void;
  title?: string;
  empty?: string;
}) {
  return (
    <section
      aria-label={title}
      className="flex h-full min-h-0 min-w-0 flex-col overflow-hidden rounded-md border bg-[#fcfcfc] shadow-xs"
    >
      <header className="flex h-10 shrink-0 items-center border-b border-[#b06a38] bg-[#d59566] px-4">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-[#1a1614]">
          {title}
        </h2>
      </header>
      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        {actions.length > 0 ? (
          <TaskRows
            variant="List"
            rows={actions.map((action) => ({
              key: action.id,
              label: action.title,
              amount: `${action.source} · L${action.level} · ${localTime(action.startedAt)}`,
              status: action.status,
              selected: action.nodeId === selectedNodeId,
              details: action.details,
            }))}
            onToggleRow={(id, open) => {
              const action = actions.find((entry) => entry.id === id);
              if (open && action) onSelectNode(action.nodeId);
            }}
          />
        ) : (
          <div
            role="status"
            className="grid h-full place-content-center justify-items-center gap-4 px-4 text-center"
          >
            {/* The caption below carries the meaning, so the pixels are decorative. */}
            <Diamond aria-hidden="true" className="size-16 text-[#b06a38]" />
            <p className="text-xs font-medium text-zinc-600">{empty}</p>
          </div>
        )}
      </div>
    </section>
  );
}
